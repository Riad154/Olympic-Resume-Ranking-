#!/usr/bin/env python3
"""
One-time setup script to create the first admin user.

Usage:
    python -m resume_app.create_admin

Then follow the prompts to set the admin username and password.
"""

import getpass

from db import fresh_conn, create_user, _hash_password


def main():
    print("=" * 50)
    print("  HR Intelligence — Create First Admin User")
    print("=" * 50)

    conn = fresh_conn()

    # Check if any admin already exists
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        admin_count = cur.fetchone()[0]

    if admin_count > 0:
        print(f"\n[INFO] {admin_count} admin user(s) already exist.")
        print("This script is for first-time setup only.")
        print("Use the Admin Panel (pages/7_Admin.py) to create additional users.")
        return

    print("\nNo admin user found. Let's create the first one.\n")

    username = input("Username: ").strip()
    display = input("Display Name (optional): ").strip() or username
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm Password: ")

    if not username:
        print("[ERROR] Username is required.")
        return
    if len(password) < 6:
        print("[ERROR] Password must be at least 6 characters.")
        return
    if password != confirm:
        print("[ERROR] Passwords do not match.")
        return

    ok, msg = create_user(conn, username, password, display_name=display, role="admin")
    if ok:
        print(f"\n[SUCCESS] {msg}")
        print(f"\nYou can now log in at the Login page with:")
        print(f"  Username: {username}")
        print(f"  Password: (the one you just set)")
    else:
        print(f"\n[ERROR] {msg}")


if __name__ == "__main__":
    main()
