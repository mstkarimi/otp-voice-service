import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def test_hash_and_verify():
    plain = "my-super-secret-api-key"
    hashed = _pwd_context.hash(plain)
    assert _pwd_context.verify(plain, hashed)


def test_wrong_key_fails():
    hashed = _pwd_context.hash("correct-key")
    assert not _pwd_context.verify("wrong-key", hashed)


def test_empty_key_fails():
    hashed = _pwd_context.hash("correct-key")
    assert not _pwd_context.verify("", hashed)
