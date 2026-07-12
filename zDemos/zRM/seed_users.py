"""Regenerate Data/Users.csv with fresh bcrypt hashes.

Same pairing as zTeamVault/seed_users.py (15_rbac.md "automatic") — the seed
CSV carries a real bcrypt hash so zLogin's own local-verify path is what gets
exercised at runtime, not a separate seeding path. One password for both demo
accounts, kept here in the clear since this is throwaway demo data.

Run:  python3 zDemos/zRM/seed_users.py
"""
import csv
import os

import bcrypt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "Data")
PASSWORD = "blog1234"

# id, email, name — avatar left blank so the schema default (default.png) fills in
USERS = [
    (1, "ada@zrm.io", "Ada"),
    (2, "grace@zrm.io", "Grace"),
]


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def main():
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "Users.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "email", "password", "name", "avatar"])
        for uid, email, name in USERS:
            w.writerow([uid, email, _hash(PASSWORD), name, "@.static.avatars.default.png"])
    print(f"Seeded {len(USERS)} users into {DATA}")
    print(f"Login with ada@zrm.io or grace@zrm.io  (password: {PASSWORD})")


if __name__ == "__main__":
    main()
