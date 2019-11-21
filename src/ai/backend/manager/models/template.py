import graphene
from graphene.types.datetime import DateTime as GQLDateTime
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pgsql

from ai.backend.common.types import (
    SessionTypes,
)
from .base import (
    metadata,
    BigInt, GUID, IDColumn, EnumType,
    ResourceSlotColumn,
    Item, PaginatedList,
)


task_templates = sa.Table(
    'task_templates', metadata,
    IDColumn(),
    sa.Column('name', sa.String(length=64)),  # human-friendly name
    sa.Column('tag', sa.String(length=64), nullable=True),
    sa.Column('domain_name', sa.String(length=64), sa.ForeignKey('domains.name'), nullable=False),
    sa.Column('group_id', GUID, sa.ForeignKey('groups.id'), nullable=False),
    sa.Column('user_uuid', GUID, sa.ForeignKey('users.uuid'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True),
              server_default=sa.func.now(), index=True),

    # Execution parameters
    sa.Column('image', sa.String(length=512)),
    sa.Column('registry', sa.String(length=512)),
    sa.Column('sess_type', EnumType(SessionTypes), nullable=False,
              default=SessionTypes.INTERACTIVE, server_default=SessionTypes.INTERACTIVE.name),
    sa.Column('resource_slots', ResourceSlotColumn(), nullable=False),
    sa.Column('resource_opts', pgsql.JSONB(), nullable=True, default={}),
    sa.Column('environ', sa.ARRAY(sa.String), nullable=True),
    sa.Column('mounts', sa.ARRAY(sa.String), nullable=True),  # list of list
    sa.Column('startup_command', sa.Text, nullable=True),
)


class TaskTemplates:
    id = graphene.UUID()
    name = graphene.String()
    tag = graphene.String()
    created_at = GQLDateTime()
    domain_name = graphene.String()
    group_id = graphene.UUID()
    user_uuid = graphene.UUID()

    image = graphene.String()
    registry = graphene.String()
    sess_type = graphene.String()
    resource_slots = graphene.JSONString()
    resource_opts = graphene.JSONString()
    environ = graphene.List(lambda: graphene.List(lambda: graphene.String))
    mounts = graphene.List(lambda: graphene.List(lambda: graphene.String))
    startup_command = graphene.String()

    @classmethod
    def parse_row(cls, context, row):
        return {
            'id': row['id'],
            'name': row['name'],
            'tag': row['tag'],
            'created_at': row['created_at'],
            'domain_name': row['domain_name'],
            'group_id': row['group_id'],
            'user_uuid': row['user_uuid'],

            'image': row['image'],
            'registry': row['registry'],
            'sess_type': row['sess_type'].name,
            'resource_slots': row['resource_slots'].to_json(),
            'resource_opts': row['resource_opts'],
            'startup_command': row['startup_command'],
            'environ': row['environ'],  # TODO: convert to list[tuple]
            'mounts': row['mounts'],
        }

    @classmethod
    def from_row(cls, context, row):
        if row is None:
            return None
        props = cls.parse_row(context, row)
        return cls(**props)
