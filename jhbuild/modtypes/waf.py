# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007  Gustavo Carneiro
# Copyright (C) 2008  Frederic Peters
#
#   waf.py: waf module type definitions.
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

from jhbuild.errors import FatalError, BuildStateError, CommandError
from jhbuild.modtypes import \
     Package, get_dependencies, get_branch, register_module_type
from jhbuild.commands.sanitycheck import inpath

__all__ = [ 'WafModule' ]

class WafModule(Package):
    '''Base type for modules that are distributed with a WAF script.'''
    type = 'waf'

    STATE_CHECKOUT       = 'checkout'
    STATE_FORCE_CHECKOUT = 'force_checkout'
    STATE_CLEAN          = 'clean'
    STATE_CONFIGURE      = 'configure'
    STATE_BUILD          = 'build'
    STATE_CHECK          = 'check'
    STATE_DIST           = 'dist'
    STATE_INSTALL        = 'install'

    def __init__(self, name, branch, dependencies=[], after=[], suggests=[],
                 waf_cmd='waf'):
        Package.__init__(self, name, dependencies, after, suggests)
        self.branch = branch
        self.waf_cmd = waf_cmd

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
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
        # skip if nobuild is set.
        if buildscript.config.nobuild:
            return True

        # don't skip this stage if we got here from one of the
        # following states:
        if last_state in [self.STATE_FORCE_CHECKOUT,
                          self.STATE_CLEAN,
                          self.STATE_BUILD,
                          self.STATE_INSTALL]:
            return False

        # skip if the .lock-wscript file exists and we don't have the
        # alwaysautogen flag turned on:
        builddir = self.get_builddir(buildscript)
        return (os.path.exists(os.path.join(builddir, '.lock-wscript')) and
                not buildscript.config.alwaysautogen)

    def do_configure(self, buildscript):
        builddir = self.get_builddir(buildscript)
        buildscript.set_action(_('Configuring'), self)
        if not inpath(self.waf_cmd, os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('Missing waf, try jhbuild -m bootstrap buildone waf'))
        if buildscript.config.buildroot and not os.path.exists(builddir):
            os.makedirs(builddir)
        cmd = [self.waf_cmd, 'configure', '--prefix', buildscript.config.prefix]
        if buildscript.config.use_lib64:
            cmd += ["--libdir", os.path.join(buildscript.config.prefix, "lib64")]
        buildscript.execute(cmd, cwd=builddir)
    do_configure.next_state = STATE_CLEAN
    do_configure.error_states = [STATE_FORCE_CHECKOUT]

    def skip_clean(self, buildscript, last_state):
        return (not buildscript.config.makeclean or
                buildscript.config.nobuild)

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
        cmd = [self.waf_cmd, 'clean']
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript))
    do_clean.next_state = STATE_BUILD
    do_clean.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_build(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        cmd = [self.waf_cmd, 'build']
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript))
    do_build.next_state = STATE_CHECK
    do_build.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_check(self, buildscript, last_state):
        if not buildscript.config.module_makecheck.get(self.name, buildscript.config.makecheck):
            return True
        if buildscript.config.forcecheck:
            return False
        if buildscript.config.nobuild:
            return True
        return False

    def do_check(self, buildscript):
        buildscript.set_action(_('Checking'), self)
        cmd = [self.waf_cmd, 'check']
        try:
            buildscript.execute(cmd, cwd=self.get_builddir(buildscript))
        except CommandError:
            if not buildscript.config.makecheck_advisory:
                raise
    do_check.next_state = STATE_DIST
    do_check.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_dist(self, buildscript, last_state):
        return not (buildscript.config.makedist or buildscript.config.makedistcheck)

    def do_dist(self, buildscript):
        buildscript.set_action(_('Creating tarball for'), self)
        if buildscript.config.makedistcheck:
            cmd = [self.waf_cmd, 'distcheck']
        else:
            cmd = [self.waf_cmd, 'dist']
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript))
    do_dist.next_state = STATE_INSTALL
    do_dist.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_install(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        cmd = [self.waf_cmd, 'install']
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript))
        buildscript.packagedb.add(self.name, self.get_revision() or '')
    do_install.next_state = Package.STATE_DONE
    do_install.error_states = []


def parse_waf(node, config, uri, repositories, default_repo):
    module_id = node.getAttribute('id')
    waf_cmd = 'waf'
    if node.hasAttribute('waf-command'):
        waf_cmd = node.getAttribute('waf-command')

    # override revision tag if requested.
    dependencies, after, suggests = get_dependencies(node)
    branch = get_branch(node, repositories, default_repo)
    if config.module_checkout_mode.get(module_id):
        branch.checkout_mode = config.module_checkout_mode[module_id]

    return WafModule(module_id, branch, dependencies=dependencies, after=after,
            suggests=suggests, waf_cmd=waf_cmd)

register_module_type('waf', parse_waf)
