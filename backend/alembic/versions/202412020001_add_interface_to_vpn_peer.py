"""add interface to vpn_peer

Revision ID: 202412020001
Revises: 202412010001
Create Date: 2024-12-02 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202412020001'
down_revision = '202412010001'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле interface в таблицу vpn_peers
    op.add_column('vpn_peers', sa.Column('interface', sa.String(length=10), nullable=False, server_default='wg0'))


def downgrade():
    # Удаляем поле interface
    op.drop_column('vpn_peers', 'interface')

