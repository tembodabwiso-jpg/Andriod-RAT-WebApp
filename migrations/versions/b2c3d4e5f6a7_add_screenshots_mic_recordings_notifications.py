"""add screenshots, mic_recordings, device_notifications tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-19 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'screenshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.String(255), sa.ForeignKey('devices.device_id'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_url', sa.String(512), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_screenshots_device_id', 'screenshots', ['device_id'])

    op.create_table(
        'mic_recordings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.String(255), sa.ForeignKey('devices.device_id'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_url', sa.String(512), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_mic_recordings_device_id', 'mic_recordings', ['device_id'])

    op.create_table(
        'device_notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.String(255), sa.ForeignKey('devices.device_id'), nullable=False),
        sa.Column('user_id', sa.String(40), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('message', sa.String(255), nullable=False),
        sa.Column('is_read', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_device_notifications_device_id', 'device_notifications', ['device_id'])
    op.create_index('ix_device_notifications_is_read', 'device_notifications', ['is_read'])


def downgrade():
    op.drop_index('ix_device_notifications_is_read', table_name='device_notifications')
    op.drop_index('ix_device_notifications_device_id', table_name='device_notifications')
    op.drop_table('device_notifications')

    op.drop_index('ix_mic_recordings_device_id', table_name='mic_recordings')
    op.drop_table('mic_recordings')

    op.drop_index('ix_screenshots_device_id', table_name='screenshots')
    op.drop_table('screenshots')
