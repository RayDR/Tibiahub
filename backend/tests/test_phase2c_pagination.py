from datetime import UTC, datetime

from app.core.security import create_access_token
from app.knowledge.models import KnowledgeJob
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry, RelationshipTypeRegistry
from app.knowledge.schemas import KnowledgeEntityCreate
from app.knowledge.services import KnowledgeEntityService, KnowledgeGraphService, RelationshipInput
from app.models.guild_member_snapshot import GuildMemberSnapshot
from app.models.workspace_audit import WorkspaceAudit
from tests.conftest import make_user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def test_roster_users_and_guild_audits_expose_stable_windows(client, db):
    admin = make_user(db, username="phase2c-admin", is_superuser=True)
    member = make_user(db, username="phase2c-member")
    snapshot_at = datetime.now(UTC)
    db.add_all([
        GuildMemberSnapshot(
            guild_name="Phase Two",
            character_name=f"Member {index:03d}",
            level=500 - index,
            vocation="Knight",
            rank="Member",
            snapshot_at=snapshot_at,
        )
        for index in range(61)
    ])
    db.add(GuildMemberSnapshot(
        guild_name="Phase Two",
        character_name="Member 000",
        level=1,
        vocation="Rookie",
        rank="Member",
        snapshot_at=datetime(2020, 1, 1, tzinfo=UTC),
    ))
    db.add_all([
        WorkspaceAudit(
            actor_id=admin.id,
            workspace_type="admin_guild_assist",
            guild_name="Phase Two",
            action=f"audit_{index:03d}",
            target_type="member",
            target_id=str(index),
            assisted=True,
            safe_metadata={},
        )
        for index in range(45)
    ])
    for index in range(55):
        make_user(db, username=f"phase2c-user-{index:03d}")
    db.commit()

    first = client.get("/api/v1/guild/Phase Two/members", params={"skip": 0, "limit": 25}, headers=auth(admin))
    second = client.get("/api/v1/guild/Phase Two/members", params={"skip": 25, "limit": 25}, headers=auth(admin))
    assert first.status_code == second.status_code == 200
    assert first.json()["total"] == second.json()["total"] == 61
    assert len(first.json()["members"]) == len(second.json()["members"]) == 25
    assert {row["character_name"] for row in first.json()["members"]}.isdisjoint(
        {row["character_name"] for row in second.json()["members"]}
    )
    searched = client.get("/api/v1/guild/Phase Two/members", params={"search": "Member 060", "limit": 25}, headers=auth(admin))
    assert searched.json()["total"] == 1 and searched.json()["members"][0]["character_name"] == "Member 060"
    assert client.get("/api/v1/guild/Phase Two/members", params={"skip": -1}, headers=auth(admin)).status_code == 422

    user_first = client.get("/api/v1/guild-management/users", params={"skip": 0, "limit": 51, "include_inactive": True, "exclude_test_accounts": False}, headers=auth(admin))
    user_second = client.get("/api/v1/guild-management/users", params={"skip": 50, "limit": 51, "include_inactive": True, "exclude_test_accounts": False}, headers=auth(admin))
    assert len(user_first.json()) == 51 and len(user_second.json()) > 0
    assert {row["id"] for row in user_first.json()[:50]}.isdisjoint({row["id"] for row in user_second.json()[:50]})
    assert client.get("/api/v1/guild-management/users", headers=auth(member)).status_code == 403

    audits_first = client.get("/api/v1/admin/guilds/phase-two/audits", params={"skip": 0, "limit": 20, "paged": True}, headers=auth(admin))
    audits_last = client.get("/api/v1/admin/guilds/phase-two/audits", params={"skip": 40, "limit": 20, "paged": True}, headers=auth(admin))
    assert audits_first.json()["total"] == audits_last.json()["total"] == 45
    assert len(audits_first.json()["items"]) == 20 and len(audits_last.json()["items"]) == 5
    legacy = client.get("/api/v1/admin/guilds/phase-two/audits", headers=auth(admin))
    assert isinstance(legacy.json(), list) and len(legacy.json()) == 45
    assert client.get("/api/v1/admin/guilds/phase-two/audits", headers=auth(member)).status_code == 403


def test_knowledge_jobs_and_relationship_review_reach_beyond_fifty(client, db):
    EntityTypeRegistry.register_initial(db)
    ProviderRegistry.register_initial(db)
    RelationshipTypeRegistry.register_initial(db)
    admin = make_user(db, username="phase2c-knowledge-admin", is_superuser=True)
    source = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="quest",
        canonical_name="Phase 2C Quest",
        language_neutral_id="quest:phase-2c",
    ))
    for index in range(55):
        db.add(KnowledgeJob(
            provider_id="reference",
            job_type="reference_import",
            entity_type_id="creature",
            scope={},
            payload={},
            state="succeeded",
            idempotency_key=f"phase2c-job-{index:03d}",
            trigger="system",
            created_by_id=admin.id,
        ))
        KnowledgeGraphService.upsert(db, RelationshipInput(
            source_entity_id=source.uuid,
            relationship_type="requires_item",
            target_entity_type="item",
            unresolved_name=f"Unknown Item {index:03d}",
            resolution_state="unresolved",
            source_provider_id="reference",
            source_context={"reason": "phase2c pagination"},
        ))
    db.commit()
    headers = auth(admin)

    jobs_first = client.get("/api/v1/admin/knowledge/jobs", params={"skip": 0, "limit": 25}, headers=headers).json()
    jobs_last = client.get("/api/v1/admin/knowledge/jobs", params={"skip": 50, "limit": 25}, headers=headers).json()
    assert jobs_first["total"] == jobs_last["total"] == 55
    assert len(jobs_first["items"]) == 25 and len(jobs_last["items"]) == 5
    assert {row["id"] for row in jobs_first["items"]}.isdisjoint({row["id"] for row in jobs_last["items"]})

    review_first = client.get("/api/v1/admin/knowledge/relationships/review", params={"resolution_state": "unresolved", "skip": 0, "limit": 20}, headers=headers).json()
    review_last = client.get("/api/v1/admin/knowledge/relationships/review", params={"resolution_state": "unresolved", "skip": 40, "limit": 20}, headers=headers).json()
    assert review_first["total"] == review_last["total"] == 55
    assert len(review_first["items"]) == 20 and len(review_last["items"]) == 15
    assert {row["id"] for row in review_first["items"]}.isdisjoint({row["id"] for row in review_last["items"]})
    assert all(row["provider_id"] == "reference" and row["resolution_state"] == "unresolved" for row in review_last["items"])
