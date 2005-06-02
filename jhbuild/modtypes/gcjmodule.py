# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   gcjmodule.py: module type definitions for the GNU Compiler for Java
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
from jhbuild.utils import cvs

class GCCCVSRoot(cvs.CVSRoot):
    '''A class to handle CVS checkout and update operations in the GCC
    tree.'''

    def getcheckoutdir(self, module, checkoutdir=None):
        '''Override CVSRoot.getcheckoutdir to return GCJ''s top-level
        directory, gcc.'''
        return os.path.join(self.localroot, 'gcc')

    def checkout(self, buildscript, module, revision=None, date=None,
                 checkoutdir=None):
        '''Override cvs.CVSRoot.checkout to check out a list of
        modules instead of just one.'''
        os.chdir(self.localroot)
        cmd = 'cvs -z3 -q -d %s checkout -P ' % self.cvsroot

        if checkoutdir:
            cmd += '-d %s ' % checkoutdir

        if revision:
            cmd += '-r %s ' % revision
        if date:
            cmd += '-D "%s" ' % date
        if not (revision or date):
            cmd = cmd + '-A '

        for updatemod in module.split(" "):
            res = buildscript.execute(cmd + updatemod, 'cvs')
            if res != 0:
                break

        return res

    def update(self, buildscript, module, revision=None, date=None,
               checkoutdir=None):
        '''Override cvs.CVSRoot.update to use gcc_update in place of
        "cvs update".'''
        dir = self.getcheckoutdir(module, checkoutdir)
        if not os.path.exists(dir):
            return self.checkout(buildscript, 'gcc',
                                 revision, date, checkoutdir)

        # gcc_update will not update the tree properly if a previous
        # checkout attempt was aborted.  Because gcc_update decides
        # what to update based on the directories that are present in
        # the top-level gcc directory, it is difficult to make the
        # update process robust against checkout interruptions.
        os.chdir(dir)
        cmd = 'contrib/gcc_update --nostdflags -d -P '

        if revision:
            cmd += '-r %s ' % revision
        if date:
            cmd += '-D "%s" ' % date
        if not (revision or date):
            cmd = cmd + '-A '

        return buildscript.execute(cmd, 'cvs')

class GCJModule(base.CVSModule):
    CVSRoot = GCCCVSRoot
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
        '''Override base.CVSModule.get_srcdir to return GCJ''s
        top-level directory, gcc.'''
        cvsroot = self.CVSRoot(self.cvsroot,
                               buildscript.config.checkoutroot)

        return cvsroot.getcheckoutdir(self.cvsmodule,
                                      self.checkoutdir)

    def do_configure(self, buildscript):
        '''Override base.CVSModule.do_configure to call configure
        rather than autogen, and to have gcc install its tools in
        gcj-bin rather than bin.'''
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
        # Keep the installed gcc tools (gcc, g++, ...) out of the main
        # JHBuild path.
        cmd += ' --bindir=%s' % os.path.join(buildscript.config.prefix, 'gcj-bin')
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

    def do_install(self, buildscript):
        '''Override base.CVSModule.do_install to create a symbolic
        link from gcj-bin to bin for gcj and gij.  This prevents the
        JHBuild-installed C and C++ compilers from overriding the
        system compilers.'''
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Installing', self)
        cmd = '%s %s install' % (os.environ.get('MAKE', 'make'), self.makeargs)
        error = None
        if buildscript.execute(cmd) != 0:
            error = 'could not make module'
        else:
            buildscript.packagedb.add(self.name, self.revision or '')
            if not os.path.exists(os.path.join(buildscript.config.prefix, 'bin', 'gcj')):
                os.symlink(os.path.join(buildscript.config.prefix, 'gcj-bin', 'gcj'), \
                           os.path.join(buildscript.config.prefix, 'bin', 'gcj'))
            if not os.path.exists(os.path.join(buildscript.config.prefix, 'bin', 'gij')):
                os.symlink(os.path.join(buildscript.config.prefix, 'gcj-bin', 'gij'), \
                           os.path.join(buildscript.config.prefix, 'bin', 'gij'))
            if not os.path.exists(os.path.join(buildscript.config.prefix, 'bin', 'gcj-dbtool')):
                os.symlink(os.path.join(buildscript.config.prefix, 'gcj-bin', 'gcj-dbtool'), \
                           os.path.join(buildscript.config.prefix, 'bin', 'gcj-dbtool'))
        return (self.STATE_DONE, error, [])

def parse_gcjmodule(node, config, dependencies, suggests, cvsroot):
    return base.parse_cvsmodule(node, config, dependencies,
                                suggests, cvsroot, CVSModule=GCJModule)

base.register_module_type('gcjmodule', parse_gcjmodule)
