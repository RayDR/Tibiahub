from __future__ import annotations

from app.core.security import create_access_token
from app.models.leadership import GuildLeadershipApplication, GuildLeadershipAssignment
from app.models.raffle import InternalNotification
from app.models.workspace_audit import WorkspaceAudit
from app.models.user_character import UserCharacter
from tests.conftest import make_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def opening_payload(**overrides):
    payload = {"title": "Viceleader opening", "description": "Help lead the guild", "responsibilities": "Support members fairly", "requirements": "Active respectful member", "openings_count": 1, "allow_viceleader_review": True, "voting_enabled": True, "votes_required": 1, "target_count": 4}
    payload.update(overrides); return payload


def application_payload(character="Applicant Knight", conduct=True):
    return {"character_name": character, "why_apply": "I want to support every guild member.", "contribution": "I can organize activities and resolve conflict.", "availability": "Ten hours weekly", "leadership_experience": "I have led gaming communities before.", "conduct_agreed": conduct}


def link_verified(db, user, guild: str, rank: str, suffix: str = "Identity"):
    db.add(UserCharacter(user_id=user.id, character_name=f"{user.username} {suffix}", normalized_name=f"{user.username} {suffix}".casefold(), ownership_status="verified", ownership_verified_at=user.created_at, guild_name=guild, guild_rank=rank, world_name="Antica"))


def setup_opening(client, db, *, guild="Leadership One", allow_review=True):
    leader = make_user(db, username=f"leader-{guild}", guild_name=guild, guild_rank="Leader")
    link_verified(db, leader, guild, "Leader")
    db.commit()
    created = client.post("/api/v1/guild/me/leadership/openings", json=opening_payload(allow_viceleader_review=allow_review), headers=auth(leader))
    assert created.status_code == 201
    opened = client.post(f"/api/v1/guild/me/leadership/openings/{created.json()['id']}/open", headers=auth(leader))
    assert opened.status_code == 200
    return leader, opened.json()


def setup_applicant(db, *, username="leadership-applicant", guild="Leadership One", character="Applicant Knight"):
    user = make_user(db, username=username, guild_name=guild, guild_rank="Member")
    user.tibia_character_name = character; user.level = 500; user.vocation = "Elite Knight"; user.world_name = "Antica"
    db.add(UserCharacter(user_id=user.id, character_name=character, normalized_name=character.casefold(), ownership_status="verified", ownership_verified_at=user.created_at, guild_name=guild, guild_rank="Member", level=500, vocation="Elite Knight", world_name="Antica")); db.commit()
    return user


def test_openings_are_guild_scoped_and_conduct_is_required(client, db):
    _, opening = setup_opening(client, db)
    applicant = setup_applicant(db)
    other = setup_applicant(db, username="other-guild-member", guild="Other", character="Other Knight")
    assert client.post(f"/api/v1/guild/me/leadership/openings/{opening['id']}/applications", json=application_payload(conduct=False), headers=auth(applicant)).status_code == 422
    assert client.post(f"/api/v1/guild/me/leadership/openings/{opening['id']}/applications", json=application_payload("Other Knight"), headers=auth(other)).status_code == 404


