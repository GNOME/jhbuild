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
     Package, DownloadableModule, get_dependencies, get_branch, register_module_type

__all__ = [ 'CMakeModule' ]

class CMakeModule(Package, DownloadableModule):
    """Base type for modules that use CMake build system."""
    type = 'cmake'

    PHASE_CHECKOUT = DownloadableModule.PHASE_CHECKOUT
    PHASE_FORCE_CHECKOUT = DownloadableModule.PHASE_FORCE_CHECKOUT
    PHASE_CONFIGURE = 'configure'
    PHASE_BUILD = 'build'
    PHASE_DIST = 'dist'
    PHASE_INSTALL = 'install'

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

    def skip_configure(self, buildscript, last_phase):
        return buildscript.config.nobuild

    def do_configure(self, buildscript):
        buildscript.set_action(_('Configuring'), self)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        if not os.path.exists(builddir):
            os.mkdir(builddir)
        prefix = os.path.expanduser(buildscript.config.prefix)
        cmd = ['cmake', '-DCMAKE_INSTALL_PREFIX=%s' % prefix,
               '-DLIB_INSTALL_DIR=%s' % buildscript.config.libdir,
               '-Dlibdir=%s' % buildscript.config.libdir,
               srcdir]
        if os.path.exists(os.path.join(builddir, 'CMakeCache.txt')):
            # remove that file, as it holds the result of a previous cmake
            # configure run, and would be reused unconditionnaly
            # (cf https://bugzilla.gnome.org/show_bug.cgi?id=621194)
            os.unlink(os.path.join(builddir, 'CMakeCache.txt'))
        buildscript.execute(cmd, cwd = builddir, extra_env = self.extra_env)
    do_configure.depends = [PHASE_CHECKOUT]
    do_configure.error_phases = [PHASE_FORCE_CHECKOUT]

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        builddir = self.get_builddir(buildscript)
        buildscript.execute(os.environ.get('MAKE', 'make'), cwd = builddir,
                extra_env = self.extra_env)
    do_build.depends = [PHASE_CONFIGURE]
    do_build.error_phases = [PHASE_FORCE_CHECKOUT]

    def do_dist(self, buildscript):
        buildscript.set_action(_('Creating tarball for'), self)
        cmd = '%s package_source' % os.environ.get('MAKE', 'make')
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                extra_env = self.extra_env)
    do_dist.depends = [PHASE_CONFIGURE]
    do_dist.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        builddir = self.get_builddir(buildscript)
        buildscript.execute([os.environ.get('MAKE', 'make'), 'install'],
                cwd = builddir,
                extra_env = self.extra_env)
        buildscript.packagedb.add(self.name, self.get_revision() or '')
    do_install.depends = [PHASE_BUILD]

    def xml_tag_and_attrs(self):
        return 'cmake', [('id', 'name', None)]


def parse_cmake(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')
    dependencies, after, suggests = get_dependencies(node)
    branch = get_branch(node, repositories, default_repo, config)

    return CMakeModule(id, branch, dependencies = dependencies, after = after,
            suggests = suggests)

register_module_type('cmake', parse_cmake)

