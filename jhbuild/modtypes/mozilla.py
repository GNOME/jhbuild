# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
# Copyright (C) 2003-2004  Marco Pesenti Gritti
#
#   mozilla.py: rules for building Mozilla
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

class MozillaModule(base.CVSModule):
    def __init__(self, name, revision, autogenargs='',
                 dependencies=[], suggests=[], cvsroot=None):
        base.CVSModule.__init__(self, name, revision=revision,
                                autogenargs=autogenargs,
                                dependencies=dependencies,
                                suggests=suggests,
                                cvsroot=cvsroot)
        
    def get_mozilla_ver(self, buildscript):
        filename = os.path.join(self.get_builddir(buildscript),
                                'config', 'milestone.txt')
	fp = open(filename, 'r')
	for line in fp.readlines():
	    if line[0] not in ('#', '\0', '\n'):
                return line[:-1]
        else:
            raise AssertionError

    def checkout(self, buildscript):
        buildscript.set_action('Checking out', self)
        cvsroot = cvs.CVSRoot(self.cvsroot, buildscript.config.checkoutroot)
        res = cvsroot.checkout(buildscript, 'mozilla/client.mk',
                               self.revision, buildscript.config.sticky_date)
        if res != 0:
            return res

        checkoutdir = self.get_builddir(buildscript)
        os.chdir(checkoutdir)
        return buildscript.execute('make -f client.mk checkout')

    def do_checkout(self, buildscript):
        checkoutdir = self.get_builddir(buildscript)
        client_mk = os.path.join(checkoutdir, 'client.mk')
        if not os.path.exists(client_mk) or \
               cvs.check_sticky_tag(client_mk) != self.revision:
            res = self.checkout(buildscript)
        else:
            os.chdir(checkoutdir)
            buildscript.set_action('Updating', self)
            res = buildscript.execute('make -f client.mk fast-update')

        if buildscript.config.nobuild:
            nextstate = self.STATE_DONE
        else:
            nextstate = self.STATE_CONFIGURE
            
        # did the checkout succeed?
        if res == 0 and os.path.exists(checkoutdir):
            return (nextstate, None, None)
        else:
            return (nextstate, 'could not update module',
                    [self.STATE_FORCE_CHECKOUT])

    def do_force_checkout(self, buildscript):
        res = self.checkout(buildscript)
        if res == 0:
            return (self.STATE_CONFIGURE, None, None)
        else:
            return (self.STATE_CONFIGURE, 'could not checkout module',
                    [self.STATE_FORCE_CHECKOUT])
        
    def do_configure(self, buildscript):
        checkoutdir = self.get_builddir(buildscript)
        os.chdir(checkoutdir)
        buildscript.set_action('Configuring', self)
        if buildscript.config.use_lib64:
            mozilla_path = '%s/lib64/mozilla-%s' \
                           % (buildscript.config.prefix,
                              self.get_mozilla_ver(buildscript))
        else:
            mozilla_path = '%s/lib/mozilla-%s' \
                           % (buildscript.config.prefix,
                              self.get_mozilla_ver(buildscript))
        
        cmd = './configure --prefix %s ' % buildscript.config.prefix
        if buildscript.config.use_lib64:
            cmd += " --libdir '${exec_prefix}/lib64'"
        cmd += ' --with-default-mozilla-five-home=%s' % mozilla_path
        cmd += ' %s %s' % (buildscript.config.autogenargs, self.autogenargs)
        
        if not buildscript.execute(cmd):
            return (self.STATE_BUILD, None, None)
        else:
            return (self.STATE_BUILD, 'could not configure module',
                    [self.STATE_FORCE_CHECKOUT])

def parse_mozillamodule(node, config, dependencies, suggests, cvsroot):
    name = node.getAttribute('id')
    revision = None
    autogenargs = ''
    dependencies = []
    if node.hasAttribute('revision'):
        revision = node.getAttribute('revision')
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')

    # override revision tag if requested.
    revision = config.branches.get(name, revision)
    autogenargs = config.module_autogenargs.get(name, autogenargs)

    return MozillaModule(name, revision, autogenargs,
                         dependencies, suggests, cvsroot)

base.register_module_type('mozillamodule', parse_mozillamodule)
