"""Payment system production - Razorpay integration

Revision ID: 20260412_0021
Revises: 20260413_0020
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260412_0021'
down_revision = '20260413_0020'
branch_labels = None
depends_on = None


def _ensure_payment_status_enum() -> None:
    """Idempotent: Render/Postgres may already have this type from a partial or retried migration."""
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE payment_status AS ENUM (
                'initiated', 'success', 'failed', 'verified', 'refunded', 'disputed'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def upgrade():
    _ensure_payment_status_enum()

    payment_status_type = postgresql.ENUM(
        "initiated",
        "success",
        "failed",
        "verified",
        "refunded",
        "disputed",
        name="payment_status",
        create_type=False,
    )

    # Payment table - immutable source of truth
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('razorpay_order_id', sa.String(255), nullable=False),
        sa.Column('razorpay_payment_id', sa.String(255), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
        sa.Column('status', payment_status_type, nullable=False),
        sa.Column('gateway_response', postgresql.JSONB(), nullable=True),
        sa.Column('webhook_payload', postgresql.JSONB(), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('idempotency_key', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    
    # Indexes for performance
    op.create_index('idx_payments_lead_id', 'payments', ['lead_id'])
    op.create_index('idx_payments_user_id', 'payments', ['user_id'])
    op.create_index('idx_payments_status', 'payments', ['status'])
    op.create_index('idx_payments_order_id', 'payments', ['razorpay_order_id'])
    op.create_index('idx_payments_payment_id', 'payments', ['razorpay_payment_id'], unique=True)
    op.create_index('idx_payments_created_at', 'payments', ['created_at'])
    op.create_index('idx_payments_idempotency', 'payments', ['idempotency_key'], unique=True)
    
    # Partial unique index: prevent duplicate active payments for same lead
    op.execute("""
        CREATE UNIQUE INDEX idx_payments_active_lead_guard 
        ON payments (lead_id) 
        WHERE status IN ('initiated', 'success', 'verified')
    """)
    
    # Add webhook events log table (for debugging and replay)
    op.create_table(
        'payment_webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_id', sa.String(255), nullable=False, unique=True),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payments.id'), nullable=True),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('signature_valid', sa.Boolean(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    
    op.create_index('idx_webhook_events_payment', 'payment_webhook_events', ['payment_id'])
    op.create_index('idx_webhook_events_event_id', 'payment_webhook_events', ['event_id'], unique=True)
    op.create_index('idx_webhook_events_processed', 'payment_webhook_events', ['processed'])


def downgrade():
    op.drop_table('payment_webhook_events')
    op.drop_table('payments')
    op.execute('DROP TYPE IF EXISTS payment_status')
