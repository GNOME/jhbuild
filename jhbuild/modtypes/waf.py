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
     Package, DownloadableModule, register_module_type
from jhbuild.commands.sanitycheck import inpath

__all__ = [ 'WafModule' ]

class WafModule(Package, DownloadableModule):
    '''Base type for modules that are distributed with a WAF script.'''
    type = 'waf'

    PHASE_CHECKOUT = DownloadableModule.PHASE_CHECKOUT
    PHASE_FORCE_CHECKOUT = DownloadableModule.PHASE_FORCE_CHECKOUT
    PHASE_CLEAN          = 'clean'
    PHASE_CONFIGURE      = 'configure'
    PHASE_BUILD          = 'build'
    PHASE_CHECK          = 'check'
    PHASE_DIST           = 'dist'
    PHASE_INSTALL        = 'install'

    def __init__(self, name, branch=None, waf_cmd='./waf'):
        Package.__init__(self, name, branch=branch)
        self.waf_cmd = waf_cmd
        self.supports_install_destdir = True

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        return self.get_srcdir(buildscript)

    def skip_configure(self, buildscript, last_phase):
        # don't skip this stage if we got here from one of the
        # following phases:
        if last_phase in [self.PHASE_FORCE_CHECKOUT,
                          self.PHASE_CLEAN,
                          self.PHASE_BUILD,
                          self.PHASE_INSTALL]:
            return False

        if buildscript.config._internal_noautogen:
            return True

        return False

    def do_configure(self, buildscript):
        builddir = self.get_builddir(buildscript)
        buildscript.set_action(_('Configuring'), self)
        if buildscript.config.buildroot and not os.path.exists(builddir):
            os.makedirs(builddir)
        cmd = [self.waf_cmd, 'configure', '--prefix', buildscript.config.prefix]
        if buildscript.config.use_lib64:
            cmd += ["--libdir", os.path.join(buildscript.config.prefix, "lib64")]
        buildscript.execute(cmd, cwd=builddir)
    do_configure.depends = [PHASE_CHECKOUT]
    do_configure.error_phases = [PHASE_FORCE_CHECKOUT]

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
        cmd = [self.waf_cmd, 'clean']
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript))
    do_clean.depends = [PHASE_CONFIGURE]
    do_clean.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        cmd = [self.waf_cmd, 'build']
        if self.supports_parallel_build:
            cmd.append('-j')
            cmd.append('%s' % (buildscript.config.jobs, ))
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript))
    do_build.depends = [PHASE_CONFIGURE]
    do_build.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def skip_check(self, buildscript, last_phase):
        if self.name in buildscript.config.module_makecheck:
            return not buildscript.config.module_makecheck[self.name]
        if 'check' not in buildscript.config.build_targets:
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
    do_check.depends = [PHASE_BUILD]
    do_check.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_dist(self, buildscript):
        buildscript.set_action(_('Creating tarball for'), self)
        if buildscript.config.makedistcheck:
            cmd = [self.waf_cmd, 'distcheck']
        else:
            cmd = [self.waf_cmd, 'dist']
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript))
    do_dist.depends = [PHASE_BUILD]
    do_dist.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        destdir = self.prepare_installroot(buildscript)
        cmd = [self.waf_cmd, 'install', '--destdir', destdir]
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript))
        self.process_install(buildscript, self.get_revision())
    do_install.depends = [PHASE_BUILD]

    def xml_tag_and_attrs(self):
        return 'waf', [('id', 'name', None),
                       ('waf-command', 'waf_cmd', 'waf')]


def parse_waf(node, config, uri, repositories, default_repo):
    instance = WafModule.parse_from_xml(node, config, uri, repositories, default_repo)

    if node.hasAttribute('waf-command'):
        instance.waf_cmd = node.getAttribute('waf-command')

    return instance

register_module_type('waf', parse_waf)
