# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
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
import re

from jhbuild.errors import BuildStateError
from jhbuild.modtypes import \
     Package, get_dependencies, get_branch, register_module_type, \
     checkout, check_build_policy

__all__ = [ 'PerlModule' ]

class PerlModule(Package):
    """Base type for modules that are distributed with a Perl style
    "Makefile.PL" Makefile."""
    type = 'perl'

    STATE_CHECKOUT = 'checkout'
    STATE_FORCE_CHECKOUT = 'force_checkout'
    STATE_BUILD = 'build'
    STATE_INSTALL = 'install'

    def __init__(self, name, branch, makeargs='',
                 dependencies=[], after=[], suggests=[]):
        Package.__init__(self, name, dependencies, after, suggests)
        self.branch = branch
        self.makeargs = makeargs

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        # does not support non-srcdir builds
        return self.get_srcdir(buildscript)

    def get_revision(self):
        return self.branch.branchname

    def do_start(self, buildscript):
        pass
    do_start.next_state = STATE_CHECKOUT
    do_start.error_states = []

    def skip_checkout(self, buildscript, last_state):
        # skip the checkout stage if the nonetwork flag is set
        return buildscript.config.nonetwork

    def do_checkout(self, buildscript):
        checkout(self, buildscript)
        check_build_policy(self, buildscript)
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
        perl = os.environ.get('PERL', 'perl')
        make = os.environ.get('MAKE', 'make')
        cmd = '%s Makefile.PL INSTALLDIRS=vendor PREFIX=%s %s' % (perl, buildscript.config.prefix, self.makeargs)
        buildscript.execute(cmd, cwd=builddir)
        buildscript.execute([make, 'LD_RUN_PATH='], cwd=builddir)
    do_build.next_state = STATE_INSTALL
    do_build.error_states = [STATE_FORCE_CHECKOUT]

    def skip_install(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_install(self, buildscript):
        buildscript.set_action('Installing', self)
        builddir = self.get_builddir(buildscript)
        make = os.environ.get('MAKE', 'make')
        buildscript.execute([make, 'install',
                             'PREFIX=%s' % buildscript.config.prefix],
                            cwd=builddir)
        buildscript.packagedb.add(self.name, self.get_revision() or '')
    do_install.next_state = Package.STATE_DONE
    do_install.error_states = []


def parse_perl(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')
    makeargs = ''
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')

    # override revision tag if requested.
    makeargs += ' ' + config.module_makeargs.get(id, config.makeargs)

    # Make some substitutions; do special handling of '${prefix}'
    p = re.compile('(\${prefix})')
    makeargs = p.sub(config.prefix, makeargs)
    
    dependencies, after, suggests = get_dependencies(node)
    branch = get_branch(node, repositories, default_repo)
    if config.module_checkout_mode.get(id):
        branch.checkout_mode = config.module_checkout_mode[id]

    return PerlModule(id, branch, makeargs,
            dependencies=dependencies, after=after,
            suggests=suggests)
register_module_type('perl', parse_perl)

