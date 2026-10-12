"""Add clinic scoping and staff access requests.

Revision ID: 6ad430c12e8b
Revises: 4c9e7a10b321
"""
from alembic import op
import sqlalchemy as sa


revision = "6ad430c12e8b"
down_revision = "4c9e7a10b321"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint("ck_threshold_nonnegative", "thresholds", "value >= 0")
    op.create_table(
        "clinics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute(sa.text("INSERT INTO clinics (id, name, code, is_active) VALUES (1, 'Default Clinic', 'DEFAULT', true)"))
    op.execute(sa.text("SELECT setval(pg_get_serial_sequence('clinics', 'id'), (SELECT MAX(id) FROM clinics))"))

    op.add_column("users", sa.Column("clinic_id", sa.Integer(), nullable=True))
    op.add_column("patients", sa.Column("clinic_id", sa.Integer(), nullable=True))
    op.add_column("devices", sa.Column("clinic_id", sa.Integer(), nullable=True))
    op.add_column("monitoring_sessions", sa.Column("clinic_id", sa.Integer(), nullable=True))
    op.execute(sa.text("UPDATE users SET clinic_id = 1 WHERE role <> 'admin'"))
    op.execute(sa.text("UPDATE patients SET clinic_id = 1"))
    op.execute(sa.text("UPDATE devices SET clinic_id = 1"))
    op.execute(sa.text("UPDATE monitoring_sessions SET clinic_id = 1"))

    op.alter_column("patients", "clinic_id", nullable=False)
    op.alter_column("devices", "clinic_id", nullable=False)
    op.alter_column("monitoring_sessions", "clinic_id", nullable=False)
    op.create_foreign_key("fk_users_clinic", "users", "clinics", ["clinic_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_patients_clinic", "patients", "clinics", ["clinic_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_devices_clinic", "devices", "clinics", ["clinic_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_sessions_clinic", "monitoring_sessions", "clinics", ["clinic_id"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint("ck_staff_user_clinic", "users", "role = 'admin' OR clinic_id IS NOT NULL")
    op.create_unique_constraint("uq_patient_clinic_id", "patients", ["clinic_id", "id"])
    op.create_unique_constraint("uq_device_clinic_id", "devices", ["clinic_id", "id"])
    op.create_foreign_key("fk_session_patient_clinic", "monitoring_sessions", "patients", ["clinic_id", "patient_id"], ["clinic_id", "id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_session_device_clinic", "monitoring_sessions", "devices", ["clinic_id", "device_id"], ["clinic_id", "id"], ondelete="RESTRICT")
    for table in ("users", "patients", "devices", "monitoring_sessions"):
        op.create_index(f"ix_{table}_clinic_id", table, ["clinic_id"], unique=False)

    op.create_unique_constraint("uq_device_component_device_id", "device_components", ["device_id", "id"])
    op.drop_constraint(op.f("component_health_logs_component_id_fkey"), "component_health_logs", type_="foreignkey")
    op.create_foreign_key(
        "fk_component_log_device_component", "component_health_logs", "device_components",
        ["device_id", "component_id"], ["device_id", "id"], ondelete="CASCADE",
    )

    op.create_table(
        "access_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(120), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('nurse', 'clinician')", name="ck_access_request_role"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_access_request_status"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("username", "email", "clinic_id", "status", "created_at"):
        op.create_index(f"ix_access_requests_{column}", "access_requests", [column], unique=False)
    op.create_index("uq_pending_access_username", "access_requests", [sa.text("lower(username)")], unique=True, postgresql_where=sa.text("status = 'pending'"))
    op.create_index("uq_pending_access_email", "access_requests", [sa.text("lower(email)")], unique=True, postgresql_where=sa.text("status = 'pending'"))


def downgrade() -> None:
    op.drop_table("access_requests")
    op.drop_constraint("ck_threshold_nonnegative", "thresholds", type_="check")
    op.drop_constraint("fk_component_log_device_component", "component_health_logs", type_="foreignkey")
    op.create_foreign_key(op.f("component_health_logs_component_id_fkey"), "component_health_logs", "device_components", ["component_id"], ["id"], ondelete="CASCADE")
    op.drop_constraint("uq_device_component_device_id", "device_components", type_="unique")
    op.drop_index("ix_monitoring_sessions_clinic_id", table_name="monitoring_sessions")
    op.drop_index("ix_devices_clinic_id", table_name="devices")
    op.drop_index("ix_patients_clinic_id", table_name="patients")
    op.drop_index("ix_users_clinic_id", table_name="users")
    op.drop_constraint("fk_session_device_clinic", "monitoring_sessions", type_="foreignkey")
    op.drop_constraint("fk_session_patient_clinic", "monitoring_sessions", type_="foreignkey")
    op.drop_constraint("uq_device_clinic_id", "devices", type_="unique")
    op.drop_constraint("uq_patient_clinic_id", "patients", type_="unique")
    op.drop_constraint("ck_staff_user_clinic", "users", type_="check")
    for name, table in (("fk_sessions_clinic", "monitoring_sessions"), ("fk_devices_clinic", "devices"), ("fk_patients_clinic", "patients"), ("fk_users_clinic", "users")):
        op.drop_constraint(name, table, type_="foreignkey")
    for table in ("monitoring_sessions", "devices", "patients", "users"):
        op.drop_column(table, "clinic_id")
    op.drop_table("clinics")
