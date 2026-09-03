"""
zHash symmetry (zOS#41 gap 1) — the plaintext-on-update trap.

Before this fix, `zHash: bcrypt` hashed on INSERT only; the natural
change-password call — data.update("Users", {"password": new}, …) — silently
wrote PLAINTEXT to the store. The contract now under test:

  • apply_zhash_fields hashes zHash fields identically for any write verb
  • an already-bcrypt-shaped value passes through UNTOUCHED (a fetched-row
    re-write or a hand-hashed caller must never double-hash — a double-hashed
    digest verifies against nothing and locks the account)
  • hashing impossibility (no zAuth / hash failure) returns an error and the
    original payload — the caller must refuse the write, never store plaintext
  • the digest-recognition regex matches REAL bcrypt output (load-bearing)
"""

import sys
from pathlib import Path

import bcrypt
import pytest

CORE = Path(__file__).resolve().parents[1] / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from zOS.L3_Abstraction.m_zData.zData_modules.shared.operations.write_prep import (  # noqa: E402
    apply_zhash_fields, _BCRYPT_DIGEST_RE,
)


SCHEMA = {
    "username": {"type": "string"},
    "password": {"type": "string", "zHash": "bcrypt"},
}


class _Logger:
    def __init__(self):
        self.lines = []

    def _log(self, msg, *args):
        self.lines.append(msg % args if args else str(msg))

    debug = info = warning = error = _log


class _Auth:
    @staticmethod
    def hash_password(plain: str) -> str:
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=4)).decode()


class _Zos:
    auth = _Auth()


class _Ops:
    def __init__(self, with_auth=True):
        self.logger = _Logger()
        self.zos = _Zos() if with_auth else object()


def test_plaintext_is_hashed_and_verifies():
    data, err = apply_zhash_fields(
        "Users", {"username": "gal", "password": "hunter2"}, SCHEMA, _Ops())
    assert err is None
    assert data["password"] != "hunter2"
    assert _BCRYPT_DIGEST_RE.match(data["password"])
    assert bcrypt.checkpw(b"hunter2", data["password"].encode())
    assert data["username"] == "gal"  # non-zHash fields untouched


def test_already_hashed_value_is_not_double_hashed():
    digest = _Auth.hash_password("hunter2")
    data, err = apply_zhash_fields(
        "Users", {"password": digest}, SCHEMA, _Ops())
    assert err is None
    assert data["password"] == digest  # verbatim — still verifies
    assert bcrypt.checkpw(b"hunter2", data["password"].encode())


def test_real_bcrypt_digest_matches_recognition_regex():
    # The no-double-hash guard rests on this regex matching genuine output.
    for pw in ("a", "123456", "correct horse battery staple"):
        assert _BCRYPT_DIGEST_RE.match(_Auth.hash_password(pw))


def test_bcrypt_lookalikes_are_still_hashed():
    # Close-but-not-a-digest strings must be treated as plaintext.
    for value in ("$2b$12$tooshort", "$3b$12$" + "a" * 53, "hello$2b$12$"):
        data, err = apply_zhash_fields("Users", {"password": value}, SCHEMA, _Ops())
        assert err is None
        assert data["password"] != value
        assert bcrypt.checkpw(value.encode(), data["password"].encode())


def test_empty_values_pass_through():
    for value in (None, ""):
        data, err = apply_zhash_fields("Users", {"password": value}, SCHEMA, _Ops())
        assert err is None
        assert data["password"] == value  # required/min_length owns the reject


def test_missing_zauth_returns_error_and_original_payload():
    payload = {"password": "hunter2"}
    data, err = apply_zhash_fields("Users", payload, SCHEMA, _Ops(with_auth=False))
    assert err is not None and "zAuth" in err
    assert data == payload  # caller must refuse the write


def test_hash_failure_returns_error():
    class _BrokenAuth:
        @staticmethod
        def hash_password(_):
            raise RuntimeError("boom")

    ops = _Ops()
    ops.zos.auth = _BrokenAuth()
    data, err = apply_zhash_fields("Users", {"password": "x"}, SCHEMA, ops)
    assert err is not None and "boom" in err
    assert data == {"password": "x"}


def test_no_zhash_fields_is_a_noop():
    schema = {"name": {"type": "string"}}
    data, err = apply_zhash_fields("T", {"name": "plain"}, schema, _Ops())
    assert err is None
    assert data == {"name": "plain"}
