"""add expire_at to vpn_peer

Revision ID: 202412090001
Revises: 202412020001
Create Date: 2024-12-09 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202412090001'
down_revision = '202412020001'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле expire_at в таблицу vpn_peers
    op.add_column('vpn_peers', sa.Column('expire_at', sa.DateTime(), nullable=True))


def downgrade():
    # Удаляем поле expire_at
    op.drop_column('vpn_peers', 'expire_at')

