import getpass
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Threshold, User

INITIAL_THRESHOLDS = (
    ("temp_low", 36.5, "°C"),
    ("temp_moderate_low", 36.0, "°C"),
    ("temp_severe_low", 32.0, "°C"),
    ("spo2_low", 90, "%"),
    ("hr_low", 100, "bpm"),
    ("hr_high", 160, "bpm"),
)


def main() -> None:
    username = settings.bootstrap_admin_username or input("Admin username: ").strip()
    email = settings.bootstrap_admin_email or input("Admin email: ").strip().lower()
    password = settings.bootstrap_admin_password
    if password is None:
        password = getpass.getpass("Admin password (minimum 12 characters): ")
        if len(password) < 12:
            sys.exit("Password must be at least 12 characters.")
    elif len(password) < 12:
        print("Warning: configured bootstrap password is shorter than the recommended 12 characters.")
    with SessionLocal() as db:
        if db.scalar(select(User).where((User.username == username) | (User.email == email))):
            print("A user with that username or email already exists; no changes made.")
            return
        db.add(User(username=username, email=email, hashed_password=hash_password(password), role="admin"))
        for parameter, value, unit in INITIAL_THRESHOLDS:
            if db.scalar(select(Threshold).where(Threshold.parameter == parameter, Threshold.is_active.is_(True))) is None:
                db.add(
                    Threshold(
                        parameter=parameter,
                        value=value,
                        unit=unit,
                        version=1,
                        source="Project note default; clinical review required before care use",
                        description="Provisional prototype alert threshold.",
                        is_active=True,
                    )
                )
        db.commit()
    print("Admin account and provisional threshold defaults created.")


if __name__ == "__main__":
    main()
