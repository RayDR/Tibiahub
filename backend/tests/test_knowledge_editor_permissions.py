from app.core.security import create_access_token
from app.models.creature import Creature
from app.models.hunt_zone import HuntZone
from app.models.workspace_audit import WorkspaceAudit
from tests.conftest import make_user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def _creature_payload(name: str):
    return {
        "name": name,
        "hitpoints": 100,
        "experience": 50,
        "description": "A locally managed test creature.",
    }


def _zone_payload(name: str):
    return {
        "name": name,
        "slug": name.casefold().replace(" ", "-"),
        "city": "Thais",
        "min_level": 20,
        "description": "A locally managed test hunt zone.",
    }


def test_global_knowledge_writes_require_writer_or_superuser(client, db):
    member = make_user(db, username="knowledge-member")
    writer = make_user(db, username="knowledge-writer")
    writer.is_writer = True
    admin = make_user(db, username="knowledge-admin", is_superuser=True)
    db.flush()

    assert client.post("/api/v1/creatures/", json=_creature_payload("Anonymous Beast")).status_code == 401
    assert client.post(
        "/api/v1/hunt-zones/",
        json=_zone_payload("Anonymous Grounds"),
    ).status_code == 401

    assert client.post(
        "/api/v1/creatures/",
        json=_creature_payload("Member Beast"),
        headers=_headers(member),
    ).status_code == 403
    assert client.post(
        "/api/v1/hunt-zones/",
        json=_zone_payload("Member Grounds"),
        headers=_headers(member),
    ).status_code == 403

    writer_creature = client.post(
        "/api/v1/creatures/",
        json=_creature_payload("Writer Beast"),
        headers=_headers(writer),
    )
    admin_zone = client.post(
        "/api/v1/hunt-zones/",
        json=_zone_payload("Admin Grounds"),
        headers=_headers(admin),
    )

    assert writer_creature.status_code == 201
    assert admin_zone.status_code == 201
    assert db.query(Creature).filter_by(name="Writer Beast").one()
    assert db.query(HuntZone).filter_by(name="Admin Grounds").one()

    creature_audit = db.query(WorkspaceAudit).filter_by(
        action="knowledge_creature_created",
        actor_id=writer.id,
    ).one()
    zone_audit = db.query(WorkspaceAudit).filter_by(
        action="knowledge_hunt_zone_created",
        actor_id=admin.id,
    ).one()
    assert creature_audit.safe_metadata == {"name": "Writer Beast"}
    assert zone_audit.safe_metadata == {"name": "Admin Grounds"}


def test_writer_can_create_hunt_zone_and_superuser_can_create_creature(client, db):
    writer = make_user(db, username="writer-second-path")
    writer.is_writer = True
    admin = make_user(db, username="admin-second-path", is_superuser=True)
    db.flush()

    zone = client.post(
        "/api/v1/hunt-zones/",
        json=_zone_payload("Writer Grounds"),
        headers=_headers(writer),
    )
    creature = client.post(
        "/api/v1/creatures/",
        json=_creature_payload("Admin Beast"),
        headers=_headers(admin),
    )

    assert zone.status_code == 201
    assert creature.status_code == 201


def test_public_knowledge_reads_remain_anonymous(client):
    assert client.get("/api/v1/creatures/").status_code == 200
    assert client.get("/api/v1/hunt-zones/").status_code == 200
