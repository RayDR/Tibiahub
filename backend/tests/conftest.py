"""
Shared pytest fixtures for TibiaHub backend tests.
Uses an in-memory SQLite database — nothing touches the production DB.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Use in-memory SQLite for all tests
TEST_DATABASE_URL = "sqlite:///:memory:"

from app.db.database import Base
import app.models  # noqa: F401 — ensure all models are registered


@pytest.fixture(scope="session")
def engine():
    _engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    _engine.dispose()


@pytest.fixture(scope="function")
def db(engine):
    """Fresh session per test, rolls back at end."""
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection)
    session: Session = TestSession()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient with overridden DB session."""
    from main import app
    from app.db.database import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def make_user(db: Session, *, username: str = "testuser", guild_rank: str = "Member", is_superuser: bool = False, guild_name: str = "TEST GUILD") -> "app.models.user.User":
    from app.models.user import User
    from app.core.security import get_password_hash
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=get_password_hash("password"),
        guild_rank=guild_rank,
        guild_name=guild_name,
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.flush()
    return user


def make_raffle(
    db: Session,
    *,
    title: str = "Test Raffle",
    guild_name: str = "TEST GUILD",
    creator_id: int,
    access_mode: str = "guild_only",
    show_participants: bool = True,
    status: str = "open",
) -> "app.models.raffle.Raffle":
    from app.models.raffle import Raffle
    from app.services.public_code import generate_unique_code
    raffle = Raffle(
        title=title,
        guild_name=guild_name,
        public_code=generate_unique_code(db, Raffle),
        access_mode=access_mode,
        show_participants=show_participants,
        visibility="private" if access_mode == "guild_only" else "public",
        registration_enabled=status == "open",
        run_mode="manual",
        archive_after_days=7,
        status=status,
        created_by_id=creator_id,
        is_active=status in {"draft", "open", "closed", "completed"},
    )
    db.add(raffle)
    db.flush()
    return raffle


def make_prize(db: Session, *, raffle_id: int, name: str = "1st Prize", reward: str = "10kk", order_index: int = 1) -> "app.models.raffle.RafflePrize":
    from app.models.raffle import RafflePrize
    prize = RafflePrize(raffle_id=raffle_id, name=name, reward=reward, order_index=order_index)
    db.add(prize)
    db.flush()
    return prize


def make_participant(db: Session, *, raffle_id: int, user_id: int, character_name: str, guild_rank: str = "Member", weight: float = 1.0) -> "app.models.raffle.RaffleParticipant":
    from app.models.raffle import RaffleParticipant
    participant = RaffleParticipant(
        raffle_id=raffle_id,
        user_id=user_id,
        character_name=character_name,
        guild_rank=guild_rank,
        weight=weight,
        weight_multiplier=1.0,
        is_eligible=True,
        source="manual_override",
    )
    db.add(participant)
    db.flush()
    return participant
