from invoke import task

APT_PACKAGES_FILE = './packages-apt'
PIP_PACKAGES_FILE = './packages-pip'


def _loadPackages(packages_file):
    return ' '.join(
        [package for package in open(packages_file).readlines()]
    ).replace('\n', '')


def _installAptPackages(ctx, packages):
    ctx.sudo('apt -qq update')
    ctx.sudo('apt -yq install %s' % packages)


def _installPipPackages(ctx, packages):
    ctx.sudo('pip3 install --quiet %s' % packages)


@task
def bootstrap_server(ctx):
    """Installs base packages for the server. In case of migration"""
    apt_packages = _loadPackages(APT_PACKAGES_FILE)
    pip_packages = _loadPackages(PIP_PACKAGES_FILE)

    _installAptPackages(apt_packages)
    _installPipPackages(pip_packages)
