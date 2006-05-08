# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   svnmodule.py: rules for building SVN modules.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os

import base
from base import AutogenModule
from base import register_module_type

def parse_svnmodule(node, config, dependencies, suggests, repository):
    id = node.getAttribute('id')
    module = None
    checkoutdir = None
    autogenargs = ''
    makeargs = ''
    supports_non_srcdir_builds = True
    if node.hasAttribute('module'):
        module = node.getAttribute('module')
    if node.hasAttribute('checkoutdir'):
        checkoutdir = node.getAttribute('checkoutdir')
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
    if node.hasAttribute('supports-non-srcdir-builds'):
        supports_non_srcdir_builds = \
            (node.getAttribute('supports-non-srcdir-builds') != 'no')

    # override revision tag if requested.
    autogenargs += ' ' + config.module_autogenargs.get(id, config.autogenargs)
    makeargs += ' ' + config.module_makeargs.get(id, config.makeargs)

    branch = repository.branch(id, module=module, checkoutdir=checkoutdir)

    return AutogenModule(id, branch, autogenargs, makeargs,
                         dependencies=dependencies,
                         suggests=suggests,
                         supports_non_srcdir_builds=supports_non_srcdir_builds)
register_module_type('svnmodule', parse_svnmodule)