def test_drafts_are_manager_only_and_member_openings_do_not_mask_applications(client, db):
    guild = "Visible Guild"
    leader = make_user(db, username="visible-leader", guild_name=guild, guild_rank="Leader")
    vice = make_user(db, username="visible-vice", guild_name=guild, guild_rank="Vice Leader")
    link_verified(db, leader, guild, "Leader")
    link_verified(db, vice, guild, "Vice Leader")
    member = setup_applicant(db, username="visible-member", guild=guild, character="Visible Knight")
    admin = make_user(db, username="visible-admin", guild_name="Admin Home", is_superuser=True)
    db.commit()
    created = client.post("/api/v1/guild/me/leadership/openings", json=opening_payload(), headers=auth(leader))
    assert created.status_code == 201 and created.json()["status"] == "draft"
    opening_id = created.json()["id"]
    assert [row["id"] for row in client.get("/api/v1/guild/me/leadership/openings", headers=auth(leader)).json()] == [opening_id]
    assert client.get("/api/v1/guild/me/leadership/openings", headers=auth(vice)).json() == []
    assert client.get("/api/v1/guild/me/leadership/openings", headers=auth(member)).json() == []
    assert client.get(f"/api/v1/guild/me/leadership/openings/{opening_id}", headers=auth(member)).status_code == 404
    assisted = client.get("/api/v1/admin/guilds/visible-guild/leadership/openings", headers=auth(admin))
    assert assisted.status_code == 200 and assisted.json()[0]["status"] == "draft"

    assert client.post(f"/api/v1/guild/me/leadership/openings/{opening_id}/open", headers=auth(leader)).status_code == 200
    assert [row["id"] for row in client.get("/api/v1/guild/me/leadership/openings", headers=auth(member)).json()] == [opening_id]
    application = client.post(
        f"/api/v1/guild/me/leadership/openings/{opening_id}/applications",
        json=application_payload("Visible Knight"), headers=auth(member),
    )
    assert application.status_code == 201
    assert client.get("/api/v1/guild/me/leadership/openings", headers=auth(member)).json() == []
    mine = client.get("/api/v1/guild/me/leadership/applications/mine", headers=auth(member)).json()
    assert [row["id"] for row in mine] == [application.json()["id"]]


def test_account_cannot_duplicate_application_using_another_character(client, db):
    _, opening = setup_opening(client, db, guild="Duplicate Guild")
    applicant = setup_applicant(db, guild="Duplicate Guild", character="First Knight")
    db.add(UserCharacter(user_id=applicant.id, character_name="Second Knight", normalized_name="second knight", ownership_status="verified", ownership_verified_at=applicant.created_at, guild_name="Duplicate Guild", guild_rank="Member")); db.commit()
    assert client.post(f"/api/v1/guild/me/leadership/openings/{opening['id']}/applications", json=application_payload("First Knight"), headers=auth(applicant)).status_code == 201
    assert client.post(f"/api/v1/guild/me/leadership/openings/{opening['id']}/applications", json=application_payload("Second Knight"), headers=auth(applicant)).status_code == 409


def test_applicant_privacy_and_internal_messages(client, db):
    leader, opening = setup_opening(client, db, guild="Private Guild")
    applicant = setup_applicant(db, guild="Private Guild", character="Private Knight")
    outsider = setup_applicant(db, username="private-outsider", guild="Private Guild", character="Outsider Knight")
    created = client.post(f"/api/v1/guild/me/leadership/openings/{opening['id']}/applications", json=application_payload("Private Knight"), headers=auth(applicant)).json()
    assert client.get(f"/api/v1/guild/me/leadership/applications/{created['id']}", headers=auth(outsider)).status_code == 403
    comment = {"audience": "applicant", "message_type": "general", "body": "Reviewer-only assessment"}
    assert client.post(f"/api/v1/guild/me/leadership/applications/{created['id']}/comments", json=comment, headers=auth(leader)).status_code == 201
    own = client.get(f"/api/v1/guild/me/leadership/applications/{created['id']}", headers=auth(applicant)).json()
    assert "answers" not in own and "vote_summary" not in own and own["messages"] == []


