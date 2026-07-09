"""Regenerate Data/Users.csv with fresh bcrypt hashes.

zLogin verifies LOCALLY against the stored hash (15_rbac.md "automatic") — the
seed CSV is written with real bcrypt so the app's own zLogin path is what gets
exercised at runtime, not a separate seeding path. One password for both demo
accounts, kept here in the clear since this is throwaway demo data.

Run:  python3 zDemos/zTeamVault/seed_users.py
"""
import csv
import os

import bcrypt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "Data")
PASSWORD = "vault123"

# id, email, name, role
USERS = [
    (1, "admin@teamvault.io", "Ada Admin", "zAdmin"),
    (2, "member@teamvault.io", "Mo Member", "zMember"),
]


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def main():
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "Users.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "email", "password", "name", "role"])
        for uid, email, name, role in USERS:
            w.writerow([uid, email, _hash(PASSWORD), name, role])
    print(f"Seeded {len(USERS)} users into {DATA}")
    print(f"Login with admin@teamvault.io or member@teamvault.io  (password: {PASSWORD})")


if __name__ == "__main__":
    main()
