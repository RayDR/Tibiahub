from __future__ import annotations

from pathlib import Path

import bcrypt
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.password_reset import PasswordResetConfirm
from app.core.password_policy import PASSWORD_POLICY_ERROR, PasswordPolicyError, validate_password
from app.core.security import get_password_hash, verify_password
from app.db.database import Base
from app.models.user import User
from app.schemas.admin import UserUpdate
from app.schemas.auth import UserCreate
from app.schemas.profile import ProfileUpdate
from app.services.admin_user_service import recover_administrator


@pytest.mark.parametrize("password", [
    "letters7!",
    "a long passphrase with spaces and 2026",
    "  leading and trailing spaces 8  ",
    "symbols-are_fine!9",
    "contraseña2026",
    "Mi frase segura 2026",
    "Árbol seguro 42",
    "Contraseña١٢٣",
])
def test_canonical_password_policy_accepts_supported_passwords(password):
    assert validate_password(password) == password


@pytest.mark.parametrize("password", [
    "short7",
    "á2",
    "letters only",
    "contraseña",
    "12345678",
    "١٢٣٤٥٦٧٨",
    "a" * 128 + "7",
])
def test_canonical_password_policy_rejects_invalid_passwords(password):
    with pytest.raises(PasswordPolicyError, match="8–128"):
        validate_password(password)


@pytest.mark.parametrize("build", [
    lambda password: UserCreate(username="policy-user", email="policy@example.com", password=password),
    lambda password: ProfileUpdate(new_password=password),
    lambda password: PasswordResetConfirm(token="t" * 32, new_password=password),
    lambda password: UserUpdate(password=password),
])
def test_all_password_setting_schemas_use_the_same_policy(build):
    preserved = "  phrase with spaces 42  "
    assert preserved in build(preserved).model_dump().values()
    with pytest.raises(ValidationError) as error:
        build("letters only")
    assert PASSWORD_POLICY_ERROR in str(error.value)


def test_new_hashes_use_argon2_and_legacy_bcrypt_still_verifies():
    password = "compatible password 7"
    modern = get_password_hash(password)
    legacy = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    assert modern.startswith("$argon2")
    assert verify_password(password, modern)
    assert verify_password(password, legacy)


def test_recovery_password_persists_and_verifies_in_a_fresh_session(tmp_path: Path):
    database_path = tmp_path / "recovery-test.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    original_password = "old password 1"
    recovered_password = "  recovered passphrase 2026  "
    with factory.begin() as session:
        session.add(User(
            username="recovery-admin", email="recovery-admin@example.test",
            hashed_password=get_password_hash(original_password),
            is_active=False, is_superuser=False,
        ))
    with factory.begin() as session:
        recover_administrator(
            session, identifier="recovery-admin", password=recovered_password,
        )
    with factory() as fresh_session:
        persisted = fresh_session.query(User).filter_by(username="recovery-admin").one()
        assert persisted.is_active is True
        assert persisted.is_superuser is True
        assert verify_password(recovered_password, persisted.hashed_password)
        assert not verify_password(original_password, persisted.hashed_password)
    engine.dispose()
