# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   cmake.py: cmake module type definitions.
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

from jhbuild.errors import BuildStateError
from jhbuild.modtypes import \
     Package, get_dependencies, get_branch, register_module_type

__all__ = [ 'CMakeModule' ]

class CMakeModule(Package):
    """Base type for modules that use CMake build system."""
    type = 'cmake'

    STATE_CHECKOUT = 'checkout'
    STATE_FORCE_CHECKOUT = 'force_checkout'
    STATE_CONFIGURE = 'configure'
    STATE_BUILD = 'build'
    STATE_DIST = 'dist'
    STATE_INSTALL = 'install'

    def __init__(self, name, branch, dependencies=[], after=[], suggests=[]):
        Package.__init__(self, name, dependencies, after, suggests)
        self.branch = branch

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        if buildscript.config.buildroot:
            d = buildscript.config.builddir_pattern % (
                os.path.basename(self.get_srcdir(buildscript)))
            return os.path.join(buildscript.config.buildroot, d)
        else:
            return self.get_srcdir(buildscript)

    def get_revision(self):
        return self.branch.tree_id()

    def do_start(self, buildscript):
        pass
    do_start.next_state = STATE_CHECKOUT
    do_start.error_states = []

    def do_checkout(self, buildscript):
        self.checkout(buildscript)
    do_checkout.next_state = STATE_CONFIGURE
    do_checkout.error_states = [STATE_FORCE_CHECKOUT]

    def skip_force_checkout(self, buildscript, last_state):
        return False

    def do_force_checkout(self, buildscript):
        buildscript.set_action(_('Checking out'), self)
        self.branch.force_checkout(buildscript)
    do_force_checkout.next_state = STATE_CONFIGURE
    do_force_checkout.error_states = [STATE_FORCE_CHECKOUT]

    def skip_configure(self, buildscript, last_state):
        return buildscript.config.nobuild
    
    def do_configure(self, buildscript):
        buildscript.set_action(_('Configuring'), self)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        if not os.path.exists(builddir):
            os.mkdir(builddir)
        prefix = os.path.expanduser(buildscript.config.prefix)
        cmd = ['cmake', '-DCMAKE_INSTALL_PREFIX=%s' % prefix, srcdir]
        buildscript.execute(cmd, cwd = builddir, extra_env = self.extra_env)
    do_configure.next_state = STATE_BUILD
    do_configure.error_states = [STATE_FORCE_CHECKOUT]

    def skip_build(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        builddir = self.get_builddir(buildscript)
        buildscript.execute(os.environ.get('MAKE', 'make'), cwd = builddir,
                extra_env = self.extra_env)
    do_build.next_state = STATE_DIST
    do_build.error_states = [STATE_FORCE_CHECKOUT]

    def skip_dist(self, buildscript, last_state):
        return not buildscript.config.makedist

    def do_dist(self, buildscript):
        buildscript.set_action(_('Creating tarball for'), self)
        cmd = '%s package_source' % os.environ.get('MAKE', 'make')
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                extra_env = self.extra_env)
    do_dist.next_state = STATE_INSTALL
    do_dist.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_install(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        builddir = self.get_builddir(buildscript)
        buildscript.execute([os.environ.get('MAKE', 'make'), 'install'],
                cwd = builddir,
                extra_env = self.extra_env)
        buildscript.packagedb.add(self.name, self.get_revision() or '')
    do_install.next_state = Package.STATE_DONE
    do_install.error_states = []

    def xml_tag_and_attrs(self):
        return 'cmake', [('id', 'name', None)]


def parse_cmake(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')
    dependencies, after, suggests = get_dependencies(node)
    branch = get_branch(node, repositories, default_repo, config)

    return CMakeModule(id, branch, dependencies = dependencies, after = after,
            suggests = suggests)

register_module_type('cmake', parse_cmake)

