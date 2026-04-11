"""lead_fields_calls_wallet_recharges

Revision ID: 20250411_0011
Revises: 20250410_0010
Create Date: 2026-04-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250411_0011"
down_revision: Union[str, Sequence[str], None] = "20250410_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── leads: new columns ──────────────────────────────────────────────────
    op.add_column("leads", sa.Column("phone", sa.String(length=20), nullable=True))
    op.add_column("leads", sa.Column("email", sa.String(length=320), nullable=True))
    op.add_column("leads", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("leads", sa.Column("source", sa.String(length=50), nullable=True))
    op.add_column("leads", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "leads",
        sa.Column("assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column(
            "call_status",
            sa.String(length=32),
            nullable=True,
            server_default=sa.text("'not_called'"),
        ),
    )
    op.add_column(
        "leads",
        sa.Column(
            "call_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "leads",
        sa.Column("last_called_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("whatsapp_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("payment_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("payment_amount_cents", sa.Integer(), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("payment_proof_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("payment_proof_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("day1_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("day2_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("day3_completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── call_events ─────────────────────────────────────────────────────────
    op.create_table(
        "call_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "called_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_call_events_lead_id", "call_events", ["lead_id"], unique=False)
    op.create_index("ix_call_events_user_id", "call_events", ["user_id"], unique=False)

    # ── wallet_recharges ─────────────────────────────────────────────────────
    op.create_table(
        "wallet_recharges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("utr_number", sa.String(length=50), nullable=True),
        sa.Column("proof_url", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("admin_note", sa.String(length=512), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_wallet_recharges_user_id", "wallet_recharges", ["user_id"], unique=False)
    op.create_index("ix_wallet_recharges_status", "wallet_recharges", ["status"], unique=False)

    # ── activity_log ─────────────────────────────────────────────────────────
    op.create_table(
        "activity_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_log_user_id", "activity_log", ["user_id"], unique=False)
    op.create_index(
        "ix_activity_log_created_at",
        "activity_log",
        ["created_at"],
        unique=False,
        postgresql_using="btree",
    )
    op.create_index(
        "ix_activity_log_entity",
        "activity_log",
        ["entity_type", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_activity_log_entity", table_name="activity_log")
    op.drop_index("ix_activity_log_created_at", table_name="activity_log", if_exists=True)
    op.drop_index("ix_activity_log_user_id", table_name="activity_log")
    op.drop_table("activity_log")

    op.drop_index("ix_wallet_recharges_status", table_name="wallet_recharges")
    op.drop_index("ix_wallet_recharges_user_id", table_name="wallet_recharges")
    op.drop_table("wallet_recharges")

    op.drop_index("ix_call_events_user_id", table_name="call_events")
    op.drop_index("ix_call_events_lead_id", table_name="call_events")
    op.drop_table("call_events")

    op.drop_column("leads", "day3_completed_at")
    op.drop_column("leads", "day2_completed_at")
    op.drop_column("leads", "day1_completed_at")
    op.drop_column("leads", "payment_proof_uploaded_at")
    op.drop_column("leads", "payment_proof_url")
    op.drop_column("leads", "payment_amount_cents")
    op.drop_column("leads", "payment_status")
    op.drop_column("leads", "whatsapp_sent_at")
    op.drop_column("leads", "last_called_at")
    op.drop_column("leads", "call_count")
    op.drop_column("leads", "call_status")
    op.drop_column("leads", "assigned_to_user_id")
    op.drop_column("leads", "notes")
    op.drop_column("leads", "source")
    op.drop_column("leads", "city")
    op.drop_column("leads", "email")
    op.drop_column("leads", "phone")
