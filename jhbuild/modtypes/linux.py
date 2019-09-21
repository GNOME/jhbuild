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
import shutil
import errno

from jhbuild.errors import FatalError, BuildStateError
from jhbuild.modtypes import \
     register_module_type, MakeModule, get_branch
from jhbuild.utils import _

__all__ = [ 'LinuxModule' ]


class LinuxConfig:

    def __init__(self, version, path, branch):
        self.version = version
        self.path = path
        self.branch = branch

    def checkout(self, buildscript):
        if self.branch:
            self.branch.checkout(buildscript)
            if not os.path.exists(self.path):
                raise BuildStateError(_('kconfig file %s was not created') % self.path)


class LinuxModule(MakeModule):
    '''For modules that are built with the linux kernel method of
    make config, make, make install and make modules_install.'''
    type = 'linux'

    PHASE_CHECKOUT        = 'checkout'
    PHASE_FORCE_CHECKOUT  = 'force_checkout'
    PHASE_CLEAN           = 'clean'
    PHASE_MRPROPER        = 'mrproper'
    PHASE_CONFIGURE       = 'configure'
    PHASE_BUILD           = 'build'
    PHASE_KERNEL_INSTALL  = 'kernel_install'
    PHASE_MODULES_INSTALL = 'modules_install'
    PHASE_HEADERS_INSTALL = 'headers_install'
    PHASE_INSTALL         = 'install'

    def __init__(self, name, branch=None, kconfigs=None, makeargs=None):
        MakeModule.__init__(self, name, branch=branch, makeargs=makeargs)
        self.kconfigs = kconfigs

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        return self.get_srcdir(buildscript)

    def skip_checkout(self, buildscript, last_phase):
        # skip the checkout stage if the nonetwork flag is set
        # (can't just call Package.skip_checkout() as build policy won't work
        # with kconfigs)
        return buildscript.config.nonetwork

    def do_checkout(self, buildscript):
        buildscript.set_action(_('Checking out'), self)
        self.checkout(buildscript)
        for kconfig in self.kconfigs:
            kconfig.checkout(buildscript)
    do_checkout.error_phases = [PHASE_MRPROPER]

    def do_force_checkout(self, buildscript):
        buildscript.set_action(_('Checking out'), self)
        self.branch.force_checkout(buildscript)
    do_force_checkout.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_MRPROPER]

    def do_mrproper(self, buildscript):
        buildscript.set_action(_('make mrproper'), self)
        for kconfig in self.kconfigs:
            cmd = '%s %s mrproper EXTRAVERSION=%s O=%s' % (
                    os.environ.get('MAKE', 'make'),
                    self.get_makeargs(buildscript),
                    kconfig.version,
                    'build-' + kconfig.version)
            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)

        cmd = '%s mrproper' % os.environ.get('MAKE', 'make')
        buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)
    do_mrproper.depends = [PHASE_CHECKOUT]

    def do_configure(self, buildscript):
        buildscript.set_action(_('Configuring'), self)

        for kconfig in self.kconfigs:
            if kconfig.path:
                shutil.copyfile(kconfig.path, os.path.join(self.branch.srcdir, ".config"))

            try:
                os.makedirs(os.path.join(self.branch.srcdir, 'build-' + kconfig.version))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

            if kconfig.branch:
                cmd = '%s oldconfig EXTRAVERSION=%s O=%s'
            else:
                cmd = '%s defconfig EXTRAVERSION=%s O=%s'

            cmd = cmd % (
                    os.environ.get('MAKE', 'make'),
                    kconfig.version,
                    'build-' + kconfig.version)

            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)

            if kconfig.path:
                os.remove(os.path.join(self.branch.srcdir, ".config"))

    do_configure.depends = [PHASE_MRPROPER]
    do_configure.error_phases = [PHASE_FORCE_CHECKOUT]

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
        for kconfig in self.kconfigs:
            cmd = '%s %s clean EXTRAVERSION=%s O=%s' % (
                    os.environ.get('MAKE', 'make'),
                    self.get_makeargs(buildscript),
                    kconfig.version,
                    'build-' + kconfig.version)
            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)

    do_clean.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        for kconfig in self.kconfigs:
            cmd = '%s %s EXTRAVERSION=%s O=%s' % (os.environ.get('MAKE', 'make'),
                                                  self.get_makeargs(buildscript),
                                                  kconfig.version,
                                                  'build-' + kconfig.version)
            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)

    do_build.depends = [PHASE_CONFIGURE]
    do_build.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_MRPROPER, PHASE_CONFIGURE]

    def do_kernel_install(self, buildscript):
        buildscript.set_action(_('Installing kernel'), self)
        bootdir = os.path.join(buildscript.config.prefix, 'boot')
        if not os.path.isdir(bootdir):
            os.makedirs(bootdir)
        for kconfig in self.kconfigs:
            # We do this on our own without 'make install' because things will go weird on the user
            # if they have a custom installkernel script in ~/bin or /sbin/ and we can't override this.
            for f in ("System.map", ".config", "vmlinux"):
                cmd = "cp %s %s" % (
                    os.path.join('build-'+kconfig.version, f),
                    os.path.join(bootdir, f+'-'+kconfig.version))
                buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)

    do_kernel_install.depends = [PHASE_BUILD]
    do_kernel_install.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_modules_install(self, buildscript):
        buildscript.set_action(_('Installing modules'), self)
        for kconfig in self.kconfigs:
            cmd = '%s %s modules_install EXTRAVERSION=%s O=%s INSTALL_MOD_PATH=%s' % (
                    os.environ.get('MAKE', 'make'),
                    self.get_makeargs(buildscript),
                    kconfig.version,
                    'build-' + kconfig.version,
                    buildscript.config.prefix)
            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)

    do_modules_install.depends = [PHASE_BUILD]
    do_modules_install.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_headers_install(self, buildscript):
        buildscript.set_action(_('Installing kernel headers'), self)
        for kconfig in self.kconfigs:
            cmd = '%s %s headers_install EXTRAVERSION=%s O=%s INSTALL_HDR_PATH=%s' % (
                    os.environ.get('MAKE', 'make'),
                    self.get_makeargs(buildscript),
                    kconfig.version,
                    'build-' + kconfig.version,
                    buildscript.config.prefix)
            buildscript.execute(cmd, cwd = self.branch.srcdir,
                    extra_env = self.extra_env)
        buildscript.moduleset.packagedb.add(self.name,
                                            self.get_revision() or '',
                                            self.get_destdir(buildscript))

    do_headers_install.depends = [PHASE_BUILD]
    do_headers_install.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_install(self, buildscript):
        pass
    do_install.depends = [PHASE_KERNEL_INSTALL, PHASE_MODULES_INSTALL, PHASE_HEADERS_INSTALL]

    def xml_tag_and_attrs(self):
        return 'linux', [('id', 'name', None),
                         ('makeargs', 'makeargs', '')]


