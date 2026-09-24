"""Bootstrap the very first Admin account.

Accounts are provisioned exclusively through `POST /users` (Manager/Admin
only, see app/api/users.py) from that point on — this script exists solely
to create the first Admin, since nobody can call that endpoint before one
exists. Safe to run more than once: it's a no-op if the email already
exists.

Usage:
    python -m app.scripts.seed_admin <email> <password>
"""
import sys

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def seed_admin(email: str, password: str) -> None:
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")

    email = email.strip().lower()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            print(f"User {email} already exists (role={existing.role.value}) — nothing to do.")
            return

        admin = User(email=email, hashed_password=hash_password(password), role=UserRole.ADMIN)
        db.add(admin)
        db.commit()
        print(f"Created admin account: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m app.scripts.seed_admin <email> <password>")
        sys.exit(1)
    seed_admin(sys.argv[1], sys.argv[2])
