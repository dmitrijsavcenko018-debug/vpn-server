"""add subscription_notifications table

Revision ID: 202412200001
Revises: 202412100001
Create Date: 2024-12-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '202412200001'
down_revision = '202412100001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'subscription_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_subscription_notifications_user_kind',
        'subscription_notifications',
        ['user_id', 'kind'],
        unique=False
    )
    op.create_index(
        'ix_subscription_notifications_subscription_kind',
        'subscription_notifications',
        ['subscription_id', 'kind'],
        unique=False
    )
    # Уникальность: одно уведомление каждого типа на подписку (если subscription_id есть)
    op.create_index(
        'uq_subscription_notifications_sub_kind',
        'subscription_notifications',
        ['subscription_id', 'kind'],
        unique=True,
        postgresql_where=sa.text('subscription_id IS NOT NULL')
    )


def downgrade():
    op.drop_index('uq_subscription_notifications_sub_kind', table_name='subscription_notifications')
    op.drop_index('ix_subscription_notifications_subscription_kind', table_name='subscription_notifications')
    op.drop_index('ix_subscription_notifications_user_kind', table_name='subscription_notifications')
    op.drop_table('subscription_notifications')
