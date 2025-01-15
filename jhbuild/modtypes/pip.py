# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2024 Fabian Wüthrich
#
#   pip.py: Python pip module type definitions.
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
import glob
import sys

from jhbuild.modtypes import Package, DownloadableModule, register_module_type
from jhbuild.utils import _

__all__ = ['PipModule']


class PipModule(Package, DownloadableModule):
    """Base type for modules that are distributed on Python Package Index."""
    type = 'pip'

    PHASE_CHECKOUT = DownloadableModule.PHASE_CHECKOUT
    PHASE_FORCE_CHECKOUT = DownloadableModule.PHASE_FORCE_CHECKOUT
    PHASE_BUILD = 'build'
    PHASE_INSTALL = 'install'
    COMMON_PIP_ARGS = ['--disable-pip-version-check', '--no-input', '--no-deps']

    def __init__(self, name, branch=None):
        Package.__init__(self, name, branch=branch)
        self.supports_non_srcdir_builds = True
        self.force_non_srcdir_builds = True
        self.supports_install_destdir = True
        self.pip_exe = [sys.executable, '-m', 'pip']

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        builddir = self.get_srcdir(buildscript)
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            d = buildscript.config.builddir_pattern % (
                    self.branch.checkoutdir or self.branch.get_module_basename())
            builddir = os.path.join(buildscript.config.buildroot, d)
        if self.force_non_srcdir_builds and builddir == self.get_srcdir(buildscript):
            builddir = os.path.join(builddir, 'build')
        return builddir

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        cmd = self.pip_exe + ['wheel'] + self.COMMON_PIP_ARGS
        cmd += ['--wheel-dir', self.get_builddir(buildscript), self.get_srcdir(buildscript)]
        buildscript.execute(cmd)

    do_build.depends = [PHASE_CHECKOUT]
    do_build.error_phase = [PHASE_FORCE_CHECKOUT]

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        wheels = glob.glob(os.path.join(self.get_builddir(buildscript), "*.whl"))
        assert len(wheels) == 1  # only the module wheel should be in the build dir
        destdir = self.prepare_installroot(buildscript)
        cmd = self.pip_exe + ['install'] + self.COMMON_PIP_ARGS
        cmd += ['--no-index',
                '--ignore-installed',
                '--prefix', buildscript.config.prefix,
                '--root', destdir,
                wheels[0]]
        buildscript.execute(cmd)
        self.process_install(buildscript, self.get_revision())

    do_install.depends = [PHASE_BUILD]

    def xml_tag_and_attrs(self):
        return 'pip', [('id', 'name', None)]


def parse_pip(node, config, uri, repositories, default_repo):
    instance = PipModule.parse_from_xml(node, config, uri, repositories, default_repo)
    return instance


register_module_type('pip', parse_pip)
