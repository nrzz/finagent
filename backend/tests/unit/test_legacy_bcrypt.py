"""Password hashes from before the Argon2 switch must keep verifying.

passlib 1.7.4 only works with bcrypt 4.0.x. bcrypt >= 4.1 removed ``__about__`` (noisy warning)
and bcrypt >= 5 rejects the 255-byte secret passlib hashes as a self-test the first time the
bcrypt backend is used, so every legacy hash then fails with "password cannot be longer than 72
bytes". New hashes use Argon2 and never load that backend, so only a test with a real bcrypt hash
notices; keep the ``bcrypt<4.1`` pin in pyproject.toml until passlib is replaced.
"""

from __future__ import annotations

import bcrypt

from finagent.api.auth import hash_password, needs_rehash, verify_password


def test_legacy_bcrypt_hash_still_verifies_and_is_flagged_for_rehash() -> None:
    legacy = bcrypt.hashpw(b"correct horse battery", bcrypt.gensalt(rounds=4)).decode()
    assert verify_password("correct horse battery", legacy) is True
    assert verify_password("wrong password", legacy) is False
    assert needs_rehash(legacy) is True


def test_new_hashes_are_argon2() -> None:
    fresh = hash_password("correct horse battery")
    assert fresh.startswith("$argon2")
    assert verify_password("correct horse battery", fresh) is True
    assert needs_rehash(fresh) is False
