# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   tarball.py: rules for building tarballs
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
from jhbuild.errors import FatalError

jhbuild_directory = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 '..', '..'))

class Tarball(base.Package):
    STATE_DOWNLOAD  = 'download'
    STATE_UNPACK    = 'unpack'
    STATE_PATCH     = 'patch'
    STATE_CONFIGURE = 'configure'
    STATE_BUILD     = 'build'
    STATE_INSTALL   = 'install'
    def __init__(self, name, version, source_url, source_size,
                 patches=[], dependencies=[], suggests=[]):
        base.Package.__init__(self, name, dependencies, suggests)
        self.version      = version
        self.source_url   = source_url
        self.source_size  = source_size
        self.patches      = patches

    def get_builddir(self, buildscript):
        localfile = os.path.basename(self.source_url)
        # strip off packaging extension ...
        if localfile.endswith('.tar.gz'):
            localfile = localfile[:-7]
        elif localfile.endswith('.tar.bz2'):
            localfile = localfile[:-8]
        elif localfile.endswith('.tgz'):
            localfile = localfile[:-4]
        return os.path.join(buildscript.config.checkoutroot, localfile)

    def get_revision(self):
        return self.version

    def do_start(self, buildscript):
        # check if jhbuild previously built it ...
        checkoutdir = self.get_builddir(buildscript)
        if buildscript.packagedb.check(self.name, self.version):
            return (self.STATE_DONE, None, None)

        return (self.STATE_DOWNLOAD, None, None)

    def do_download(self, buildscript):
        localfile = os.path.join(buildscript.config.checkoutroot,
                                 os.path.basename(self.source_url))
        if not buildscript.config.nonetwork:
            if (not os.path.exists(localfile) or
                os.stat(localfile)[6] != self.source_size):
                buildscript.set_action('Downloading', self, action_target=self.source_url)
                res = buildscript.execute('wget "%s" -O "%s"' %
                                          (self.source_url, localfile))
                if res:
                    return (self.STATE_UNPACK, 'error downloading file', [])

        if not os.path.exists(localfile) or \
               os.stat(localfile)[6] != self.source_size:
            return (self.STATE_UNPACK,
                    'file not downloaded, or of incorrect size', [])
        return (self.STATE_UNPACK, None, None)

    def do_unpack(self, buildscript):
        os.chdir(buildscript.config.checkoutroot)
        localfile = os.path.basename(self.source_url)
        checkoutdir = self.get_builddir(buildscript)

        buildscript.set_action('Unpacking', self)
        if localfile.endswith('.bz2'):
            res = buildscript.execute('bunzip2 -dc %s | tar xf -' % localfile)
        elif localfile.endswith('.gz'):
            res = buildscript.execute('gunzip -dc %s | tar xf -' % localfile)
        else:
            raise FatalError("don't know how to handle: %s" % localfile)
        
        if res or not os.path.exists(checkoutdir):
            return (self.STATE_PATCH, 'could not unpack tarball', [])

        return (self.STATE_PATCH, None, None)

    def do_patch(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        
        for (patch, patchstrip) in self.patches:
            patchfile = os.path.join(jhbuild_directory, 'patches', patch)
            buildscript.set_action('Applying Patch', self, action_target=patch)
            res = buildscript.execute('patch -p%d < %s' % (patchstrip,
                                                           patchfile))
            if res:
                return (self.STATE_CONFIGURE, 'could not apply patch', [])
            
        if buildscript.config.nobuild:
            return (self.STATE_DONE, None, None)
        else:
            return (self.STATE_CONFIGURE, None, None)

    def do_configure(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Configuring', self)
        cmd = './configure --prefix %s' % buildscript.config.prefix
        if buildscript.config.use_lib64:
            cmd += " --libdir '${exec_prefix}/lib64'"
        res = buildscript.execute(cmd)
        error = None
        if res != 0:
            error = 'could not configure package'
        return (self.STATE_BUILD, error, [])

    def do_build(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Building', self)
        cmd = 'make %s' % buildscript.config.makeargs
        if buildscript.execute(cmd) == 0:
            return (self.STATE_INSTALL, None, None)
        else:
            return (self.STATE_INSTALL, 'could not build module', [])

    def do_install(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Installing', self)
        cmd = 'make %s install' % buildscript.config.makeargs
        error = None
        if buildscript.execute(cmd) != 0:
            error = 'could not make module'
        else:
            buildscript.packagedb.add(self.name, self.version or '')
        return (self.STATE_DONE, error, [])

def parse_tarball(node, config, dependencies, suggests, cvsroot):
    name = node.getAttribute('id')
    version = node.getAttribute('version')
    source_url = None
    source_size = None
    patches = []
    dependencies = []
    for childnode in node.childNodes:
        if childnode.nodeType != childnode.ELEMENT_NODE: continue
        if childnode.nodeName == 'source':
            source_url = childnode.getAttribute('href')
            source_size = int(childnode.getAttribute('size'))
        elif childnode.nodeName == 'patches':
            for patch in childnode.childNodes:
                if patch.nodeType != patch.ELEMENT_NODE: continue
                if patch.nodeName != 'patch': continue
                patchfile = patch.getAttribute('file')
                if patch.hasAttribute('strip'):
                    patchstrip = int(patch.getAttribute('strip'))
                else:
                    patchstrip = 0
                patches.append((patchfile, patchstrip))

    return Tarball(name, version, source_url, source_size,
                   patches, dependencies, suggests)

base.register_module_type('tarball', parse_tarball)
