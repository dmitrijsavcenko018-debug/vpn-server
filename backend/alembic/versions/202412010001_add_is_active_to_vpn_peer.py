"""add is_active to vpn_peer

Revision ID: 202412010001
Revises: 202311260001
Create Date: 2024-12-01 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202412010001'
down_revision = '202311260001'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле is_active в таблицу vpn_peers
    op.add_column('vpn_peers', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))


def downgrade():
    # Удаляем поле is_active
    op.drop_column('vpn_peers', 'is_active')

