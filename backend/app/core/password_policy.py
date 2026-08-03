"""Canonical password policy for every password-setting workflow."""

from __future__ import annotations


MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
PASSWORD_POLICY_ERROR = (
    "Password must be 8–128 characters and include at least one letter and one number. "
    "Spaces and symbols are allowed."
)


class PasswordPolicyError(ValueError):
    """Raised when a new password does not satisfy the product policy."""


def validate_password(password: str) -> str:
    """Validate a new password without normalizing or trimming meaningful text."""
    if not isinstance(password, str):
        raise PasswordPolicyError(PASSWORD_POLICY_ERROR)
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(PASSWORD_POLICY_ERROR)
    if not any(character.isalpha() for character in password):
        raise PasswordPolicyError(PASSWORD_POLICY_ERROR)
    if not any(character.isdecimal() for character in password):
        raise PasswordPolicyError(PASSWORD_POLICY_ERROR)
    return password
