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

from jhbuild.errors import FatalError, CommandError, BuildStateError

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
        # has the state been updated to the new system?
        if hasattr(method, 'next_state'):
            try:
                method(buildscript)
            except (CommandError, BuildStateError), e:
                return (method.next_state, str(e), method.error_states)
            else:
                return (method.next_state, None, None)
        else:
            return method(buildscript)

class AutogenModule(Package):
    '''Base type for modules that are distributed with a Gnome style
    "autogen.sh" script and the GNU build tools.  Subclasses are
    responsible for downloading/updating the working copy.'''
    type = 'autogen'

    STATE_CHECKOUT       = 'checkout'
    STATE_FORCE_CHECKOUT = 'force_checkout'
    STATE_CLEAN          = 'clean'
    STATE_CONFIGURE      = 'configure'
    STATE_BUILD          = 'build'
    STATE_CHECK          = 'check'
    STATE_INSTALL        = 'install'

    def __init__(self, name, branch, autogenargs='', makeargs='',
                 dependencies=[], suggests=[],
                 supports_non_srcdir_builds=True):
        Package.__init__(self, name, dependencies, suggests)
        self.branch = branch
        self.autogenargs = autogenargs
        self.makeargs    = makeargs
        self.supports_non_srcdir_builds = supports_non_srcdir_builds

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            d = buildscript.config.builddir_pattern % (
                os.path.basename(self.get_srcdir(buildscript)))
            return os.path.join(buildscript.config.buildroot, d)
        else:
            return self.get_srcdir(buildscript)

    def get_revision(self):
        return self.branch.branchname

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
        srcdir = self.get_srcdir(buildscript)
        builddir = self.get_builddir(buildscript)
        buildscript.set_action('Checking out', self)
        try:
            self.branch.checkout(buildscript)
        except CommandError:
            succeeded = False
        else:
            succeeded = True

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
        if succeeded and os.path.exists(srcdir):
            return (nextstate, None, None)
        else:
            return (nextstate, 'could not update module',
                    [self.STATE_FORCE_CHECKOUT])

    def do_force_checkout(self, buildscript):
        if buildscript.config.nobuild:
            nextstate = self.STATE_DONE
        else:
            nextstate = self.STATE_CONFIGURE

        buildscript.set_action('Checking out', self)
        try:
            self.branch.force_checkout(buildscript)
        except CommandError:
            return (nextstate, 'could not checkout module',
                    [self.STATE_FORCE_CHECKOUT])
        else:
            return (nextstate, None, None)

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
        cmd += ' %s' % self.autogenargs
        if buildscript.config.makeclean:
            nextstate = self.STATE_CLEAN
        else:
            nextstate = self.STATE_BUILD
        try:
            buildscript.execute(cmd)
        except CommandError:
            return (nextstate, 'could not configure module',
                    [self.STATE_FORCE_CHECKOUT])
        else:
            return (nextstate, None, None)

    def do_clean(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Cleaning', self)
        cmd = '%s %s clean' % (os.environ.get('MAKE', 'make'), self.makeargs)
        buildscript.execute(cmd)
    do_clean.next_state = STATE_BUILD
    do_clean.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def do_build(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Building', self)
        cmd = '%s %s' % (os.environ.get('MAKE', 'make'), self.makeargs)
        if buildscript.config.makecheck:
            nextstate = self.STATE_CHECK
        else:
            nextstate = self.STATE_INSTALL
        try:
            buildscript.execute(cmd)
        except CommandError:
            return (nextstate, 'could not build module',
                    [self.STATE_FORCE_CHECKOUT, self.STATE_CONFIGURE])
        else:
            return (nextstate, None, None)

    def do_check(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Checking', self)
        cmd = '%s %s check' % (os.environ.get('MAKE', 'make'), self.makeargs)
        buildscript.execute(cmd)
    do_check.next_state = STATE_INSTALL
    do_check.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def do_install(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Installing', self)
        cmd = '%s %s install' % (os.environ.get('MAKE', 'make'), self.makeargs)
        buildscript.execute(cmd)
        buildscript.packagedb.add(self.name, self.get_revision() or '')
    do_install.next_state = Package.STATE_DONE
    do_install.error_states = []


def parse_cvsmodule(node, config, dependencies, suggests, repository):
    id = node.getAttribute('id')
    module = None
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
    autogenargs += ' ' + config.module_autogenargs.get(module,
                                                       config.autogenargs)
    makeargs += ' ' + config.module_makeargs.get(module, config.makeargs)

    branch = repository.branch(id, module=module, checkoutdir=checkoutdir,
                               revision=revision)

    return AutogenModule(id, branch, autogenargs, makeargs,
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
        pass
    do_start.next_state = Package.STATE_DONE
    do_start.error_states = []

def parse_metamodule(node, config, dependencies, suggests, cvsroot):
    id = node.getAttribute('id')
    return MetaModule(id, dependencies=dependencies, suggests=suggests)
register_module_type('metamodule', parse_metamodule)
