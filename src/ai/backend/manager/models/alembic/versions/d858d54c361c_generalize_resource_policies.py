"""generalize_resource_policies

Revision ID: d858d54c361c
Revises: ce209920f654
Create Date: 2020-01-04 11:46:42.131535

"""
from datetime import datetime
import textwrap
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pgsql
from ai.backend.common.types import DefaultForUnspecified
from ai.backend.manager.models.base import convention, EnumType, IDColumn, ResourceSlotColumn

# revision identifiers, used by Alembic.
revision = 'd858d54c361c'
down_revision = 'ce209920f654'
branch_labels = None
depends_on = None


metadata = sa.MetaData(naming_convention=convention)
domains = sa.Table(
    'domains', metadata,
    sa.Column('name', sa.String(length=64), primary_key=True),
    sa.Column('total_resource_slots', ResourceSlotColumn(), default='{}'),
    sa.Column('allowed_vfolder_hosts', pgsql.ARRAY(sa.String), default='{}'),
    sa.Column('allowed_docker_registries', pgsql.ARRAY(sa.String), default='{}'),
    sa.Column('resource_policy', sa.String(length=256), nullable=True),
)
groups = sa.Table(
    'groups', metadata,
    IDColumn('id'),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('total_resource_slots', ResourceSlotColumn(), default='{}'),
    sa.Column('allowed_vfolder_hosts', pgsql.ARRAY(sa.String), default='{}'),
    sa.Column('resource_policy', sa.String(length=256), nullable=True),
)
keypair_resource_policies = sa.Table(
    'keypair_resource_policies', metadata,
    sa.Column('name', sa.String(length=256), primary_key=True),
    sa.Column('created_at', sa.DateTime(timezone=True),
              server_default=sa.func.now()),
    sa.Column('default_for_unspecified',
              EnumType(DefaultForUnspecified),
              default=DefaultForUnspecified.LIMITED,
              nullable=False),
    sa.Column('total_resource_slots', ResourceSlotColumn(), nullable=False),
    sa.Column('max_concurrent_sessions', sa.Integer(), nullable=False),
    sa.Column('max_containers_per_session', sa.Integer(), nullable=False),
    sa.Column('max_vfolder_count', sa.Integer(), nullable=False),
    sa.Column('max_vfolder_size', sa.BigInteger(), nullable=False),
    sa.Column('idle_timeout', sa.BigInteger(), nullable=False),
    sa.Column('allowed_vfolder_hosts', pgsql.ARRAY(sa.String), nullable=False),
    sa.Column('allowed_docker_registries', pgsql.ARRAY(sa.String), default='{}'),
)