def test_viceleader_review_is_explicit_and_cannot_decide(client, db):
    leader, opening = setup_opening(client, db, guild="Review Guild", allow_review=True)
    vice = make_user(db, username="review-vice", guild_name="Review Guild", guild_rank="Vice Leader")
    link_verified(db, vice, "Review Guild", "Vice Leader")
    applicant = setup_applicant(db, guild="Review Guild", character="Review Knight")
    db.commit(); created = client.post(f"/api/v1/guild/me/leadership/openings/{opening['id']}/applications", json=application_payload("Review Knight"), headers=auth(applicant)).json()
    assert client.get(f"/api/v1/guild/me/leadership/applications/{created['id']}", headers=auth(vice)).status_code == 200
    assert client.patch(f"/api/v1/guild/me/leadership/applications/{created['id']}/status", json={"status": "under_review"}, headers=auth(leader)).status_code == 200
    assert client.patch(f"/api/v1/guild/me/leadership/applications/{created['id']}/status", json={"status": "voting"}, headers=auth(leader)).status_code == 200
    assert client.post(f"/api/v1/guild/me/leadership/applications/{created['id']}/votes", json={"vote": "support"}, headers=auth(vice)).status_code == 200
    assert client.post(f"/api/v1/guild/me/leadership/applications/{created['id']}/decision", json={"decision": "accepted"}, headers=auth(vice)).status_code == 403


def test_acceptance_creates_one_pending_assignment_and_preserves_history(client, db):
    leader, opening = setup_opening(client, db, guild="Accepted Guild")
    applicant = setup_applicant(db, guild="Accepted Guild", character="Accepted Knight")
    created = client.post(f"/api/v1/guild/me/leadership/openings/{opening['id']}/applications", json=application_payload("Accepted Knight"), headers=auth(applicant)).json()
    client.patch(f"/api/v1/guild/me/leadership/applications/{created['id']}/status", json={"status": "under_review"}, headers=auth(leader))
    client.patch(f"/api/v1/guild/me/leadership/applications/{created['id']}/status", json={"status": "voting"}, headers=auth(leader))
    client.post(f"/api/v1/guild/me/leadership/applications/{created['id']}/votes", json={"vote": "support"}, headers=auth(leader))
    accepted = client.post(f"/api/v1/guild/me/leadership/applications/{created['id']}/decision", json={"decision": "accepted"}, headers=auth(leader))
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"
    assignment = db.query(GuildLeadershipAssignment).filter_by(user_id=applicant.id, is_active=True).one()
    assert assignment.in_game_promotion_status == "pending"
    assert client.post(f"/api/v1/guild/me/leadership/applications/{created['id']}/decision", json={"decision": "accepted"}, headers=auth(leader)).status_code == 409
    db.refresh(db.get(GuildLeadershipApplication, created["id"])); assert len(db.get(GuildLeadershipApplication, created["id"]).histories) == 4


def test_admin_assistance_is_fixed_audited_and_does_not_change_membership(client, db):
    assisted = make_user(db, username="assisted-leader", guild_name="Assisted Leadership", guild_rank="Leader")
    link_verified(db, assisted, "Assisted Leadership", "Leader")
    admin = make_user(db, username="leadership-admin", guild_name="Admin Home", is_superuser=True); db.commit()
    response = client.post("/api/v1/admin/guilds/assisted-leadership/leadership/openings", json=opening_payload(), headers=auth(admin))
    assert response.status_code == 201
    db.refresh(admin); assert admin.guild_name == "Admin Home"
    audit = db.query(WorkspaceAudit).filter_by(actor_id=admin.id, action="leadership_opening_created").one()
    assert audit.guild_name == "Assisted Leadership" and audit.assisted is True


def test_notifications_are_private_and_legacy_table_is_untouched(client, db):
    leader, opening = setup_opening(client, db, guild="Notify Guild")
    applicant = setup_applicant(db, guild="Notify Guild", character="Notify Knight")
    member = make_user(db, username="notify-member", guild_name="Notify Guild", guild_rank="Member"); db.commit()
    client.post(f"/api/v1/guild/me/leadership/openings/{opening['id']}/applications", json=application_payload("Notify Knight"), headers=auth(applicant))
    recipients = {item.recipient_user_id for item in db.query(InternalNotification).filter(InternalNotification.notification_type == "leadership_application_received").all()}
    assert recipients == {leader.id} and member.id not in recipients
    assert db.bind.dialect.has_table(db.connection(), "recruitments")
