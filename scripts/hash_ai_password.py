#!/usr/bin/env python3
"""Print an AI_PASSWORD_HASH value. Nothing is written to disk."""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_agent import password_digest

import bcrypt


def main() -> None:
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm: ")
    if not password or password != confirm:
        print("Passwords did not match.", file=sys.stderr)
        sys.exit(1)
    if len(password) < 12:
        print("Use at least 12 characters.", file=sys.stderr)
        sys.exit(1)
    hashed = bcrypt.hashpw(password_digest(password), bcrypt.gensalt())
    print(hashed.decode())


if __name__ == "__main__":
    main()