def upgrade():
    conn = op.get_bind()

    # ### Add `allowed_docker_registries` to `resource_policies`.
    op.add_column('keypair_resource_policies',
                  sa.Column('allowed_docker_registries', pgsql.ARRAY(sa.String()), nullable=True))
    allowed_registries = '{index.docker.io}'
    query = ("UPDATE keypair_resource_policies SET allowed_docker_registries = '{}';".format(allowed_registries))
    conn.execute(query)
    op.alter_column('keypair_resource_policies', column_name='allowed_docker_registries', nullable=False)
    print('allowed_docker_registries field is added to keypair_resource_policies.')
    print('- Default docker registry (index.docker.io) is automatically set.')

    # ### Domain's resource policy.
    # Add `resource_policy` to `domains`.
    op.add_column('domains', sa.Column('resource_policy', sa.String(length=256), nullable=True, index=True))
    op.create_foreign_key(
        op.f('fk_domains_resource_policy_keypair_resource_policies'),
        'domains', 'keypair_resource_policies',
        ['resource_policy'], ['name'])
    # Auto-generate domain's resource policy.
    query = sa.select([
        domains.c.name,
        domains.c.total_resource_slots,
        domains.c.allowed_vfolder_hosts,
        domains.c.allowed_docker_registries
    ]).select_from(domains)
    for domain in conn.execute(query).fetchall():
        if not domain.total_resource_slots and not domain.allowed_vfolder_hosts \
                and not domain.allowed_docker_registries:
            continue
        policy_name = f'_auto_generated_domain_policy_{domain.name}'
        data = {
            'name': policy_name,
            'default_for_unspecified': DefaultForUnspecified.UNLIMITED,
            'total_resource_slots': domain.total_resource_slots,
            'max_concurrent_sessions': 30,
            'max_containers_per_session': 1,
            'max_vfolder_count': 10,
            'max_vfolder_size': 0,
            'idle_timeout': 0,
            'allowed_vfolder_hosts': domain.allowed_vfolder_hosts,
            'allowed_docker_registries': domain.allowed_docker_registries,
        }
        query = (keypair_resource_policies.insert().values(data))
        conn.execute(query)
        query = (domains.update()
                        .values(resource_policy=policy_name)
                        .where(domains.c.name == domain.name))
        conn.execute(query)
    # Drop deprecated fields.
    op.drop_column('domains', 'total_resource_slots')
    op.drop_column('domains', 'allowed_vfolder_hosts')
    op.drop_column('domains', 'allowed_docker_registries')
    print('resource_policy field is added to domains.')
    print('- domains\' resource data, if exists, is migrated into auto-generated resource policy.')
    print('- domains\' resource fields are dropped.')

    # ### Add `resource_policy` to `groups`.
    # Add `resource_policy` to `groups`.
    op.add_column('groups', sa.Column('resource_policy', sa.String(length=256), nullable=True, index=True))
    op.create_foreign_key(
        op.f('fk_groups_resource_policy_keypair_resource_policies'),
        'groups', 'keypair_resource_policies',
        ['resource_policy'], ['name'])
    # Auto-generate group's resource policy.
    query = sa.select([
        groups.c.id,
        groups.c.name,
        groups.c.total_resource_slots,
        groups.c.allowed_vfolder_hosts,
    ]).select_from(groups)
    for group in conn.execute(query).fetchall():
        if not group.total_resource_slots and not group.allowed_vfolder_hosts:
            continue
        policy_name = f'_auto_generated_group_policy_{group.name}_{group.id}'
        data = {
            'name': policy_name,
            'default_for_unspecified': DefaultForUnspecified.UNLIMITED,
            'total_resource_slots': group.total_resource_slots,
            'max_concurrent_sessions': 30,
            'max_containers_per_session': 1,
            'max_vfolder_count': 10,
            'max_vfolder_size': 0,
            'idle_timeout': 0,
            'allowed_vfolder_hosts': group.allowed_vfolder_hosts,
            'allowed_docker_registries': '',
        }
        query = (keypair_resource_policies.insert().values(data))
        conn.execute(query)
        query = (groups.update()
                       .values(resource_policy=policy_name)
                       .where(groups.c.id == group.id))
        conn.execute(query)
    # Drop deprecated fields.
    op.drop_column('groups', 'total_resource_slots')
    op.drop_column('groups', 'allowed_vfolder_hosts')
    print('resource_policy field is added to domains.')
    print('- domains\' resource data, if exists, is migrated into auto-generated resource policy.')
    print('- domains\' resource fields are dropped.')


