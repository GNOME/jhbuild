# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   distutils.py: Python distutils module type definitions.
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
import sys

from jhbuild.utils import _
from jhbuild.modtypes import \
     Package, DownloadableModule, register_module_type

__all__ = [ 'DistutilsModule' ]

class DistutilsModule(Package, DownloadableModule):
    """Base type for modules that are distributed with a Python
    Distutils style setup.py."""
    type = 'distutils'

    PHASE_CHECKOUT = DownloadableModule.PHASE_CHECKOUT
    PHASE_FORCE_CHECKOUT = DownloadableModule.PHASE_FORCE_CHECKOUT
    PHASE_BUILD = 'build'
    PHASE_INSTALL = 'install'

    def __init__(self, name, branch=None, supports_non_srcdir_builds = True):
        Package.__init__(self, name, branch=branch)
        self.supports_non_srcdir_builds = supports_non_srcdir_builds
        self.supports_install_destdir = True
        self.python = os.environ.get('PYTHON', 'python2')

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            d = buildscript.config.builddir_pattern % (
                self.branch.checkoutdir or self.branch.get_module_basename())
            return os.path.join(buildscript.config.buildroot, d)
        else:
            return self.get_srcdir(buildscript)

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        cmd = [self.python, 'setup.py', 'build']
        if srcdir != builddir:
            cmd.extend(['--build-base', builddir])
        buildscript.execute(cmd, cwd = srcdir, extra_env = self.extra_env)
    do_build.depends = [PHASE_CHECKOUT]
    do_build.error_phase = [PHASE_FORCE_CHECKOUT]

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        destdir = self.prepare_installroot(buildscript)
        cmd = [self.python, 'setup.py']
        if srcdir != builddir:
            cmd.extend(['build', '--build-base', builddir])
        cmd.extend(['install', 
                    '--prefix', buildscript.config.prefix,
                    '--root', destdir])
        buildscript.execute(cmd, cwd = srcdir, extra_env = self.extra_env)
        self.process_install(buildscript, self.get_revision())
    do_install.depends = [PHASE_BUILD]

    @property
    def extra_env(self):
        # distutils was removed from the stdlib in 3.12.
        if sys.version_info.major > 3 or sys.version_info.minor >= 12:
            return super().extra_env

        return {
            **(super().extra_env or {}),
            # Setuptools v60+ changes the way it builds wheels (prefix/local/lib)
            # See https://github.com/pypa/setuptools/issues/2896
            # See https://gitlab.gnome.org/GNOME/jhbuild/-/issues/286
            'SETUPTOOLS_USE_DISTUTILS': 'stdlib',
        }

    def xml_tag_and_attrs(self):
        return 'distutils', [('id', 'name', None),
                             ('supports-non-srcdir-builds',
                              'supports_non_srcdir_builds', True)]


def parse_distutils(node, config, uri, repositories, default_repo):
    instance = DistutilsModule.parse_from_xml(node, config, uri, repositories, default_repo)

    if node.hasAttribute('supports-non-srcdir-builds'):
        instance.supports_non_srcdir_builds = \
            (node.getAttribute('supports-non-srcdir-builds') != 'no')

    if node.hasAttribute('python3'):
        instance.python = os.environ.get('PYTHON3', 'python3')

    return instance

register_module_type('distutils', parse_distutils)

