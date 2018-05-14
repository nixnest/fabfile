from invoke import task, Exit
from patchwork.files import contains


BLOCK_SIZE = 1024
INODES_LIMIT = 1000000  # An arbitrarily large number. It's irrelevant

AUTH_KEYS_FILE = '.ssh/authorized_keys'


def _copyDefaultZshrc(ctx, user):
    ctx.sudo('cp /etc/zsh/newuser.zshrc.recommended /home/%s/.zshrc'
             % user, user=user)


def _sshContext(ctx, user, action, key=None):
    ssh_dir = '/home/%s' % user

    ctx.sudo('mkdir -p %s/.ssh' % ssh_dir, user=user)
    ctx.sudo('touch %s/%s' % (ssh_dir, AUTH_KEYS_FILE), user=user,
             pty=True)

    if action == 'enable':
        ctx.sudo("sed -i 's|^|#|gm' %s/%s" % (ssh_dir, AUTH_KEYS_FILE),
                 user=user)
    elif action == 'disable':
        ctx.sudo("sed -i 's|^#||gm' %s/%s" % (ssh_dir, AUTH_KEYS_FILE),
                 user=user)
    elif action == 'add':
        if key is None:
            Exit("No key provided for SSH handling command.")
        if contains(ctx, '%s/%s' % (ssh_dir, AUTH_KEYS_FILE), key):
            print("Key is already authorized, skipping...")
            return
        ctx.sudo("bash -c 'echo \"%s\" >> %s/%s'" %
                 (key, ssh_dir, AUTH_KEYS_FILE),
                 user=user, pty=True)
    elif action == 'remove':
        ctx.run('rm %s/%s' % (ssh_dir, AUTH_KEYS_FILE), pty=True)


@task
def setup_new_user(ctx, user,  ssh_keyfile=None, quota_size=10,
                   is_sudoer=False):
    """Executes the required tasks to fully setup a new user
    add_on_create: whether an SSH key should be added on create (default False)
    ssh_keyfile: pubfile containing the key for the new user (default None)
    quota_size: allocated disk size in Gigabytes (default 10)
    is_sudoer: whether the user should be a sudoer (default False)
    use_zsh: whether the user should have its default shell set to zsh
             (default True)
    """
    create_user(ctx, user)

    create_access(ctx, user, ssh_keyfile=ssh_keyfile)

    set_user_shell(ctx, user)
    _copyDefaultZshrc(ctx, user)

    if is_sudoer:
        enable_sudo(ctx, user)

    if quota_size > 0:
        set_quota(ctx, user, quota_size=quota_size)


@task
def enable_access(ctx, user):
    """Enables the SSH key on the user"""
    _sshContext(ctx, user, action='enable')


@task
def disable_access(ctx, user):
    """Disables the SSH key on the user"""
    _sshContext(ctx, user, action='disable')


@task
def create_access(ctx, user, ssh_keyfile):
    """Adds a SSH key for the user
    ssh_keyfile: pubfile with the key to add (required)"""
    key = ctx.local('cat %s' % ssh_keyfile).stdout.replace('\n', '')
    _sshContext(ctx, user, action='add', key=key)


@task
def remove_access(ctx, user):
    """Removes the authorized_keys from the user"""
    _sshContext(action='remove')


@task
def enable_sudo(ctx, user):
    """Adds user to the sudo group"""
    ctx.sudo('usermod -aG sudo %s' % user)


@task
def disable_sudo(ctx, user):
    """Removes user from the sudo group"""
    ctx.sudo('gpasswd -d %s sudo' % user, warn_only=True)


@task
def set_quota(ctx, user, quota_format='vfsv1', quota_size=10, partition='/'):
    """Sets the disk quota for the user
    quota_format: The format that was configured on fstab (default 'vsfv0')
    quota_size: Allocated disk quota in gigabytes (default 10)
    partition: The partition to quota (default /)
    """
    if not ctx.run('apt list quota | grep installed'):
        print("Quota is not installed/configured. Not setting user quota...")
        return

    quota_size_gb = (BLOCK_SIZE ** 2) * quota_size
    ctx.sudo("setquota -u -F {} {} {} {} {} {} {}".format(
        quota_format, user, quota_size_gb, quota_size_gb,
        INODES_LIMIT, INODES_LIMIT, partition))


@task
def set_user_shell(ctx, user, shell='/bin/zsh'):
    """Reconfigures the user's login shell
    shell: the path of the login shell (default /bin/zsh)
    """
    ctx.sudo('chsh -s %s %s' % (shell, user))


@task
def create_user(ctx, user):
    """Creates a user without password"""
    if ctx.run('id -u %s' % user, warn=True).ok:
        print("The user is already created, skipping task...")
        return

    ctx.sudo('adduser --disabled-password --gecos "" %s' % user)
