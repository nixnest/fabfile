Fab-nixNest
###########

This is the `Fabric <http://www.fabfile.org/>`_ project for the nixNest community VPS.

In theory, it should also work for generic Debian/Ubuntu machines. However, the
task selection is rather limited as it's thought for our use mainly.

Dependencies
============

This script has recently been rewritten, so it only works with fabric>=2.0.0.
More detailed dependencies are available in ``requirements.txt``, as usual.

Usage
=====

``fab -l`` gives you an overview of the available tasks. More detail about these
tasks can be read by running ``fab -h <module>.<command>``.

Host management changed, so a selection task is no longer necessary. This is now
done through the ``-H`` command line flag.

As well, user selection is also a per-task assignment, which is why using the
wrapper tasks is more imporant than ever.

The fabric project is split between (for now) two modules: ``users`` and ``server``

A full usage example would look like this::

    fab -H nixnest setup_new_user --user=nep --ssh_keyfile=~/.ssh/id_ed25519.pub --is-sudoer
