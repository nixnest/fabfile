#!/usr/bin/env python3

from fabric.api import task, run, env, sudo, execute
from fabric.utils import abort
from fabric.context_managers import cd, settings
from fabric.contrib.files import append, comment, uncomment


AUTH_KEYS_FILE = '.ssh/authorized_keys'
BLOCK_SIZE = 1024
INODES_LIMIT = 1000000  # An arbitrarily large number. It's irrelevant

env['new_user'] = ''


class user_required:
    """Decorator that verifies a user has been set
    """
    def __init__(self, f):
        if not env['new_user']:
            abort("A user must be set to run user commands.")
        f()


def _isFileEmpty(file):
    if run('file %s | grep %s' % (file, file), warn_only=True).succeeded:
        return True
    else:
        return False


def _sshContext(action, keyfile=None):
    """TODO: make this an actual context manager and
    relegate each action to its task
    """
    with settings(user=env['new_user']), cd('/home/%s' % env['user']):
        run('mkdir -p .ssh')
        run('touch %s' % AUTH_KEYS_FILE)
        if action == 'enable':
            uncomment(AUTH_KEYS_FILE, r'^')
        elif action == 'disable':
            comment(AUTH_KEYS_FILE, r'^')
        elif action == 'add':
            if keyfile is None:
                abort("No key provided for SSH handling command.")
                with open(keyfile) as key:
                    append(AUTH_KEYS_FILE, key)
        elif action == 'remove':
            run('rm %s' % AUTH_KEYS_FILE)


@task
def on(host):
    """Set target host to work on
    """
    env['hosts'] = [host]


@task
def user(user):
    """Set target user to work on
    """
    env['new_user'] = user


@user_required
@task
def setup_new_user(add_on_create=False, ssh_keyfile=None, quota_size=10):
    """Executes the required tasks to fully setup a new user
    add_on_create: whether an SSH key should be added on create (default False)
    ssh_keyfile: pubfile containing the key for the new user (default None)
    quota_size: allocated disk size in Gigabytes (default 10)
    """
    execute(create_user)

    if add_on_create and ssh_keyfile:
        execute(create_access, action='add', keyfile=ssh_keyfile)

    execute(set_quota, quota_size=quota_size)


@user_required
@task
def create_user():
    """Creates a user without password"""
    sudo('adduser --disabled-password --gecos "" %s' % env['new_user'])


@user_required
@task
def enable_access():
    """Enables the SSH key on the user"""
    _sshContext(action='enable')


@user_required
@task
def disable_access():
    """Disables the SSH key on the user"""
    _sshContext(action='disable')


@user_required
@task
def create_access(ssh_keyfile):
    """Adds a SSH key for the user
    ssh_keyfile: pubfile with the key to add (required)"""
    _sshContext(action='add', keyfile=ssh_keyfile)


@user_required
@task
def remove_access():
    """Removes the authorized_keys from the user"""
    _sshContext(action='remove')


@user_required
@task
def set_quota(quota_format='vsfv0', quota_size=10):
    """Sets the disk quota for the user
    quota_format: The format that was configured on fstab (default 'vsfv0')
    quota_size: Allocated disk quota in gigabytes (default 10)
    """
    quota_size_gb = BLOCK_SIZE ** quota_size
    sudo("setquota -u -F %(format)s %(user)s %(size)i %(size)i %(inode)i " +
         "%(inode)i /" % {'format': quota_format, 'user': env['new_user'],
                          'size': quota_size_gb, 'inode': INODES_LIMIT})
