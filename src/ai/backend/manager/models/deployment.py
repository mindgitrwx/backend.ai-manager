import graphene
from graphene.types.datetime import DateTime as GQLDateTime
import sqlalchemy as sa

from .base import (
    metadata,
    GUID, IDColumn,
    Item, PaginatedList,
)


deployments = sa.Table(
    'deployments', metadata,
    IDColumn(),
    sa.Column('name', sa.String(length=64)),  # human-friendly name
    sa.Column('tag', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True),
              server_default=sa.func.now(), index=True),
    sa.Column('is_active', sa.Boolean, index=True, default=True),
    sa.Column('task_template', sa.ForeignKey('task_templates.id'), nullable=False),
    sa.Column('scaling_group', sa.ForeignKey('scaling_groups.name'), index=True, nullable=True),
    sa.Column('domain_name', sa.String(length=64), sa.ForeignKey('domains.name'), nullable=False),
    sa.Column('group_id', GUID, sa.ForeignKey('groups.id'), nullable=False),
    sa.Column('user_uuid', GUID, sa.ForeignKey('users.uuid'), nullable=False),
    sa.Column('access_key', sa.String(length=20), sa.ForeignKey('keypairs.access_key')),
)


class Deployments:
    id = graphene.UUID()
    name = graphene.String()
    tag = graphene.String()
    created_at = GQLDateTime()
    is_active = graphene.Boolean()
    scaling_group = graphene.String()
    domain_name = graphene.String()
    group_id = graphene.UUID()
    user_uuid = graphene.UUID()
    access_key = graphene.String()
    image = graphene.String()
    tag = graphene.String()

    @classmethod
    def parse_row(cls, context, row):
        return {
            'id': row['id'],
            'name': row['name'],
            'tag': row['tag'],
            'created_at': row['created_at'],
            'is_active': row['is_active'],
            'scaling_group': row['scaling_group'],
            'domain_name': row['domain_name'],
            'group_id': row['group_id'],
            'user_uuid': row['user_uuid'],
            'access_key': row['access_key'],
        }

    @classmethod
    def from_row(cls, context, row):
        if row is None:
            return None
        props = cls.parse_row(context, row)
        return cls(**props)
