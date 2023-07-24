# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2023 Igalia S.L.
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

import logging
import os
import sys
import subprocess
import sysconfig

build_available = True
installer_available = True

try:
    import build
except ImportError:
    build_available = False

try:
    import installer
except ImportError:
    installer_available = False

from jhbuild.errors import BuildStateError
from jhbuild.modtypes import Package, DownloadableModule, register_module_type
from jhbuild.utils import _

__all__ = ['PyprojectModule']

class PyprojectModule(Package, DownloadableModule):
    type = 'pyproject'

    def __init__(self, name, branch=None,
                 skip_install_phase=False):
        Package.__init__(self, name, branch=branch)
        DownloadableModule.__init__(self)
        self.supports_non_srcdir_builds = True
        self.skip_install_phase = skip_install_phase
        self.force_non_srcdir_builds = True
        self.supports_install_destdir = True
        self.built_wheel_file = None

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

        if not build_available:
            raise BuildStateError(_('Python\'s `build` module not available'))

        project = build.ProjectBuilder(self.get_srcdir(buildscript))
        # TODO: Exception handling
        self.built_wheel_file = project.build('wheel', self.get_builddir(buildscript))

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)

        if not installer_available:
            raise BuildStateError(_('Python\'s `installer` module not available'))

        destdir = self.prepare_installroot(buildscript)
        prefix = os.path.expanduser(buildscript.config.prefix)
        destination = installer.destinations.SchemeDictionaryDestination(
            sysconfig.get_paths('posix_user', {'userbase': prefix}, True),
            interpreter=sys.executable,
            script_kind="posix",
            destdir=destdir,
        )

        with installer.sources.WheelFile.open(self.built_wheel_file) as wheel:
            installer.install(wheel, destination, additional_metadata={})

        self.process_install(buildscript, self.get_revision())
    do_install.depends = ['build']

def parse_pyproject(node, config, uri, repositories, default_repo):
    instance = PyprojectModule.parse_from_xml(node, config, uri, repositories, default_repo)

    # FIXME: Add python3 module deps
    # instance.dependencies += []

    if node.hasAttribute('skip-install'):
        skip_install = node.getAttribute('skip-install')
        if skip_install.lower() in ('true', 'yes'):
            instance.skip_install_phase = True
        else:
            instance.skip_install_phase = False

    return instance


register_module_type('pyproject', parse_pyproject)
