"""Isolated integration tests. Never point these at an existing patient database."""
import os
import secrets

# Import-time settings need a secret; this is a disposable random test secret.
os.environ.setdefault("JWT_SECRET_KEY", secrets.token_urlsafe(48))
