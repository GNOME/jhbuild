# jhbuild - a tool to ease building collections of source packages
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

from jhbuild.errors import CommandError
from jhbuild.modtypes import \
     Package, DownloadableModule, register_module_type
from jhbuild.utils import _

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

    def __init__(self, name, branch=None, waf_cmd='./waf', python_cmd='python'):
        Package.__init__(self, name, branch=branch)
        self.waf_cmd = waf_cmd
        self.python_cmd = python_cmd
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

        # skip if the .lock-wscript file exists and we don't have the
        # alwaysautogen flag turned on:
        builddir = self.get_builddir(buildscript)
        return (os.path.exists(os.path.join(builddir, '.lock-wscript')) and
                not buildscript.config.alwaysautogen)

    def do_configure(self, buildscript):
        builddir = self.get_builddir(buildscript)
        buildscript.set_action(_('Configuring'), self)
        if buildscript.config.buildroot and not os.path.exists(builddir):
            os.makedirs(builddir)
        cmd = [self.waf_cmd, 'configure', '--prefix', buildscript.config.prefix]
        buildscript.execute(cmd, cwd=builddir, extra_env={'PYTHON': self.python_cmd})
    do_configure.depends = [PHASE_CHECKOUT]
    do_configure.error_phases = [PHASE_FORCE_CHECKOUT]

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
        cmd = [self.waf_cmd, 'clean']
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript),
                            extra_env={'PYTHON': self.python_cmd})
    do_clean.depends = [PHASE_CONFIGURE]
    do_clean.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        cmd = [self.waf_cmd, 'build']
        if self.supports_parallel_build:
            cmd.append('-j')
            cmd.append('%s' % (buildscript.config.jobs, ))
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript),
                            extra_env={'PYTHON': self.python_cmd})
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
            buildscript.execute(cmd, cwd=self.get_builddir(buildscript),
                                extra_env={'PYTHON': self.python_cmd})
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
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript),
                            extra_env={'PYTHON': self.python_cmd})
    do_dist.depends = [PHASE_BUILD]
    do_dist.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        destdir = self.prepare_installroot(buildscript)
        cmd = [self.waf_cmd, 'install', '--destdir', destdir]
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript),
                            extra_env={'PYTHON': self.python_cmd})
        self.process_install(buildscript, self.get_revision())
    do_install.depends = [PHASE_BUILD]

    def xml_tag_and_attrs(self):
        return 'waf', [('id', 'name', None),
                       ('waf-command', 'waf_cmd', 'waf')]


def parse_waf(node, config, uri, repositories, default_repo):
    instance = WafModule.parse_from_xml(node, config, uri, repositories, default_repo)

    if node.hasAttribute('waf-command'):
        instance.waf_cmd = node.getAttribute('waf-command')

    if node.hasAttribute('python-command'):
        instance.python_cmd = node.getAttribute('python-command')

    return instance

register_module_type('waf', parse_waf)
