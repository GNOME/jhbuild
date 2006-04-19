# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
# Copyright (C) 2003-2004  Marco Pesenti Gritti
#
#   mozillamodule.py: rules for building Mozilla
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
from jhbuild.errors import FatalError, CommandError

class MozillaModule(base.CVSModule):
    def __init__(self, name, projects, revision, autogenargs='',
		 makeargs='', dependencies=[], suggests=[], cvsroot=None):
        base.CVSModule.__init__(self, name,
				revision=revision,
                                autogenargs=autogenargs,
                                makeargs=makeargs,
                                dependencies=dependencies,
                                suggests=suggests,
                                cvsroot=cvsroot,
                                supports_non_srcdir_builds=False)
	self.projects = projects
	os.environ['MOZ_CO_PROJECT'] = projects

    def get_mozilla_app(self):
        if self.projects == 'browser':
            return 'firefox'
        else:
            return 'mozilla'

    def get_mozilla_ver(self, buildscript):
	if self.projects == 'browser':
            filename = os.path.join(self.get_builddir(buildscript),
                                    'browser', 'config', 'version.txt') 
        else:
            filename = os.path.join(self.get_builddir(buildscript),
                                    'config', 'milestone.txt')
	fp = open(filename, 'r')
	for line in fp.readlines():
	    if line[0] not in ('#', '\0', '\n'):
                return line.strip()
        else:
            raise FatalError('could not determine mozilla version')

    def checkout(self, buildscript):
        buildscript.set_action('Checking out', self)
        cvsroot = self.CVSRoot(self.cvsroot, buildscript.config.checkoutroot)
        cvsroot.checkout(buildscript, 'mozilla/client.mk',
                         self.revision, buildscript.config.sticky_date)

        checkoutdir = self.get_builddir(buildscript)
        os.chdir(checkoutdir)
        buildscript.execute(['make', '-f', 'client.mk', 'checkout'])

    def do_checkout(self, buildscript):
        checkoutdir = self.get_builddir(buildscript)
        client_mk = os.path.join(checkoutdir, 'client.mk')
        try:
            if not os.path.exists(client_mk) or \
                   cvs.check_sticky_tag(client_mk) != self.revision:
                self.checkout(buildscript)
            else:
                os.chdir(checkoutdir)
                buildscript.set_action('Updating', self)
                buildscript.execute(['make', '-f', 'client.mk',
                                     'fast-update'])
        except CommandError:
            succeeded = False
        else:
            succeeded = True

        if buildscript.config.nobuild:
            nextstate = self.STATE_DONE
        else:
            nextstate = self.STATE_CONFIGURE
            
        # did the checkout succeed?
        if succeeded and os.path.exists(checkoutdir):
            return (nextstate, None, None)
        else:
            return (nextstate, 'could not update module',
                    [self.STATE_FORCE_CHECKOUT])

    def do_force_checkout(self, buildscript):
        try:
            self.checkout(buildscript)
        except CommandError:
            return (self.STATE_CONFIGURE, 'could not checkout module',
                    [self.STATE_FORCE_CHECKOUT])
        else:
            return (self.STATE_CONFIGURE, None, None)
        
    def do_configure(self, buildscript):
        checkoutdir = self.get_builddir(buildscript)
        os.chdir(checkoutdir)
        buildscript.set_action('Configuring', self)
        if buildscript.config.use_lib64:
            mozilla_path = '%s/lib64/%s-%s' \
                           % (buildscript.config.prefix,
                              self.get_mozilla_app(),
                              self.get_mozilla_ver(buildscript))
        else:
            mozilla_path = '%s/lib/%s-%s' \
                           % (buildscript.config.prefix,
                              self.get_mozilla_app(),
                              self.get_mozilla_ver(buildscript))
        
        cmd = './configure --prefix %s ' % buildscript.config.prefix
        if buildscript.config.use_lib64:
            cmd += " --libdir '${exec_prefix}/lib64'"
        cmd += ' --with-default-mozilla-five-home=%s' % mozilla_path
        cmd += ' %s' % self.autogenargs

        if self.projects:
            cmd += ' --enable-application=%s' % self.projects

        try:
            buildscript.execute(cmd)
        except CommandError:
            return (self.STATE_BUILD, 'could not configure module',
                    [self.STATE_FORCE_CHECKOUT])
        else:
            return (self.STATE_BUILD, None, None)

    def do_install(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Installing', self)
        try:
            cmd = 'make %s %s install' % (buildscript.config.makeargs,
                                          self.makeargs)
            buildscript.execute(cmd)
            cmd = 'mkdir %s/include/%s-%s/nss' \
                              % (buildscript.config.prefix,
				self.get_mozilla_app(),
				self.get_mozilla_ver(buildscript))
            buildscript.execute(cmd)

            cmd = 'find %s/security/nss/lib/ -name \'*.h\' -type f -exec /bin/cp {} %s/include/%s-%s/nss/ \;' \
                              % (self.get_builddir(buildscript),
                                 buildscript.config.prefix,
				 self.get_mozilla_app(),
                                 self.get_mozilla_ver(buildscript))
            buildscript.execute(cmd)
        except CommandError:
            return (self.STATE_DONE, 'could not make module', [])
        else:
            buildscript.packagedb.add(self.name, self.get_revision() or '')
            return (self.STATE_DONE, None, None)

def parse_mozillamodule(node, config, dependencies, suggests, root):
    if root[0] != 'cvs':
        raise FatalError('%s is not a CVS root' % root[1])
    cvsroot = root[1]
    name = node.getAttribute('id')
    projects = node.getAttribute('projects')
    revision = None
    autogenargs = ''
    makeargs = ''
    dependencies = []
    if node.hasAttribute('revision'):
        revision = node.getAttribute('revision')
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')

    # override revision tag if requested.
    revision = config.branches.get(name, revision)
    autogenargs += ' ' + config.module_autogenargs.get(name,
                                                       config.autogenargs)
    makeargs += ' ' + config.module_makeargs.get(name, makeargs)

    return MozillaModule(name, projects, revision, autogenargs, makeargs,
                         dependencies, suggests, cvsroot)

base.register_module_type('mozillamodule', parse_mozillamodule)
