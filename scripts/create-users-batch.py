'''
This scripts generates a bunch of users
by creating fixtures and populating them
using the manager CLI.
'''

import json
import secrets
import subprocess
import sys
import tempfile
import uuid

from ai.backend.manager.models.keypair import generate_keypair

import click


@click.command()
@click.argument('username_prefix')
@click.argument('num_users', type=int)
@click.option('-r', '--resource-policy', type=str, default='default',
              help='Set the resource policy of the users.')
@click.option('-d', '--domain', type=str, default='default',
              help='Set the domain name of the users.')
@click.option('-g', '--group', type=str, default='default',
              help='Set the group name of the users.')
@click.option('--create-group', is_flag=True,
              help='Create a new group in the given domain.')
@click.option('--rate-limit', type=int, default=30_000,
              help='Set the API rate limit for the keypairs.')
@click.option('--dry-run', is_flag=True,
              help='Generate fixture and credentials only without population.')
def main(username_prefix, num_users, *,
         resource_policy,
         domain, group, create_group,
         rate_limit, dry_run):
    '''
    Generate NUM_USERS users with their email/names prefixed with USERNAME_PREFIX.
    '''
    run_id = secrets.token_hex(4)
    fixture = {}

    if create_group:
        fixture['groups'] = []
        group_uuid = str(uuid.uuid4())
        g = {
            'id': group_uuid,
            'name': group,
            'is_active': True,
            'domain_name': domain,
            'total_resource_slots': {},
            'allowed_vfolder_hosts': [],
        }
        fixture['groups'].append(g)
    else:
        group_uuid = '...'  # TODO: implement

    fixture['users'] = []
    fixture['association_groups_users'] = []
    fixture['keypairs'] = []

    for idx in range(1, num_users + 1):
        ak, sk = generate_keypair()
        email = f'{username_prefix}{idx:03d}@managed.lablup.com'
        user_uuid = str(uuid.uuid4())
        u = {
            'uuid': user_uuid,
            'username': email,
            'email': email,
            'password': secrets.token_urlsafe(4),
            'need_password_change': True,
            'full_name': f'{username_prefix}{idx:03d}',
            'description': 'Auto-generated user account',
            'is_active': True,
            'domain_name': domain,
            'role': 'USER',
        }
        fixture['users'].append(u)
        uga = {
            'user_id': user_uuid,
            'group_id': group_uuid,
        }
        fixture['association_groups_users'].append(uga)
        kp = {
            'user_id': email,
            'access_key': ak,
            'secret_key': sk,
            'is_active': True,
            'is_admin': False,
            'resource_policy': resource_policy,
            'concurrency_used': 0,
            'rate_limit': rate_limit,
            'num_queries': 0,
            'user': user_uuid,
        }
        fixture['keypairs'].append(kp)

    with tempfile.NamedTemporaryFile('w', prefix=username_prefix,
                                     suffix='.json', encoding='utf-8') as ftmp:
        json.dump(fixture, ftmp, indent=4)
        ftmp.flush()
        if dry_run:
            fixture_path = f'generated-users-{run_id}-fixture.json'
            with open(fixture_path, 'w') as fout:
                json.dump(fixture, fout, indent=4)
            print(f'Generated user fixtures are saved at {fixture_path}')
        else:
            subprocess.run([
                sys.executable, '-m', 'ai.backend.manager.cli',
                'fixture', 'populate', ftmp.name,
            ], check=True)

    creds_path = f'generated-users-{run_id}-creds.csv'
    with open(creds_path, 'w') as f:
        f.write('username,password,access_key,secret_key\n')
        for u, kp in zip(fixture['users'], fixture['keypairs']):
            f.write(f"{u['username']},{u['password']},{kp['access_key']},{kp['secret_key']}\n")

    print(f'Generated user credentials are saved at {creds_path}')
    if create_group:
        print(f'NOTE: You need to configure total_resource_slots and allowed_vfolder_hosts\n'
              f'      in the new group "{group}" as required.')


if __name__ == '__main__':
    main()
