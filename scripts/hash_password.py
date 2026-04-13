#!/usr/bin/env python3
"""
Generate a SHA-256 password hash for use in index.html USERS config.
Usage: python scripts/hash_password.py
"""
import getpass
import hashlib
import json
import sys

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def main():
    print("Tech Vigilance — Password Hash Generator")
    print("─" * 40)
    username = input("Username: ").strip()
    if not username:
        sys.exit("Username cannot be empty.")
    password = getpass.getpass("Password: ")
    if not password:
        sys.exit("Password cannot be empty.")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        sys.exit("Passwords do not match.")

    h = sha256(password)
    entry = {"username": username, "hash": h}

    print("\nAdd this entry to the USERS array in index.html:\n")
    print(json.dumps(entry, indent=2))
    print(f"\nFull hash: {h}")

if __name__ == "__main__":
    main()
