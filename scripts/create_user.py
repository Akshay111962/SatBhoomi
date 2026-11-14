r"""Administrative CLI script for creating SatBhoomi users.

Prompts interactively for credentials using hidden input (`getpass`).
Security Guardrails:
- Strictly refuses passwords from command-line arguments or environment variables.
- Enforces a minimum password length of 12 characters.
- Asks for password confirmation twice before hashing.
- Never prints passwords or password hashes to the console or logs.
- Refuses duplicate usernames.

PowerShell Usage:
    .venv\Scripts\python.exe scripts/create_user.py `
        --username admin --name "Branch Admin" --role admin
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from satbhoomi.api.auth.passwords import hash_password
from satbhoomi.db.models.user import User
from satbhoomi.db.session import SessionLocal

MIN_PASSWORD_LENGTH = 12
ALLOWED_ROLES = ("officer", "admin")


def create_user(
    *,
    username: str,
    name: str,
    role: str,
    session: Session | None = None,
    prompt_fn: Callable[[str], str] | None = None,
) -> int:
    """Create a new user with prompted password.

    Args:
        username: Unique login identifier.
        name: Full name of officer or administrator.
        role: User role ('officer' or 'admin').
        session: Optional SQLAlchemy session (defaults to SessionLocal()).
        prompt_fn: Optional password prompter (defaults to getpass.getpass).

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    clean_username = username.strip()
    clean_name = name.strip()
    clean_role = role.strip().lower()

    if not clean_username:
        print("Error: Username cannot be empty.", file=sys.stderr)
        return 1

    if not clean_name:
        print("Error: Display name cannot be empty.", file=sys.stderr)
        return 1

    if clean_role not in ALLOWED_ROLES:
        print(
            f"Error: Invalid role '{clean_role}'. Allowed roles: {list(ALLOWED_ROLES)}",
            file=sys.stderr,
        )
        return 1

    prompt = prompt_fn or getpass.getpass

    pwd1 = prompt(f"Enter password for '{clean_username}' (min {MIN_PASSWORD_LENGTH} chars): ")
    if len(pwd1) < MIN_PASSWORD_LENGTH:
        print(
            f"Error: Password must be at least {MIN_PASSWORD_LENGTH} characters long.",
            file=sys.stderr,
        )
        return 1

    pwd2 = prompt("Confirm password: ")
    if pwd1 != pwd2:
        print("Error: Passwords do not match.", file=sys.stderr)
        return 1

    db = session or SessionLocal()
    should_close = session is None

    try:
        existing = db.execute(
            select(User).where(User.username == clean_username)
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Error: Username '{clean_username}' already exists.", file=sys.stderr)
            return 1

        pwd_hash = hash_password(pwd1)

        user = User(
            username=clean_username,
            name=clean_name,
            role=clean_role,
            password_hash=pwd_hash,
            is_active=True,
            failed_login_count=0,
            locked_until=None,
            last_login_at=None,
            created_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()
        print(f"User '{clean_username}' created successfully with role '{clean_role}'.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Error: Failed to create user: {exc}", file=sys.stderr)
        return 1
    finally:
        if should_close:
            db.close()


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and invoke user creation."""
    parser = argparse.ArgumentParser(
        description="Create a new SatBhoomi system user with secure password prompt.",
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Unique alphanumeric login identifier (e.g. admin, officer_01)",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Full human-readable display name",
    )
    parser.add_argument(
        "--role",
        choices=ALLOWED_ROLES,
        default="officer",
        help="Role assigned to user (default: officer)",
    )

    args = parser.parse_args(argv)
    return create_user(
        username=args.username,
        name=args.name,
        role=args.role,
    )


if __name__ == "__main__":
    sys.exit(main())
