"""add reminder_3days_sent to subscription

Revision ID: 202412100001
Revises: 202412090001
Create Date: 2024-12-10 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202412100001'
down_revision = '202412090001'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле reminder_3days_sent в таблицу subscriptions
    op.add_column('subscriptions', sa.Column('reminder_3days_sent', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # Удаляем поле reminder_3days_sent
    op.drop_column('subscriptions', 'reminder_3days_sent')

