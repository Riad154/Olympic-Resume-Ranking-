"""
reset_password.py — Standalone script to reset any user's password.

Usage:
    python scripts/reset_password.py <username> <new_password>

Example:
    python scripts/reset_password.py admin MyNewPass123
"""

import sys
import os
from pathlib import Path

# Load .env if present
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key, val)

import psycopg2
import bcrypt


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def main():
    if len(sys.argv) != 3:
        print("Usage: python reset_password.py <username> <new_password>")
        print("Example: python reset_password.py admin MyNewPass123")
        sys.exit(1)

    username = sys.argv[1]
    new_password = sys.argv[2]

    if len(new_password) < 6:
        print("Error: Password must be at least 6 characters.")
        sys.exit(1)

    host = os.environ.get("PG_HOST", "localhost")
    port = int(os.environ.get("PG_PORT", "5432"))
    dbname = os.environ.get("PG_DBNAME", "resume_ranking")
    user = os.environ.get("PG_USER", "postgres")
    password = os.environ.get("PG_PASSWORD", "")

    try:
        conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE username = %s",
                (_hash_password(new_password), username),
            )
            if cur.rowcount == 0:
                print(f"Error: User '{username}' not found.")
                sys.exit(1)
        conn.close()
        print(f"Success: Password for '{username}' has been reset.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
