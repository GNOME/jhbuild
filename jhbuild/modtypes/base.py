# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   base.py: common module type definitions.
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

from jhbuild.utils import cvs


__all__ = [ 'Package', 'CVSModule',
            'register_module_type', 'parse_xml_node' ]

_module_types = {}
def register_module_type(name, parse_func):
    _module_types[name] = parse_func

def parse_xml_node(node, config, dependencies, suggests, cvsroot):
    if not _module_types.has_key(node.nodeName):
        try:
            __import__('jhbuild.modtypes.%s' % node.nodeName)
        except ImportError:
            pass
    if not _module_types.has_key(node.nodeName):
        raise FatalError('unknown module type %s' % node.nodeName)

    parser = _module_types[node.nodeName]
    return parser(node, config, dependencies, suggests, cvsroot)

class Package:
    type = 'base'
    STATE_START = 'start'
    STATE_DONE  = 'done'
    def __init__(self, name, dependencies=[], suggests=[]):
        self.name = name
        self.dependencies = dependencies
        self.suggests = suggests
    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.name)

    def get_srcdir(self, buildscript):
        raise NotImplementedError
    def get_builddir(self, buildscript):
        raise NotImplementedError

    def get_revision(self):
        return None

    def run_state(self, buildscript, state):
        '''run a particular part of the build for this package.

        Returns a tuple of the following form:
          (next-state, error-flag, [other-states])'''
        method = getattr(self, 'do_' + state)
        return method(buildscript)

