"""Bind readings to their device/session and make model windows idempotent."""
from alembic import op
import sqlalchemy as sa

revision = "4c9e7a10b321"
down_revision = "e489b65cfe50"
branch_labels = None
depends_on = None


def upgrade():
    # Fail visibly if existing rows violate these relationships; never reassign them.
    op.create_unique_constraint("uq_session_device_id", "monitoring_sessions", ["device_id", "id"])
    op.create_foreign_key("fk_reading_device_session", "readings", "monitoring_sessions", ["device_id", "session_id"], ["device_id", "id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_risk_score_window_model", "risk_scores", ["session_id", "model_registry_id", "data_window_end"])


def downgrade():
    op.drop_constraint("uq_risk_score_window_model", "risk_scores", type_="unique")
    op.drop_constraint("fk_reading_device_session", "readings", type_="foreignkey")
    op.drop_constraint("uq_session_device_id", "monitoring_sessions", type_="unique")
