import getpass
import re

from sqlalchemy import select

from backend.auth_security import hash_password
from backend.database import SessionLocal, create_database
from backend.models import AuditLog, User


USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")


def main():
    create_database()
    database = SessionLocal()

    try:
        existing_admin = database.scalar(
            select(User).where(User.role == "admin")
        )

        if existing_admin is not None:
            print(
                "An administrator already exists. "
                "Use the admin API to create additional users."
            )
            return

        username = input("Administrator username: ").strip().lower()

        if (
            len(username) < 3
            or len(username) > 100
            or not USERNAME_PATTERN.fullmatch(username)
        ):
            print(
                "Username must be 3-100 characters and use only "
                "letters, numbers, periods, underscores, or hyphens."
            )
            return

        password = getpass.getpass(
            "Administrator password (12+ characters): "
        )

        if len(password) < 12:
            print("Password must contain at least 12 characters.")
            return

        password_confirmation = getpass.getpass(
            "Confirm administrator password: "
        )

        if password != password_confirmation:
            print("Passwords do not match.")
            return

        administrator = User(
            username=username,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )

        database.add(administrator)
        database.flush()

        database.add(
            AuditLog(
                user_id=administrator.id,
                action="user.bootstrap_admin_created",
                resource_type="user",
                resource_id=str(administrator.id),
                details={
                    "username": administrator.username,
                    "role": administrator.role,
                },
                source_ip="localhost",
            )
        )

        database.commit()

        print("")
        print("Watchtower administrator created successfully.")
        print(f"Username: {administrator.username}")
    except Exception:
        database.rollback()
        raise
    finally:
        database.close()


if __name__ == "__main__":
    main()