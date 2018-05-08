#!/usr/bin/env python3

from fabric.api import task, run, env, sudo, execute, local
from fabric.utils import abort, puts, warn
from fabric.context_managers import cd, settings
from fabric.contrib.files import append, comment, uncomment


AUTH_KEYS_FILE = '.ssh/authorized_keys'
BLOCK_SIZE = 1024
INODES_LIMIT = 1000000  # An arbitrarily large number. It's irrelevant

APT_PACKAGES_FILE = './packages-apt'
PIP_PACKAGES_FILE = './packages-pip'

env['new_user'] = ''
env['use_ssh_config'] = True

# Disgusting hack to pass environment through sudo
# Useful for cloning repos and stuff
env['sudo_prefix'] += '-E '


class user_required:
    """Decorator that verifies a user has been set
    """
    def __init__(self, func):
        self.func = func

    def __call__(self):
        if not env['new_user']:
            abort("A user must be set to run user commands.")
        self.func()


def _copyDefaultZshrc():
    sudo('cp /etc/zsh/newuser.zshrc.recommended /home/%s/.zshrc'
         % env['new_user'], sudo_user=env['new_user'])


def _installAptPackages(packages):
    sudo('apt -qq update')
    sudo('apt -yq install %s' % packages)


def _installPipPackages(packages):
    sudo('pip3 install --quiet %s' % packages)


def _addAptRepo(repository):
    sudo("add-apt-repository \"%s\"" % repository, shell=True)


def _setupDocker():
    sudo('curl -fsSL https://download.docker.com/linux/debian/gpg | ' +
         'sudo apt-key add -', shell=True)

    _addAptRepo("deb [arch=amd64] https://download.docker.com/linux/debian \
       $(lsb_release -cs) \
       stable")
    _installAptPackages('docker-ce')


def _loadPackages(packages_file):
    return ' '.join(
        [package for package in open(packages_file).readlines()]
    ).replace('\n', '')


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


def _isFileEmpty(file_to_check):
    if _runFailsafeCommand(
            'file %s | grep %s' % (file_to_check, file_to_check)).succeeded:
        return True
    return False


def _sshContext(action, key=None):
    """TODO: make this an actual context manager and
    delegate each action to its task
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
def user(new_user):
    """Set target user to work on
    """
    env['new_user'] = new_user


@task
def setup_new_user(add_on_create=False, ssh_keyfile=None, quota_size=10,
                   is_sudoer=False, use_zsh=True):
    """Executes the required tasks to fully setup a new user
    add_on_create: whether an SSH key should be added on create (default False)
    ssh_keyfile: pubfile containing the key for the new user (default None)
    quota_size: allocated disk size in Gigabytes (default 10)
    is_sudoer: whether the user should be a sudoer (default False)
    use_zsh: whether the user should have its default shell set to zsh
             (default True)
    """
    execute(create_user)

    if add_on_create and ssh_keyfile:
        execute(create_access, ssh_keyfile=ssh_keyfile)

    if is_sudoer:
        execute(enable_sudo)

    if use_zsh:
        execute(set_user_shell)
        _copyDefaultZshrc()

    if quota_size > 0:
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
    sudo('usermod -aG sudo %s' % env['new_user'])


@task
def disable_sudo():
    """Removes user from the sudo group"""
    sudo('gpasswd -d %s sudo' % env['new_user'], warn_only=True)


@task
def set_quota(quota_format='vfsv1', quota_size=10, partition='/'):
    """Sets the disk quota for the user
    quota_format: The format that was configured on fstab (default 'vsfv0')
    quota_size: Allocated disk quota in gigabytes (default 10)
    partition: The partition to quota (default /)
    """
    if not _runFailsafeCommand('apt list quota | grep installed').succeeded:
        warn("Quota is not installed/configured. Not setting user quota...")
        return

    quota_size_gb = (BLOCK_SIZE ** 2) * quota_size
    sudo("setquota -u -F {} {} {} {} {} {} {}".format(
        quota_format, env['new_user'], quota_size_gb, quota_size_gb,
        INODES_LIMIT, INODES_LIMIT, partition))


@task
def bootstrap_server():
    """Installs base packages for the server. In case of migration"""
    apt_packages = _loadPackages(APT_PACKAGES_FILE)
    pip_packages = _loadPackages(PIP_PACKAGES_FILE)

    _installAptPackages(apt_packages)
    _installPipPackages(pip_packages)

    _setupDocker()


@task
def set_user_shell(shell='/bin/zsh'):
    """Reconfigures the user's login shell
    shell: the path of the login shell (default /bin/zsh)
    """
    sudo('chsh -s %s %s' % (shell, env['new_user']))
