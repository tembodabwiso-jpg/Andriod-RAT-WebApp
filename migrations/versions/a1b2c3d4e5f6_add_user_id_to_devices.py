"""add user_id to devices table

Revision ID: a1b2c3d4e5f6
Revises: 631ffc7f0d6a
Create Date: 2026-03-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '631ffc7f0d6a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'devices',
        sa.Column(
            'user_id',
            sa.String(length=40),
            sa.ForeignKey('users.id'),
            nullable=True
        )
    )
    op.create_index('ix_devices_user_id', 'devices', ['user_id'])


def downgrade():
    op.drop_index('ix_devices_user_id', table_name='devices')
    op.drop_column('devices', 'user_id')
