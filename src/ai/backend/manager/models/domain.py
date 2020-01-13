from collections import OrderedDict
import re
from typing import Sequence

import graphene
from graphene.types.datetime import DateTime as GQLDateTime
import sqlalchemy as sa

from .base import (
    metadata,
    privileged_mutation,
    simple_db_mutate,
    simple_db_mutate_returning_item,
    set_if_set,
)
from .resource_policy import KeyPairResourcePolicy
from .scaling_group import ScalingGroup
from .user import UserRole


__all__: Sequence[str] = (
    'domains',
    'Domain', 'DomainInput', 'ModifyDomainInput',
    'CreateDomain', 'ModifyDomain', 'DeleteDomain',
)

_rx_slug = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$')

domains = sa.Table(
    'domains', metadata,
    sa.Column('name', sa.String(length=64), primary_key=True),
    sa.Column('description', sa.String(length=512)),
    sa.Column('is_active', sa.Boolean, default=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column('modified_at', sa.DateTime(timezone=True),
              server_default=sa.func.now(), onupdate=sa.func.current_timestamp()),
    sa.Column('resource_policy', sa.String(length=256),
              sa.ForeignKey('keypair_resource_policies.name'), index=True),
    # TODO: separate resource-related fields with new domain resource policy table when needed.
    #: Field for synchronization with external services.
    sa.Column('integration_id', sa.String(length=512)),
)


class Domain(graphene.ObjectType):
    name = graphene.String()
    description = graphene.String()
    is_active = graphene.Boolean()
    created_at = GQLDateTime()
    modified_at = GQLDateTime()
    resource_policy = graphene.String()
    integration_id = graphene.String()

    # Dynamic fields.
    scaling_groups = graphene.List(lambda: graphene.String)

    # Legacy fields.
    total_resource_slots = graphene.JSONString()
    allowed_vfolder_hosts = graphene.List(lambda: graphene.String)
    allowed_docker_registries = graphene.List(lambda: graphene.String)

    async def resolve_scaling_groups(self, info):
        sgroups = await ScalingGroup.load_by_domain(info.context, self.name)
        return [sg.name for sg in sgroups]

    async def resolve_total_resource_slots(self, info):
        if self.resource_policy is None:
            return {}
        policies = await KeyPairResourcePolicy.batch_load_by_name(info.context, [self.resource_policy])
        slots = policies[0].total_resource_slots if policies and len(policies) > 0 else {}
        return slots

    async def resolve_allowed_vfolder_hosts(self, info):
        if self.resource_policy is None:
            return []
        policies = await KeyPairResourcePolicy.batch_load_by_name(info.context, [self.resource_policy])
        hosts = policies[0].allowed_vfolder_hosts if policies and len(policies) > 0 else []
        return hosts

    async def resolve_allowed_docker_registries(self, info):
        if self.resource_policy is None:
            return []
        policies = await KeyPairResourcePolicy.batch_load_by_name(info.context, [self.resource_policy])
        registries = policies[0].allowed_docker_registries if policies and len(policies) > 0 else []
        return registries

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            name=row['name'],
            description=row['description'],
            is_active=row['is_active'],
            created_at=row['created_at'],
            modified_at=row['modified_at'],
            resource_policy=row['resource_policy'],
            integration_id=row['integration_id'],
        )

    @staticmethod
    async def load_all(context, *, is_active=None):
        async with context['dbpool'].acquire() as conn:
            query = sa.select([domains]).select_from(domains)
            if is_active is not None:
                query = query.where(domains.c.is_active == is_active)
            objs_per_key = OrderedDict()
            async for row in conn.execute(query):
                o = Domain.from_row(row)
                objs_per_key[row.name] = o
            objs = list(objs_per_key.values())
        return objs

    @staticmethod
    async def batch_load_by_name(context, names=None, *, is_active=None):
        async with context['dbpool'].acquire() as conn:
            query = (sa.select([domains])
                       .select_from(domains)
                       .where(domains.c.name.in_(names)))
            objs_per_key = OrderedDict()
            # For each name, there is only one domain.
            # So we don't build lists in objs_per_key variable.
            for k in names:
                objs_per_key[k] = None
            async for row in conn.execute(query):
                o = Domain.from_row(row)
                objs_per_key[row.name] = o
        return tuple(objs_per_key.values())


class DomainInput(graphene.InputObjectType):
    description = graphene.String(required=False)
    is_active = graphene.Boolean(required=False, default=True)
    resource_policy = graphene.String(required=False)
    integration_id = graphene.String(required=False)


class ModifyDomainInput(graphene.InputObjectType):
    name = graphene.String(required=False)
    description = graphene.String(required=False)
    is_active = graphene.Boolean(required=False)
    resource_policy = graphene.String(required=False)
    integration_id = graphene.String(required=False)


class CreateDomain(graphene.Mutation):

    class Arguments:
        name = graphene.String(required=True)
        props = DomainInput(required=True)

    ok = graphene.Boolean()
    msg = graphene.String()
    domain = graphene.Field(lambda: Domain)

    @classmethod
    @privileged_mutation(UserRole.SUPERADMIN)
    async def mutate(cls, root, info, name, props):
        if _rx_slug.search(name) is None:
            return cls(False, 'invalid name format. slug format required.', None)
        data = {
            'name': name,
            'description': props.description,
            'is_active': props.is_active,
            'resource_policy': props.resource_policy,
            'integration_id': props.integration_id,
        }
        insert_query = (
            domains.insert()
            .values(data)
        )
        item_query = domains.select().where(domains.c.name == name)
        return await simple_db_mutate_returning_item(
            cls, info.context, insert_query,
            item_query=item_query, item_cls=Domain)


class ModifyDomain(graphene.Mutation):

    class Arguments:
        name = graphene.String(required=True)
        props = ModifyDomainInput(required=True)

    ok = graphene.Boolean()
    msg = graphene.String()
    domain = graphene.Field(lambda: Domain)

    @classmethod
    @privileged_mutation(UserRole.SUPERADMIN)
    async def mutate(cls, root, info, name, props):
        data = {}
        set_if_set(props, data, 'name')  # data['name'] is new domain name
        set_if_set(props, data, 'description')
        set_if_set(props, data, 'is_active')
        set_if_set(props, data, 'resource_policy')
        set_if_set(props, data, 'integration_id')
        if 'name' in data:
            assert _rx_slug.search(data['name']) is not None, \
                'invalid name format. slug format required.'
        update_query = (
            domains.update()
            .values(data)
            .where(domains.c.name == name)
        )
        # The name may have changed if set.
        if 'name' in data:
            name = data['name']
        item_query = domains.select().where(domains.c.name == name)
        return await simple_db_mutate_returning_item(
            cls, info.context, update_query,
            item_query=item_query, item_cls=Domain)


class DeleteDomain(graphene.Mutation):

    class Arguments:
        name = graphene.String(required=True)

    ok = graphene.Boolean()
    msg = graphene.String()

    @classmethod
    @privileged_mutation(UserRole.SUPERADMIN)
    async def mutate(cls, root, info, name):
        query = (
            domains.update()
            .values(is_active=False)
            .where(domains.c.name == name)
        )
        return await simple_db_mutate(cls, info.context, query)
