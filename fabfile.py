#!/usr/bin/env python3

from fabric.api import task, run, env, sudo, execute, local
from fabric.utils import abort, puts, warn
from fabric.context_managers import cd, settings
from fabric.contrib.files import append, comment, uncomment


AUTH_KEYS_FILE = '.ssh/authorized_keys'
BLOCK_SIZE = 1024
INODES_LIMIT = 1000000  # An arbitrarily large number. It's irrelevant

env['new_user'] = ''
env['use_ssh_config'] = True


class user_required:
    """Decorator that verifies a user has been set
    """
    def __init__(self, f):
        self.f = f

    def __call__(self):
        if not env['new_user']:
            abort("A user must be set to run user commands.")
        self.f()


def _runFailsafeCommand(command):
    return run(command, warn_only=True)


def _isKeyInFile(key):
    key = key.replace(' ', '\ ')
    with cd('/home/%s/.ssh' % env['new_user']):
        if _runFailsafeCommand('grep %s authorized_keys'
                               % key).succeeded:
            return True
        return False


def _isUserCreated():
    if _runFailsafeCommand('id -u %s' % env['new_user']).succeeded:
        return True
    return False


def _isFileEmpty(file):
    if _runFailsafeCommand('file %s | grep %s' % (file, file)).succeeded:
        return True
    return False


def _sshContext(action, key=None):
    """TODO: make this an actual context manager and
    relegate each action to its task
    """
    with cd('/home/%s' % env['new_user']), settings(sudo_user=env['new_user']):
        sudo('mkdir -p .ssh')
        sudo('touch %s' % AUTH_KEYS_FILE)
        if action == 'enable':
            uncomment(AUTH_KEYS_FILE, r'^')
        elif action == 'disable':
            comment(AUTH_KEYS_FILE, r'^')
        elif action == 'add':
            if key is None:
                abort("No key provided for SSH handling command.")
            if _isKeyInFile(key):
                puts("Key is already authorized, skipping...")
                return
            append(AUTH_KEYS_FILE, key, use_sudo=True)
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


@task
def setup_new_user(add_on_create=False, ssh_keyfile=None, quota_size=10):
    """Executes the required tasks to fully setup a new user
    add_on_create: whether an SSH key should be added on create (default False)
    ssh_keyfile: pubfile containing the key for the new user (default None)
    quota_size: allocated disk size in Gigabytes (default 10)
    """
    execute(create_user)

    if add_on_create and ssh_keyfile:
        execute(create_access, ssh_keyfile=ssh_keyfile)

    execute(set_quota, quota_size=quota_size)


@task
def create_user():
    """Creates a user without password"""
    if _isUserCreated():
        puts("The user is already created, skipping task...")
        return

    sudo('adduser --disabled-password --gecos "" %s' % env['new_user'])


@task
def enable_access():
    """Enables the SSH key on the user"""
    _sshContext(action='enable')


@task
def disable_access():
    """Disables the SSH key on the user"""
    _sshContext(action='disable')


@task
def create_access(ssh_keyfile):
    """Adds a SSH key for the user
    ssh_keyfile: pubfile with the key to add (required)"""
    key = local('cat %s' % ssh_keyfile, capture=True)
    puts('Using key %s...' % key)
    _sshContext(action='add', key=key)


@task
def remove_access():
    """Removes the authorized_keys from the user"""
    _sshContext(action='remove')


@task
def enable_sudo():
    """Adds user to the sudo group"""
    sudo('usermod -aG sudo %s' % env['user'])


@task
def disable_sudo():
    """Removes user from the sudo group"""
    sudo('gpasswd -d %s sudo' % env['user'])


@task
def set_quota(quota_format='vsfv0', quota_size=10):
    """Sets the disk quota for the user
    quota_format: The format that was configured on fstab (default 'vsfv0')
    quota_size: Allocated disk quota in gigabytes (default 10)
    """
    if not _runFailsafeCommand('dpkg-query -l quota').succeeded:
        warn("Quota is not installed/configured. Not setting user quota...")
        return
    quota_size_gb = (BLOCK_SIZE ** 2) * quota_size
    sudo("setquota -u -F {} {} {} {} {} {} /".format(
        quota_format, env['new_user'], quota_size_gb, quota_size_gb,
        INODES_LIMIT, INODES_LIMIT))
