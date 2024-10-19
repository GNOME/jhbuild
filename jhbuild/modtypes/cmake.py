# jhbuild - a tool to ease building collections of source packages
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
import shutil

from jhbuild.errors import CommandError
from jhbuild.modtypes import \
     Package, DownloadableModule, register_module_type, MakeModule, NinjaModule
from jhbuild.modtypes.autotools import collect_args
from jhbuild.utils import inpath, _

__all__ = [ 'CMakeModule' ]

class CMakeModule(MakeModule, NinjaModule, DownloadableModule):
    """Base type for modules that use CMake build system."""
    type = 'cmake'

    PHASE_CHECKOUT = DownloadableModule.PHASE_CHECKOUT
    PHASE_FORCE_CHECKOUT = DownloadableModule.PHASE_FORCE_CHECKOUT
    PHASE_CONFIGURE = 'configure'
    PHASE_BUILD = 'build'
    PHASE_DIST = 'dist'
    PHASE_INSTALL = 'install'

    def __init__(self, name, branch=None,
                 cmakeargs='', makeargs='', ninjaargs='',
                 skip_install_phase=False):
        MakeModule.__init__(self, name, branch=branch, makeargs=makeargs)
        NinjaModule.__init__(self, name, branch=branch, ninjaargs=ninjaargs)
        self.cmakeargs = cmakeargs
        self.supports_non_srcdir_builds = True
        self.skip_install_phase = skip_install_phase
        self.force_non_srcdir_builds = False
        self.supports_install_destdir = True
        self.use_ninja = True
        self.cmakedir = None

    def eval_args(self, args):
        args = Package.eval_args(self, args)
        args = args.replace('${libsuffix}', '')
        return args

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

    def get_cmakeargs(self):
        args = '%s %s' % (self.cmakeargs,
                          self.config.module_cmakeargs.get(
                              self.name, self.config.cmakeargs))
        return self.eval_args(args)

    def do_configure(self, buildscript):
        buildscript.set_action(_('Configuring'), self)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        if os.path.exists(builddir):
            try:
                # Clear CMake files so we get a clean configure.
                os.unlink(os.path.join(builddir, 'CMakeCache.txt'))
                shutil.rmtree(os.path.join(builddir, 'CMakeFiles'))
            except EnvironmentError:
                pass
        else:
            os.makedirs(builddir)
        prefix = os.path.expanduser(buildscript.config.prefix)
        if not inpath('cmake', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'cmake')
        baseargs = '-DCMAKE_INSTALL_PREFIX=%s -DCMAKE_INSTALL_LIBDIR=lib' % prefix
        cmakeargs = self.get_cmakeargs()
        if self.use_ninja:
            baseargs += ' -G Ninja'
        # CMake on Windows generates VS projects or NMake makefiles by default.
        # When using MSYS "MSYS Makefiles" is the best guess. "Unix Makefiles"
        # and "MinGW Makefiles" could also work (each is a bit different).
        if os.name == 'nt' and os.getenv("MSYSCON") and '-G' not in cmakeargs:
            baseargs += ' -G "MSYS Makefiles"'
        cmakedir = os.path.join(srcdir, self.cmakedir) if self.cmakedir else srcdir
        cmd = 'cmake %s %s %s' % (baseargs, cmakeargs, cmakedir)
        buildscript.execute(cmd, cwd = builddir, extra_env = self.extra_env)
    do_configure.depends = [PHASE_CHECKOUT]
    do_configure.error_phases = [PHASE_FORCE_CHECKOUT]

    def skip_configure(self, buildscript, last_phase):
        # don't skip this stage if we got here from one of the
        # following phases:
        if last_phase in [self.PHASE_FORCE_CHECKOUT,
                          self.PHASE_BUILD,
                          self.PHASE_INSTALL]:
            return False

        if buildscript.config.alwaysautogen:
            return False

        builddir = self.get_builddir(buildscript)
        if not builddir:
            return False

        cmakecache_path = os.path.join(builddir, 'CMakeCache.txt')
        if not os.path.exists(cmakecache_path):
            return False

        return True

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
        if self.use_ninja:
            self.ninja(buildscript, 'clean')
        else:
            self.make(buildscript, 'clean')
    do_clean.depends = [PHASE_CONFIGURE]
    do_clean.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        if self.use_ninja:
            self.ninja(buildscript)
        else:
            self.make(buildscript)
    do_build.depends = [PHASE_CONFIGURE]
    do_build.error_phases = [PHASE_FORCE_CHECKOUT]

    def do_dist(self, buildscript):
        buildscript.set_action(_('Creating tarball for'), self)
        if self.use_ninja:
            self.ninja(buildscript, 'package_source')
        else:
            self.make(buildscript, 'package_source')
    do_dist.depends = [PHASE_CONFIGURE]
    do_dist.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def skip_install(self, buildscript, last_phase):
        return self.config.noinstall or self.skip_install_phase

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        destdir = self.prepare_installroot(buildscript)
        if self.use_ninja:
            self.ninja(buildscript, 'install', env={'DESTDIR': destdir})
        else:
            self.make(buildscript, 'install DESTDIR={}'.format(destdir))
        self.process_install(buildscript, self.get_revision())
    do_install.depends = [PHASE_BUILD]

    def xml_tag_and_attrs(self):
        return 'cmake', [('id', 'name', None),
                         ('skip-install', 'skip_install_phase', False),
                         ('use-ninja', 'use_ninja', True),
                         ('cmakedir', 'cmakedir', None),
                         ('supports-non-srcdir-builds',
                          'supports_non_srcdir_builds', True),
                         ('force-non-srcdir-builds',
                          'force_non_srcdir_builds', False)]


def parse_cmake(node, config, uri, repositories, default_repo):
    instance = CMakeModule.parse_from_xml(node, config, uri, repositories, default_repo)

    instance.cmakeargs = collect_args(instance, node, 'cmakeargs')
    instance.makeargs = collect_args(instance, node, 'makeargs')
    instance.ninjaargs = collect_args(instance, node, 'ninjaargs')

    if node.hasAttribute('skip-install'):
        skip_install = node.getAttribute('skip-install')
        if skip_install.lower() in ('true', 'yes'):
            instance.skip_install_phase = True
        else:
            instance.skip_install_phase = False
    if node.hasAttribute('supports-non-srcdir-builds'):
        instance.supports_non_srcdir_builds = \
                (node.getAttribute('supports-non-srcdir-builds') != 'no')
    if node.hasAttribute('force-non-srcdir-builds'):
        instance.force_non_srcdir_builds = \
                (node.getAttribute('force-non-srcdir-builds') != 'no')
    if node.hasAttribute('use-ninja'):
        use_ninja = node.getAttribute('use-ninja')
        if use_ninja.lower() in ('false', 'no'):
            instance.use_ninja = False
    if node.hasAttribute('cmakedir'):
        instance.cmakedir = node.getAttribute('cmakedir')

    instance.dependencies.append('cmake')
    if instance.use_ninja:
        instance.dependencies.append('ninja')
    else:
        instance.dependencies.append(instance.get_makecmd(config))

    return instance

register_module_type('cmake', parse_cmake)
