# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2008  David Schleef
#
#   ant.py: ant module type definitions.
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
     Package, DownloadableModule, get_dependencies, get_branch, register_module_type
from jhbuild.commands.sanitycheck import inpath

__all__ = [ 'AntModule' ]

class AntModule(Package, DownloadableModule):
    """Base type for modules that are built with Ant."""
    type = 'ant'

    PHASE_CHECKOUT = DownloadableModule.PHASE_CHECKOUT
    PHASE_FORCE_CHECKOUT = DownloadableModule.PHASE_FORCE_CHECKOUT
    PHASE_BUILD = 'build'
    PHASE_INSTALL = 'install'

    def __init__(self, name, branch,
                 dependencies=[], after=[],
                 supports_non_srcdir_builds=False):
        Package.__init__(self, name, dependencies, after)
        self.branch = branch
        self.supports_non_srcdir_builds = supports_non_srcdir_builds

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            d = buildscript.config.builddir_pattern % (
                self.branch.checkoutdir or self.branch.get_module_basename())
            return os.path.join(buildscript.config.buildroot, d)
        else:
            return self.get_srcdir(buildscript)

    def get_revision(self):
        return self.branch.branchname

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        ant = os.environ.get('ANT', 'ant')
        if not inpath(ant, os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('Missing ant build tool'))
        cmd = [ant]
        #if srcdir != builddir:
        #    cmd.extend(['--build-base', builddir])
        buildscript.execute(cmd, cwd=srcdir)
    do_build.depends = [PHASE_CHECKOUT]
    do_build.error_phases = [PHASE_FORCE_CHECKOUT]

    def do_install(self, buildscript):
        # Quoting David Schleef:
        #   "It's not clear to me how to install a typical
        #    ant-based project, so I left that out."
        #    -- http://bugzilla.gnome.org/show_bug.cgi?id=537037
        buildscript.set_action(_('Installing'), self)
        buildscript.packagedb.add(self.name, self.get_revision() or '')
    do_install.depends = [PHASE_BUILD]

    def xml_tag_and_attrs(self):
        return 'ant', [('id', 'name', None),
                       ('supports-non-srcdir-builds',
                        'supports_non_srcdir_builds', False)]


def parse_ant(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')
    supports_non_srcdir_builds = False

    if node.hasAttribute('supports-non-srcdir-builds'):
        supports_non_srcdir_builds = \
            (node.getAttribute('supports-non-srcdir-builds') != 'no')
    dependencies, after, suggests = get_dependencies(node)
    branch = get_branch(node, repositories, default_repo)

    return AntModule(id, branch,
                           dependencies=dependencies, after=after,
                           supports_non_srcdir_builds=supports_non_srcdir_builds)

register_module_type('ant', parse_ant)