def get_kconfigs(node, repositories, default_repo):
    id = node.getAttribute('id')

    kconfigs = []
    kconfig = None

    for childnode in node.childNodes:
        if childnode.nodeType != childnode.ELEMENT_NODE or childnode.nodeName != 'kconfig':
            continue

        if childnode.hasAttribute('repo'):
            repo_name = childnode.getAttribute('repo')
            try:
                repo = repositories[repo_name]
            except KeyError:
                raise FatalError(_('Repository=%(missing)s not found for kconfig in linux id=%(linux_id)s. Possible repositories are %(possible)s'
                                   % {'missing': repo_name, 'linux_id': id, 'possible': repositories}))
        else:
            try:
                repo = repositories[default_repo]
            except KeyError:
                raise FatalError(_('Default repository=%(missing)s not found for kconfig in linux id=%(linux_id)s. Possible repositories are %(possible)s'
                                   % {'missing': default_repo, 'linux_id': id, 'possible': repositories}))

        branch = repo.branch_from_xml(id, childnode, repositories, default_repo)

        version = childnode.getAttribute('version')

        if childnode.hasAttribute('config'):
            path = os.path.join(kconfig.srcdir, childnode.getAttribute('config'))
        else:
            path = kconfig.srcdir

        kconfig = LinuxConfig(version, path, branch)
        kconfigs.append(kconfig)

    if not kconfigs:
        kconfig = LinuxConfig('default', None, None)
        kconfigs.append(kconfig)

    return kconfigs

def parse_linux(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')

    makeargs = ''
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
        makeargs = makeargs.replace('${prefix}', config.prefix)

    branch = get_branch(node, repositories, default_repo, config)
    kconfigs = get_kconfigs(node, repositories, default_repo)

    return LinuxModule(id, branch, kconfigs, makeargs)

register_module_type('linux', parse_linux)
