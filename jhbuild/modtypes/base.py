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

def parse_xml_node(node, config, dependencies, cvsroot):
    parser = _module_types[node.nodeName]
    return parser(node, config, dependencies, cvsroot)

class Package:
    STATE_START = 'start'
    STATE_DONE  = 'done'
    def __init__(self, name, dependencies=[]):
        self.name = name
        self.dependencies = dependencies
    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.name)

    def get_builddir(self, buildscript):
        pass

    def get_revision(self):
        return None

    def run_state(self, buildscript, state):
        '''run a particular part of the build for this package.

        Returns a tuple of the following form:
          (next-state, error-flag, [other-states])'''
        method = getattr(self, 'do_' + state)
        return method(buildscript)

class CVSModule(Package):
    STATE_CHECKOUT       = 'checkout'
    STATE_FORCE_CHECKOUT = 'force_checkout'
    STATE_CONFIGURE      = 'configure'
    STATE_BUILD          = 'build'
    STATE_INSTALL        = 'install'

    def __init__(self, cvsmodule, checkoutdir=None, revision=None,
                 autogenargs='', dependencies=[], cvsroot=None):
        Package.__init__(self, checkoutdir or cvsmodule, dependencies)
        self.cvsmodule   = cvsmodule
        self.checkoutdir = checkoutdir
        self.revision    = revision
        self.autogenargs = autogenargs
        self.cvsroot     = cvsroot

    def get_builddir(self, buildscript):
        return os.path.join(buildscript.config.checkoutroot,
                            self.checkoutdir or self.cvsmodule)

    def get_revision(self):
        return self.revision

    def do_start(self, buildscript):
        checkoutdir = self.get_builddir(buildscript)
        if not buildscript.config.nonetwork: # normal start state
            return (self.STATE_CHECKOUT, None, None)
        elif buildscript.config.nobuild:
            return (self.STATE_DONE, None, None)
        elif not buildscript.config.alwaysautogen and \
                 os.path.exists(os.path.join(checkoutdir, 'Makefile')):
            return (self.STATE_BUILD, None, None)
        else:
            return (self.STATE_CONFIGURE, None, None)

    def do_checkout(self, buildscript):
        cvsroot = cvs.CVSRoot(self.cvsroot,
                              buildscript.config.checkoutroot)
        checkoutdir = self.get_builddir(buildscript)
        buildscript.set_action('Checking out', self)
        res = cvsroot.update(buildscript, self.cvsmodule,
                             self.revision, buildscript.config.sticky_date,
                             checkoutdir=self.checkoutdir)

        if buildscript.config.nobuild:
            nextstate = self.STATE_DONE
        elif not buildscript.config.alwaysautogen and \
                 os.path.exists(os.path.join(checkoutdir, 'Makefile')):
            nextstate = self.STATE_BUILD
        else:
            nextstate = self.STATE_CONFIGURE
        # did the checkout succeed?
        if res == 0 and os.path.exists(checkoutdir):
            return (nextstate, None, None)
        else:
            return (nextstate, 'could not update module',
                    [self.STATE_FORCE_CHECKOUT])

    def do_force_checkout(self, buildscript):
        cvsroot = cvs.CVSRoot(self.cvsroot,
                              buildscript.config.checkoutroot)
        checkoutdir = self.get_builddir(buildscript)
        buildscript.set_action('Checking out', self)
        res = cvsroot.checkout(buildscript, self.cvsmodule,
                               self.revision, buildscript.config.sticky_date,
                               checkoutdir=self.checkoutdir)
        if res == 0 and os.path.exists(checkoutdir):
            return (self.STATE_CONFIGURE, None, None)
        else:
            return (self.STATE_CONFIGURE, 'could not checkout module',
                    [self.STATE_FORCE_CHECKOUT])

    def do_configure(self, buildscript):
        checkoutdir = self.get_builddir(buildscript)
        os.chdir(checkoutdir)
        buildscript.set_action('Configuring', self)
        cmd = './autogen.sh --prefix %s' % buildscript.config.prefix
        if buildscript.config.use_lib64:
            cmd += " --libdir '${exec_prefix}/lib64'"
        cmd += ' %s %s' % (self.autogenargs, buildscript.config.autogenargs)
        if buildscript.execute(cmd) == 0:
            return (self.STATE_BUILD, None, None)
        else:
            return (self.STATE_BUILD, 'could not configure module',
                    [self.STATE_FORCE_CHECKOUT])

    def do_build(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Building', self)
        cmd = 'make %s' % buildscript.config.makeargs
        if buildscript.execute(cmd) == 0:
            return (self.STATE_INSTALL, None, None)
        else:
            return (self.STATE_INSTALL, 'could not build module',
                    [self.STATE_FORCE_CHECKOUT, self.STATE_CONFIGURE])

    def do_install(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Installing', self)
        cmd = 'make %s install' % buildscript.config.makeargs
        error = None
        if buildscript.execute(cmd) != 0:
            error = 'could not make module'
        return (self.STATE_DONE, error, [])

def parse_cvsmodule(node, config, dependencies, cvsroot):
    id = node.getAttribute('id')
    module = id
    revision = None
    checkoutdir = None
    autogenargs = ''
    if node.hasAttribute('module'):
        module = node.getAttribute('module')
    if node.hasAttribute('revision'):
        revision = node.getAttribute('revision')
    if node.hasAttribute('checkoutdir'):
        checkoutdir = node.getAttribute('checkoutdir')
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')

    # override revision tag if requested.
    revision = config.branches.get(module, revision)
    autogenargs = config.module_autogenargs.get(module, autogenargs)

    return CVSModule(module, checkoutdir, revision,
                     autogenargs, cvsroot=cvsroot,
                     dependencies=dependencies)
register_module_type('cvsmodule', parse_cvsmodule)

class MetaModule(Package):
    def get_builddir(self, buildscript):
        return buildscript.config.checkoutroot
    
    # nothing to actually build in a metamodule ...
    def do_start(self, buildscript):
        return (self.STATE_DONE, None, None)

def parse_metamodule(node, config, dependencies, cvsroot):
    id = node.getAttribute('id')
    return MetaModule(id, dependencies=dependencies)
register_module_type('metamodule', parse_metamodule)
