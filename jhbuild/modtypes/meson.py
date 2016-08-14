# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   meson.py: meson module type definitions.
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

from jhbuild.errors import BuildStateError, CommandError
from jhbuild.modtypes import \
     Package, DownloadableModule, register_module_type, MakeModule
from jhbuild.modtypes.autotools import collect_args
from jhbuild.commands.sanitycheck import inpath

__all__ = [ 'MesonModule' ]

class MesonModule(MakeModule, DownloadableModule):
    """Base type for modules that use Meson build system."""
    type = 'meson'

    PHASE_CHECKOUT = DownloadableModule.PHASE_CHECKOUT
    PHASE_FORCE_CHECKOUT = DownloadableModule.PHASE_FORCE_CHECKOUT
    PHASE_CLEAN = 'clean'
    PHASE_CONFIGURE = 'configure'
    PHASE_BUILD = 'build'
    PHASE_INSTALL = 'install'

    def __init__(self, name, branch=None,
                 mesonargs='', makeargs='',
                 skip_install_phase=False):
        MakeModule.__init__(self, name, branch=branch, makeargs=makeargs)
        self.mesonargs = mesonargs
        self.supports_non_srcdir_builds = True
        self.skip_install_phase = skip_install_phase
        self.force_non_srcdir_builds = True
        self.supports_install_destdir = True

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

    def get_mesonargs(self):
        args = '%s %s' % (self.mesonargs,
                          self.config.module_mesonargs.get(
                              self.name, self.config.mesonargs))
        return self.eval_args(args)

    def do_configure(self, buildscript):
        buildscript.set_action(_('Configuring'), self)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        if not os.path.exists(builddir):
            os.makedirs(builddir)
        prefix = os.path.expanduser(buildscript.config.prefix)
        if not inpath('meson', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'meson')
        baseargs = '--prefix %s' % prefix
        mesonargs = self.get_mesonargs()
        cmd = 'meson %s %s %s' % (baseargs, mesonargs, srcdir)
        buildscript.execute(cmd, cwd=builddir, extra_env=self.extra_env)
    do_configure.depends = [PHASE_CHECKOUT]
    do_configure.error_phases = [PHASE_FORCE_CHECKOUT]

    def skip_configure(self, buildscript, last_phase):
        # don't skip this stage if we got here from one of the
        # following phases:
        if last_phase in [self.PHASE_FORCE_CHECKOUT,
                          self.PHASE_CLEAN,
                          self.PHASE_BUILD,
                          self.PHASE_INSTALL]:
            return False

        if buildscript.config.alwaysautogen:
            return False

        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        meson_marker_path = os.path.join(builddir, 'meson-private')
        if not os.path.exists(meson_marker_path):
            return False

        return True

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
        builddir = self.get_builddir(buildscript)
        buildscript.execute('ninja clean', cwd=builddir, extra_env=self.extra_env)
    do_clean.depends = [PHASE_CONFIGURE]
    do_clean.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        builddir = self.get_builddir(buildscript)
        buildscript.execute('ninja', cwd=builddir, extra_env=self.extra_env)
    do_build.depends = [PHASE_CONFIGURE]
    do_build.error_phases = [PHASE_FORCE_CHECKOUT]

    def skip_install(self, buildscript, last_phase):
        return self.config.noinstall or self.skip_install_phase

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        builddir = self.get_builddir(buildscript)
        destdir = self.prepare_installroot(buildscript)
        extra_env = (self.extra_env or {}).copy()
        extra_env['DESTDIR'] = destdir
        buildscript.execute('ninja install', cwd=builddir, extra_env=extra_env)
        self.process_install(buildscript, self.get_revision())
    do_install.depends = [PHASE_BUILD]

    def xml_tag_and_attrs(self):
        return 'meson', [('id', 'name', None),
                         ('skip-install', 'skip_install_phase', False)]


def parse_meson(node, config, uri, repositories, default_repo):
    instance = MesonModule.parse_from_xml(node, config, uri, repositories, default_repo)

    instance.dependencies += ['meson', instance.get_makecmd(config)]

    instance.mesonargs = collect_args(instance, node, 'mesonargs')
    instance.makeargs = collect_args(instance, node, 'makeargs')

    if node.hasAttribute('skip-install'):
        skip_install = node.getAttribute('skip-install')
        if skip_install.lower() in ('true', 'yes'):
            instance.skip_install_phase = True
        else:
            instance.skip_install_phase = False

    return instance

register_module_type('meson', parse_meson)
