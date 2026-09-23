"""Tests for password hashing/verification primitives."""

from app.core.security import hash_password, verify_password


def test_hash_password_produces_a_hash() -> None:
    hashed = hash_password("StrongPass123")
    assert hashed
    assert hashed != "StrongPass123"


def test_hash_password_is_salted_per_call() -> None:
    assert hash_password("StrongPass123") != hash_password("StrongPass123")


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("StrongPass123")
    assert verify_password("StrongPass123", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("StrongPass123")
    assert verify_password("WrongPass999", hashed) is False