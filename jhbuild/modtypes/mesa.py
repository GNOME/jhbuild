# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2006-2007  Eric Anholt
#
#   perl.py: perl module type definitions.
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

__metaclass__ = type

import os
import glob
import platform

from jhbuild.errors import BuildStateError
from jhbuild.modtypes import \
     Package, get_dependencies, get_branch, register_module_type

__all__ = [ 'MesaModule' ]

class MesaModule(Package):
    """Base type for building Mesa."""
    type = 'mesa'

    STATE_CHECKOUT = 'checkout'
    STATE_FORCE_CHECKOUT = 'force_checkout'
    STATE_BUILD = 'build'
    STATE_INSTALL = 'install'

    def __init__(self, name, branch, makeargs='',
                 dependencies=[], after=[]):
        Package.__init__(self, name, dependencies, after)
        self.branch = branch
        self.makeargs = makeargs

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        return self.get_srcdir(buildscript)

    def get_revision(self):
        return self.branch.branchname

    def get_mesa_config(self):
        uname = platform.uname();
        if uname[0] == 'FreeBSD':
            if uname[4] == 'i386':
                config = 'freebsd-dri-x86'
            elif uname[4] == 'amd64':
                config = 'freebsd-dri-amd64'
            else:
                config = 'freebsd-dri'
        if uname[0] == 'Linux':
            if uname[4] == 'i386':
                config = 'linux-dri-x86'
            elif uname[4] == 'x86_64':
                config = 'linux-dri-x86_64'
            else:
                config = 'linux-dri'
        return config

    def do_start(self, buildscript):
        pass
    do_start.next_state = STATE_CHECKOUT
    do_start.error_states = []

    def skip_checkout(self, buildscript, last_state):
        # skip the checkout stage if the nonetwork flag is set
        return buildscript.config.nonetwork

    def do_checkout(self, buildscript):
        srcdir = self.get_srcdir(buildscript)
        buildscript.set_action('Checking out', self)
        self.branch.checkout(buildscript)
        # did the checkout succeed?
        if not os.path.exists(srcdir):
            raise BuildStateError('source directory %s was not created'
                                  % srcdir)
    do_checkout.next_state = STATE_BUILD
    do_checkout.error_states = [STATE_FORCE_CHECKOUT]

    def skip_force_checkout(self, buildscript, last_state):
        return False

    def do_force_checkout(self, buildscript):
        buildscript.set_action('Checking out', self)
        self.branch.force_checkout(buildscript)
    do_force_checkout.next_state = STATE_BUILD
    do_force_checkout.error_states = [STATE_FORCE_CHECKOUT]

    def skip_build(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_build(self, buildscript):
        buildscript.set_action('Building', self)
        builddir = self.get_builddir(buildscript)
        make = os.environ.get('MAKE', 'make')
	if (os.path.exists(builddir + '/configs/current')):
	    buildscript.execute([make], cwd=builddir)
	else:
	    buildscript.execute([make, self.get_mesa_config()], cwd=builddir)
    do_build.next_state = STATE_INSTALL
    do_build.error_states = [STATE_FORCE_CHECKOUT]

    def skip_install(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_install(self, buildscript):
        buildscript.set_action('Installing', self)
        builddir = self.get_builddir(buildscript)
        prefix = buildscript.config.prefix

        buildscript.execute(['mkdir', '-p',
			     prefix + '/lib/dri'],
                             cwd=builddir)
        for x in glob.glob(builddir + '/lib/libGL*'):
            buildscript.execute(['cp',
                                 x,
                                 prefix + '/lib'],
                                cwd=builddir)
        for x in glob.glob(builddir + '/lib/*_dri.so'):
            buildscript.execute(['cp',
                                 x,
                                 prefix + '/lib/dri'],
                                cwd=builddir)
        for x in glob.glob(builddir + '/include/GL/*.h'):
            buildscript.execute(['cp',
                                 x,
                                 prefix + '/include/GL'],
                                cwd=builddir)
        buildscript.packagedb.add(self.name, self.get_revision() or '')
    do_install.next_state = Package.STATE_DONE
    do_install.error_states = []


def parse_mesa(node, config, repositories, default_repo):
    id = node.getAttribute('id')
    makeargs = ''
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')

    # override revision tag if requested.
    makeargs += ' ' + config.module_makeargs.get(id, config.makeargs)

    dependencies, after = get_dependencies(node)
    branch = get_branch(node, repositories, default_repo)

    return MesaModule(id, branch, makeargs,
                         dependencies=dependencies, after=after)
register_module_type('mesa', parse_mesa)
