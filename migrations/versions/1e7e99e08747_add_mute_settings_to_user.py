"""Add mute settings to User

Revision ID: 1e7e99e08747
Revises: 
Create Date: 2025-04-13 12:25:28.615064

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1e7e99e08747'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('group_member')
    op.drop_table('group_message')
    op.drop_table('chat_group')
    with op.batch_alter_table('private_message', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type', sa.String(length=50), nullable=True))

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mute_messages', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('mute_posts', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('mute_requests', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('mute_requests')
        batch_op.drop_column('mute_posts')
        batch_op.drop_column('mute_messages')

    with op.batch_alter_table('private_message', schema=None) as batch_op:
        batch_op.drop_column('type')

    op.create_table('chat_group',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('group_name', sa.VARCHAR(length=100), nullable=False),
    sa.Column('owner_id', sa.INTEGER(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('group_message',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('group_id', sa.INTEGER(), nullable=False),
    sa.Column('sender_id', sa.INTEGER(), nullable=False),
    sa.Column('message', sa.TEXT(), nullable=False),
    sa.Column('timestamp', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['chat_group.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('group_member',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('group_id', sa.INTEGER(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['chat_group.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###
