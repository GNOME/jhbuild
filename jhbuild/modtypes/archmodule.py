# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   archmodule.py: rules for building Arch modules.
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

import base
from base import AutogenModule
from base import register_module_type
from jhbuild.utils import arch
from jhbuild.errors import FatalError

class ArchModule(AutogenModule):
    ArchArchive = arch.ArchArchive
    type = 'arch'

    def __init__(self, version, checkoutdir=None,
                 autogenargs='', makeargs='', dependencies=[], suggests=[],
                 archive=None, archive_uri=None,
                 supports_non_srcdir_builds=True):
        AutogenModule.__init__(self,checkoutdir or branch,
                               autogenargs, makeargs,
                               dependencies, suggests,
                               supports_non_srcdir_builds)
        self.version     = version
        self.checkoutdir = checkoutdir
        self.archive     = archive
        self.archive_uri = archive_uri

    def get_srcdir(self, buildscript):
        return os.path.join(buildscript.config.checkoutroot,
                            self.checkoutdir or self.version)

    def get_builddir(self, buildscript):
        if buildscript.config.buildroot and \
               self.supports_non_srcdir_builds:
            d = buildscript.config.builddir_pattern \
                % (self.checkoutdir or self.version)
            return os.path.join(buildscript.config.buildroot, d)
        else:
            return self.get_srcdir(buildscript)

    def get_revision(self):
        # The convention for Subversion repositories is to put the head
        # branch under trunk/, branches under branches/foo/ and tags
        # under tags/bar/.
        # Use this to give a meaningful revision number.
        return self.version

    def do_checkout(self, buildscript):
        # make sure that the archive is registered
        arch.register(self.archive, self.archive_uri)
        archive = self.ArchArchive(self.archive,
                                   buildscript.config.checkoutroot)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        buildscript.set_action('Checking out', self)
        res = archive.update(buildscript, self.version,
                             buildscript.config.sticky_date,
                             checkoutdir=self.checkoutdir)

        if buildscript.config.nobuild:
            nextstate = self.STATE_DONE
        elif buildscript.config.alwaysautogen or \
                 not os.path.exists(os.path.join(builddir, 'Makefile')):
            nextstate = self.STATE_CONFIGURE
        elif buildscript.config.makeclean:
            nextstate = self.STATE_CLEAN
        else:
            nextstate = self.STATE_BUILD
        # did the checkout succeed?
        if res == 0 and os.path.exists(srcdir):
            return (nextstate, None, None)
        else:
            return (nextstate, 'could not update module',
                    [self.STATE_FORCE_CHECKOUT])

    def do_force_checkout(self, buildscript):
        # make sure that the archive is registered
        arch.register(self.archive, self.archive_uri)
        archive = self.ArchArchive(self.archive,
                                   buildscript.config.checkoutroot)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        if buildscript.config.nobuild:
            nextstate = self.STATE_DONE
        else:
            nextstate = self.STATE_CONFIGURE

        buildscript.set_action('Checking out', self)
        res = archive.checkout(buildscript, self.version,
                               buildscript.config.sticky_date,
                               checkoutdir=self.checkoutdir)
        if res == 0 and os.path.exists(srcdir):
            return (nextstate, None, None)
        else:
            return (nextstate, 'could not checkout module',
                    [self.STATE_FORCE_CHECKOUT])

def parse_archmodule(node, config, dependencies, suggests, root,
                     ArchModule=ArchModule):
    if root[0] != 'arch':
        raise FatalError('%s is not a ArchArchive' % root[1])
    archive = root[1]
    archive_uri = root[2]
    id = node.getAttribute('id')
    revision = id
    checkoutdir = None
    autogenargs = ''
    makeargs = ''
    supports_non_srcdir_builds = True
    if node.hasAttribute('version'):
        version = node.getAttribute('version')
    if node.hasAttribute('checkoutdir'):
        checkoutdir = node.getAttribute('checkoutdir')
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
    if node.hasAttribute('supports-non-srcdir-builds'):
        supports_non_srcdir_builds = \
            (node.getAttribute('supports-non-srcdir-builds') != 'no')

    # override revision tag if requested.
    full_version = '%s/%s' % (archive, version)
    if config.branches.has_key(full_version):
        archive, version = arch.split_name(config.branches[full_version])
        archie_uri = None

    autogenargs = config.module_autogenargs.get(revision, autogenargs)
    makeargs = config.module_makeargs.get(revision, makeargs)

    return ArchModule(version, checkoutdir,
                      autogenargs, makeargs,
                      archive=archive,
                      archive_uri=archive_uri,
                      dependencies=dependencies,
                      suggests=suggests,
                      supports_non_srcdir_builds=supports_non_srcdir_builds)
register_module_type('archmodule', parse_archmodule)