class CVSModule(Package):
    CVSRoot = cvs.CVSRoot
    
    type = 'cvs'
    STATE_CHECKOUT       = 'checkout'
    STATE_FORCE_CHECKOUT = 'force_checkout'
    STATE_CLEAN          = 'clean'
    STATE_CONFIGURE      = 'configure'
    STATE_BUILD          = 'build'
    STATE_CHECK          = 'check'
    STATE_INSTALL        = 'install'

    def __init__(self, cvsmodule, checkoutdir=None, revision=None,
                 autogenargs='', makeargs='', dependencies=[], suggests=[],
                 cvsroot=None, supports_non_srcdir_builds=True):
        Package.__init__(self, checkoutdir or cvsmodule, dependencies,
                         suggests)
        self.cvsmodule   = cvsmodule
        self.checkoutdir = checkoutdir
        self.revision    = revision
        self.autogenargs = autogenargs
        self.makeargs    = makeargs
        self.cvsroot     = cvsroot
        self.supports_non_srcdir_builds = supports_non_srcdir_builds

    def get_srcdir(self, buildscript):
        return os.path.join(buildscript.config.checkoutroot,
                            self.checkoutdir or self.cvsmodule)
        
    def get_builddir(self, buildscript):
        if buildscript.config.buildroot and \
               self.supports_non_srcdir_builds:
            return os.path.join(buildscript.config.buildroot,
                                self.checkoutdir or self.cvsmodule)
        else:
            return self.get_srcdir(buildscript)

    def get_revision(self):
        return self.revision

    def do_start(self, buildscript):
        builddir = self.get_builddir(buildscript)
        if not buildscript.config.nonetwork: # normal start state
            return (self.STATE_CHECKOUT, None, None)
        elif buildscript.config.nobuild:
            return (self.STATE_DONE, None, None)
        elif buildscript.config.alwaysautogen or \
                 not os.path.exists(os.path.join(builddir, 'Makefile')):
            return (self.STATE_CONFIGURE, None, None)
        elif buildscript.config.makeclean:
            return (self.STATE_CLEAN, None, None)
        else:
            return (self.STATE_BUILD, None, None)

    def do_checkout(self, buildscript):
        cvsroot = self.CVSRoot(self.cvsroot,
                               buildscript.config.checkoutroot)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        buildscript.set_action('Checking out', self)
        res = cvsroot.update(buildscript, self.cvsmodule,
                             self.revision, buildscript.config.sticky_date,
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
        cvsroot = self.CVSRoot(self.cvsroot,
                              buildscript.config.checkoutroot)
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        if buildscript.config.nobuild:
            nextstate = self.STATE_DONE
        else:
            nextstate = self.STATE_CONFIGURE

        buildscript.set_action('Checking out', self)
        res = cvsroot.checkout(buildscript, self.cvsmodule,
                               self.revision, buildscript.config.sticky_date,
                               checkoutdir=self.checkoutdir)
        if res == 0 and os.path.exists(srcdir):
            return (nextstate, None, None)
        else:
            return (nextstate, 'could not checkout module',
                    [self.STATE_FORCE_CHECKOUT])

    def do_configure(self, buildscript):
        builddir = self.get_builddir(buildscript)
        if buildscript.config.buildroot and not os.path.exists(builddir):
            os.makedirs(builddir)
        os.chdir(builddir)
        buildscript.set_action('Configuring', self)
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            cmd = self.get_srcdir(buildscript) + '/autogen.sh'
        else:
            cmd = './autogen.sh'
        cmd += ' --prefix %s' % buildscript.config.prefix
        if buildscript.config.use_lib64:
            cmd += " --libdir '${exec_prefix}/lib64'"
        cmd += ' %s %s' % (self.autogenargs, buildscript.config.autogenargs)
        if buildscript.config.makeclean:
            nextstate = self.STATE_CLEAN
        else:
            nextstate = self.STATE_BUILD
        if buildscript.execute(cmd) == 0:
            return (nextstate, None, None)
        else:
            return (nextstate, 'could not configure module',
                    [self.STATE_FORCE_CHECKOUT])

    def do_clean(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Cleaning', self)
        cmd = 'make %s %s clean' % (buildscript.config.makeargs, self.makeargs)
        if buildscript.execute(cmd) == 0:
            return (self.STATE_BUILD, None, None)
        else:
            return (self.STATE_BUILD, 'could not clean module',
                    [self.STATE_FORCE_CHECKOUT, self.STATE_CONFIGURE])

    def do_build(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Building', self)
        cmd = 'make %s %s' % (buildscript.config.makeargs, self.makeargs)
        if buildscript.config.makecheck:
            nextstate = self.STATE_CHECK
        else:
            nextstate = self.STATE_INSTALL
        if buildscript.execute(cmd) == 0:
            return (nextstate, None, None)
        else:
            return (nextstate, 'could not build module',
                    [self.STATE_FORCE_CHECKOUT, self.STATE_CONFIGURE])

    def do_check(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Checking', self)
        cmd = 'make %s %s check' % (buildscript.config.makeargs, self.makeargs)
        if buildscript.execute(cmd) == 0:
            return (self.STATE_INSTALL, None, None)
        else:
            return (self.STATE_INSTALL, 'test suite failed',
                    [self.STATE_FORCE_CHECKOUT, self.STATE_CONFIGURE])

    def do_install(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Installing', self)
        cmd = 'make %s %s install' % (buildscript.config.makeargs,
                                      self.makeargs)
        error = None
        if buildscript.execute(cmd) != 0:
            error = 'could not make module'
        else:
            buildscript.packagedb.add(self.name, self.revision or '')
        return (self.STATE_DONE, error, [])

def parse_cvsmodule(node, config, dependencies, suggests, cvsroot,
                    CVSModule=CVSModule):
    id = node.getAttribute('id')
    module = id
    revision = None
    checkoutdir = None
    autogenargs = ''
    makeargs = ''
    supports_non_srcdir_builds = True
    if node.hasAttribute('module'):
        module = node.getAttribute('module')
    if node.hasAttribute('revision'):
        revision = node.getAttribute('revision')
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
    revision = config.branches.get(module, revision)
    autogenargs = config.module_autogenargs.get(module, autogenargs)
    makeargs = config.module_makeargs.get(module, makeargs)

    return CVSModule(module, checkoutdir, revision,
                     autogenargs, makeargs,
                     cvsroot=cvsroot,
                     dependencies=dependencies,
                     suggests=suggests,
                     supports_non_srcdir_builds=supports_non_srcdir_builds)
register_module_type('cvsmodule', parse_cvsmodule)

class MetaModule(Package):
    type = 'meta'
    def get_srcdir(self, buildscript):
        return buildscript.config.checkoutroot
    def get_builddir(self, buildscript):
        return buildscript.config.buildroot or \
               self.get_srcdir(buildscript)

    # nothing to actually build in a metamodule ...
    def do_start(self, buildscript):
        return (self.STATE_DONE, None, None)

def parse_metamodule(node, config, dependencies, suggests, cvsroot):
    id = node.getAttribute('id')
    return MetaModule(id, dependencies=dependencies, suggests=suggests)
register_module_type('metamodule', parse_metamodule)
