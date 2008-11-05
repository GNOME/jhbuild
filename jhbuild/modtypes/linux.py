#
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007  Red Hat, Inc.
#
#   linux.py: support for building the linux kernel
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
import re
import shutil
import errno

from jhbuild.errors import FatalError, BuildStateError
from jhbuild.modtypes import \
     Package, get_dependencies, get_branch, register_module_type

__all__ = [ 'LinuxModule' ]

class LinuxModule(Package):
    '''For modules that are built with the linux kernel method of
    make config, make, make install and make modules_install.'''
    type = 'linux'

    STATE_CHECKOUT        = 'checkout'
    STATE_FORCE_CHECKOUT  = 'force_checkout'
    STATE_CLEAN           = 'clean'
    STATE_CONFIGURE       = 'configure'
    STATE_BUILD           = 'build'
    STATE_INSTALL         = 'install'
    STATE_MODULES_INSTALL = 'modules_install'

    def __init__(self, name, branch, kconfigs, makeargs,
            dependencies, after, suggests, extra_env = None):
        Package.__init__(self, name, dependencies, after, suggests, extra_env)
        self.branch = branch
        self.kconfigs = kconfigs
        self.makeargs = makeargs

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        return self.get_srcdir(buildscript)

    def get_revision(self):
        return self.branch.branchname

    def do_start(self, buildscript):
        pass
    do_start.next_state = STATE_CHECKOUT
    do_start.error_states = []

    def skip_checkout(self, buildscript, last_state):
        # skip the checkout stage if the nonetwork flag is set
        # (can't just call Package.skip_checkout() as build policy won't work
        # with kconfigs)
        return buildscript.config.nonetwork

    def do_checkout(self, buildscript):
        buildscript.set_action(_('Checking out'), self)
        self.checkout(buildscript)
        for kconfig in self.kconfigs:
            kconfig.checkout(buildscript)
            if not os.path.exists(kconfig.path):
                raise BuildStateError(_('kconfig file %s was not created') % kconfig.path)
    do_checkout.next_state = STATE_CONFIGURE
    do_checkout.error_states = [STATE_FORCE_CHECKOUT]

    def skip_force_checkout(self, buildscript, last_state):
        return False

    def do_force_checkout(self, buildscript):
        buildscript.set_action(_('Checking out'), self)
        self.branch.force_checkout(buildscript)
    do_force_checkout.next_state = STATE_CONFIGURE
    do_force_checkout.error_states = [STATE_FORCE_CHECKOUT]

    def skip_configure(self, buildscript, last_state):
        return False

    def do_configure(self, buildscript):
        buildscript.set_action(_('Configuring'), self)

        for kconfig in self.kconfigs:
            shutil.copyfile(kconfig.path, os.path.join(self.branch.srcdir, ".config"))

            try:
                os.makedirs(os.path.join(self.branch.srcdir, 'build-' + kconfig.version))
            except OSError, (e, msg):
                if e != errno.EEXIST:
                    raise

            cmd = '%s oldconfig EXTRAVERSION=%s O=%s' % (
                    os.environ.get('MAKE', 'make'),
                    kconfig.version,
                    'build-' + kconfig.version)

            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)

            os.remove(os.path.join(self.branch.srcdir, ".config"))

    do_configure.next_state = STATE_CLEAN
    do_configure.error_states = [STATE_FORCE_CHECKOUT]

    def skip_clean(self, buildscript, last_state):
        return (not buildscript.config.makeclean or
                buildscript.config.nobuild)

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
        for kconfig in self.kconfigs:
            cmd = '%s %s clean EXTRAVERSION=%s O=%s' % (
                    os.environ.get('MAKE', 'make'),
                    self.makeargs,
                    kconfig.version,
                    'build-' + kconfig.version)
            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)

    do_clean.next_state = STATE_BUILD
    do_clean.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_build(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        for kconfig in self.kconfigs:
            cmd = '%s %s EXTRAVERSION=%s O=%s' % (os.environ.get('MAKE', 'make'),
                                                  self.makeargs,
                                                  kconfig.version,
                                                  'build-' + kconfig.version)
            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)

    do_build.next_state = STATE_INSTALL
    do_build.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_install(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        for kconfig in self.kconfigs:
            cmd = '%s %s install EXTRAVERSION=%s O=%s INSTALL_PATH=%s/boot' % (
                    os.environ.get('MAKE', 'make'),
                    self.makeargs,
                    kconfig.version,
                    'build-' + kconfig.version,
                    buildscript.config.prefix)
            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)

    do_install.next_state = STATE_MODULES_INSTALL
    do_install.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_modules_install(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_modules_install(self, buildscript):
        buildscript.set_action(_('Installing modules'), self)
        for kconfig in self.kconfigs:
            cmd = '%s %s modules_install EXTRAVERSION=%s O=%s INSTALL_MOD_PATH=%s' % (
                    os.environ.get('MAKE', 'make'),
                    self.makeargs,
                    kconfig.version,
                    'build-' + kconfig.version,
                    buildscript.config.prefix)
            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)
        buildscript.packagedb.add(self.name, self.get_revision() or '')

    do_install.next_state = Package.STATE_DONE
    do_install.error_states = []

def get_kconfigs(node, repositories, default_repo):
    id = node.getAttribute('id')

    kconfigs = []

    for childnode in node.childNodes:
        if childnode.nodeType != childnode.ELEMENT_NODE or childnode.nodeName != 'kconfig':
            continue

        if childnode.hasAttribute('repo'):
            repo_name = childnode.getAttribute('repo')
            try:
                repo = repositories[repo_name]
            except KeyError:
                raise FatalError(_('Repository=%s not found for kconfig in linux id=%s. Possible repositories are %s') % (repo_name, id, repositories))
        else:
            try:
                repo = repositories[default_repo]
            except KeyError:
                raise FatalError(_('Default Repository=%s not found for kconfig in module id=%s. Possible repositories are %s') % (default_repo, id, repositories))

        kconfig = repo.branch_from_xml(id, childnode, repositories, default_repo)

        kconfig.version = childnode.getAttribute('version')

        if childnode.hasAttribute('config'):
            kconfig.path = os.path.join(kconfig.srcdir, childnode.getAttribute('config'))
        else:
            kconfig.path = kconfig.srcdir

        kconfigs.append(kconfig)

    if not kconfigs:
        raise FatalError(_('No <kconfig> elements found for module %s') % id)

    return kconfigs

def parse_linux(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')

    makeargs = ''
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
    # Make some substitutions; do special handling of '${prefix}' and '${libdir}'
    p = re.compile('(\${prefix})')
    makeargs = p.sub(config.prefix, makeargs)
    makeargs += ' ' + config.module_makeargs.get(id, config.makeargs)

    dependencies, after, suggests = get_dependencies(node)
    extra_env = config.module_extra_env.get(id)
    branch = get_branch(node, repositories, default_repo, config)
    if config.module_checkout_mode.get(id):
        branch.checkout_mode = config.module_checkout_mode[id]
    kconfigs = get_kconfigs(node, repositories, default_repo)

    return LinuxModule(id, branch, kconfigs,
                       makeargs, dependencies, after, suggests,
                       extra_env = extra_env)

register_module_type('linux', parse_linux)