def downgrade():
    conn = op.get_bind()

    # ### Drop `resource_policy` from `groups`.
    # Add deprecated fields.
    op.add_column('groups', sa.Column('total_resource_slots', ResourceSlotColumn(), default='{}'))
    op.add_column('groups', sa.Column('allowed_vfolder_hosts', pgsql.ARRAY(sa.String), default='{}'))
    # Update deprecated fields from resource policies.
    query = sa.select([
        groups.c.id,
        groups.c.name,
        groups.c.resource_policy,
    ]).select_from(groups)
    for group in conn.execute(query).fetchall():
        if not group.resource_policy:
            data = {
                'total_resource_slots': {},
                'allowed_vfolder_hosts': {},
                'resource_policy': None,
            }
        else:
            policy_name = f'_auto_generated_group_policy_{group.name}_{group.id}'
            query = sa.select([
                keypair_resource_policies.c.total_resource_slots,
                keypair_resource_policies.c.allowed_vfolder_hosts,
            ]).select_from(
                keypair_resource_policies
            ).where(
                keypair_resource_policies.c.name == policy_name
            )
            rp = conn.execute(query).fetchone()
            data = {
                'total_resource_slots': rp.total_resource_slots,
                'allowed_vfolder_hosts': rp.allowed_vfolder_hosts,
                'resource_policy': None,
            }
        query = (groups.update().values(data)
                       .where(groups.c.name == group.name))
        conn.execute(query)
    op.alter_column('groups', column_name='allowed_vfolder_hosts', nullable=False)
    # Delete auto-generated group resource policies.
    query = (
        keypair_resource_policies
        .delete()
        .where(keypair_resource_policies.c.name.like('_auto_generated_group_policy_%'))
    )
    conn.execute(query)
    # Drop `resource_policy` from `groups`.
    op.drop_constraint(op.f('fk_groups_resource_policy_keypair_resource_policies'),
                       'groups', type_='foreignkey')
    op.drop_column('groups', 'resource_policy')

    # ### Drop `resource_policy` from `domains` and restore deprecated domain fields.
    # Add deprecated fields.
    op.add_column('domains', sa.Column('total_resource_slots', ResourceSlotColumn(), default='{}'))
    op.add_column('domains', sa.Column('allowed_vfolder_hosts', pgsql.ARRAY(sa.String), default='{}'))
    op.add_column('domains', sa.Column('allowed_docker_registries',
                                       pgsql.ARRAY(sa.String), default='{}'))
    # Update deprecated fields from resource policies.
    query = sa.select([
        domains.c.name,
        domains.c.resource_policy,
    ]).select_from(domains)
    for domain in conn.execute(query).fetchall():
        if not domain.resource_policy:
            data = {
                'total_resource_slots': {},
                'allowed_vfolder_hosts': {},
                'allowed_docker_registries': {},
                'resource_policy': None,
            }
        else:
            policy_name = f'_auto_generated_domain_policy_{domain.name}'
            query = sa.select([
                keypair_resource_policies.c.total_resource_slots,
                keypair_resource_policies.c.allowed_vfolder_hosts,
                keypair_resource_policies.c.allowed_docker_registries,
            ]).select_from(
                keypair_resource_policies
            ).where(
                keypair_resource_policies.c.name == policy_name
            )
            rp = conn.execute(query).fetchone()
            data = {
                'total_resource_slots': rp.total_resource_slots,
                'allowed_vfolder_hosts': rp.allowed_vfolder_hosts,
                'allowed_docker_registries': rp.allowed_docker_registries,
                'resource_policy': None,
            }
        query = (domains.update().values(data)
                        .where(domains.c.name == domain.name))
        conn.execute(query)
    op.alter_column('domains', column_name='allowed_vfolder_hosts', nullable=False)
    op.alter_column('domains', column_name='allowed_docker_registries', nullable=False)
    # Delete auto-generated domain resource policies.
    query = (
        keypair_resource_policies
        .delete()
        .where(keypair_resource_policies.c.name.like('_auto_generated_domain_policy_%'))
    )
    conn.execute(query)
    # Drop `resource_policy` from `domains`.
    op.drop_constraint(op.f('fk_domains_resource_policy_keypair_resource_policies'),
                       'domains', type_='foreignkey')
    op.drop_column('domains', 'resource_policy')

    # ### Drop `allowed_docker_registries` field from `resource_policies`
    op.drop_column('keypair_resource_policies', 'allowed_docker_registries')
