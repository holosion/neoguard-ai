import getpass
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User


def main() -> None:
    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip().lower()
    password = getpass.getpass("Admin password (minimum 12 characters): ")
    if len(password) < 12:
        sys.exit("Password must be at least 12 characters.")
    with SessionLocal() as db:
        if db.scalar(select(User).where((User.username == username) | (User.email == email))):
            sys.exit("A user with that username or email already exists.")
        db.add(User(username=username, email=email, hashed_password=hash_password(password), role="admin"))
        db.commit()
    print("Admin account created.")


if __name__ == "__main__":
    main()
