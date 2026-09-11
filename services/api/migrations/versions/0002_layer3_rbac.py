"""Layer 3 (Week 6): identity/RBAC/audit schema (PRD 3.3, 4.4, 5.3).

Adds:
- users.display_name, users.is_active
- devices.bound_at
- coach_patient — resource-level RBAC grants (a coach may only reach a
  patient's data once a row exists here)
- refresh_tokens — makes logout/revocation possible for an otherwise
  stateless JWT
- audit_logs is recreated with the richer shape PRD 5.3 needs (actor_email,
  resource_type/resource_id, target_user_id, status, ip_address, detail).
  Dropped and recreated rather than ALTERed column-by-column: this table has
  never held real data (the api service predates this week's work), and the
  id column's type is changing (UUID -> BIGSERIAL) alongside several other
  columns, so an in-place ALTER would be more code for no benefit here. A
  service that already had real audit rows in production would instead
  ALTER + backfill in place — call that out explicitly if adapting this
  migration for a live table.

Revision ID: 0002_layer3_rbac
Revises: 0001_baseline
Create Date: 2026-09-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_layer3_rbac"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # server_default backfills every pre-existing row in the same statement,
    # so this NOT NULL column addition doesn't need a separate UPDATE pass.
    op.add_column(
        "devices",
        sa.Column(
            "bound_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "coach_patient",
        sa.Column("coach_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("jti", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.drop_table("audit_logs")
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_email", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("target_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="success"),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_target_user_id_created_at", "audit_logs", ["target_user_id", "created_at"])
    op.create_index("ix_audit_logs_actor_id_created_at", "audit_logs", ["actor_id", "created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])

    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("coach_patient")
    op.drop_column("devices", "bound_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "display_name")
