# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   gdbmodule.py: module type definitions for the GNU Debugger
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
import string

import base
from jhbuild.utils import cvs

class GDBCVSRoot(cvs.CVSRoot):
    '''A class to handle CVS update operations in the GDB CVS
    repository.'''

    def getcheckoutdir(self, module, checkoutdir=None):
        '''Override CVSRoot.getcheckoutdir to return GDB''s top-level
        directory, src.'''
        return os.path.join(self.localroot, 'src')

    def update(self, buildscript, module, revision=None, date=None,
               checkoutdir=None):
        '''Override CVSRoot.update to remove the -d option to cvs
        update.  When run in GDB''s top-level directory, src, cvs
        update -d will checkout all modules in the repository rather
        than simply updating gdb and its requirements.'''
        dir = self.getcheckoutdir(module, checkoutdir)
        if not os.path.exists(dir):
            return self.checkout(buildscript, module,
                                 revision, date, checkoutdir)

        os.chdir(dir)
        cmd = 'cvs -z3 -q -d %s update -P ' % self.cvsroot

        if revision:
            cmd += '-r %s ' % revision
        if date:
            cmd += '-D "%s" ' % date
        if not (revision or date):
            cmd = cmd + '-A '

        cmd += '.'

        return buildscript.execute(cmd, 'cvs')

class GDBModule(base.CVSModule):
    CVSRoot = GDBCVSRoot
    def __init__(self,
                 cvsmodule,
                 checkoutdir=None,
                 revision=None,
                 autogenargs=None,
                 makeargs=None,
                 dependencies=[],
                 suggests=[],
                 cvsroot=None,
                 supports_non_srcdir_builds=True):
        base.CVSModule.__init__(self,
                                cvsmodule,
                                checkoutdir=checkoutdir,
                                revision=revision,
                                autogenargs=autogenargs,
                                makeargs=makeargs,
                                dependencies=dependencies,
                                suggests=suggests,
                                cvsroot=cvsroot,
                                supports_non_srcdir_builds=supports_non_srcdir_builds)

    def get_srcdir(self, buildscript):
        '''Override base.CVSModule.get_srcdir to return GDB''s
        top-level directory, src.'''
        cvsroot = self.CVSRoot(self.cvsroot,
                               buildscript.config.checkoutroot)

        return cvsroot.getcheckoutdir(self.cvsmodule,
                                      self.checkoutdir)

    def do_configure(self, buildscript):
        '''Override base.CVSModule.do_configure to call configure
        rather than autogen.  Also, GDB''s configure script only
        accepts the --option=%s syntax; the build fails if --prefix %s
        is used.'''
        builddir = self.get_builddir(buildscript)
        if buildscript.config.buildroot and not os.path.exists(builddir):
            os.makedirs(builddir)
        os.chdir(builddir)
        buildscript.set_action('Configuring', self)
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            cmd = self.get_srcdir(buildscript) + '/configure'
        else:
            cmd = './configure'
        cmd += ' --prefix=%s' % buildscript.config.prefix
        if buildscript.config.use_lib64:
            cmd += " --libdir='${exec_prefix}/lib64'"
        cmd += ' %s' % self.autogenargs
        if buildscript.config.makeclean:
            nextstate = self.STATE_CLEAN
        else:
            nextstate = self.STATE_BUILD
        if buildscript.execute(cmd) == 0:
            return (nextstate, None, None)
        else:
            return (nextstate, 'could not configure module',
                    [self.STATE_FORCE_CHECKOUT])

def parse_gdbmodule(node, config, dependencies, suggests, cvsroot):
    return base.parse_cvsmodule(node, config, dependencies,
                                suggests, cvsroot, CVSModule=GDBModule)

base.register_module_type('gdbmodule', parse_gdbmodule)
