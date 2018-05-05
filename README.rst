Fab-nixNest
###########

This is the `Fabric <http://www.fabfile.org/>`_ project for the nixNest community VPS.

In theory, it should also work for generic Debian/Ubuntu machines. However, the
task selection is rather limited as it's thought for our use mainly.

Dependencies
============

Execution has only been tested with Fabric3==1.14.post1

Usage
=====

``fab -l`` gives you an overview of the available tasks. More detail about these
tasks can be read by running ``fab -d <command>``.

A full usage example would look like this::

    fab on:nixnest user:nep setup_new_user:add_on_create=True,ssh_keyfile=~/.ssh/id_ed25519.pub
