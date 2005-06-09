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
    type = 'tarball'
    STATE_DOWNLOAD  = 'download'
    STATE_UNPACK    = 'unpack'
    STATE_PATCH     = 'patch'
    STATE_CONFIGURE = 'configure'
    STATE_BUILD     = 'build'
    STATE_INSTALL   = 'install'
    def __init__(self, name, version, source_url, source_size, source_md5=None,
                 patches=[], autogenargs='', makeargs='',
                 dependencies=[], suggests=[],
                 supports_non_srcdir_builds=True):
        base.Package.__init__(self, name, dependencies, suggests)
        self.version      = version
        self.source_url   = source_url
        self.source_size  = source_size
        self.source_md5   = source_md5
        self.patches      = patches
        self.autogenargs  = autogenargs
        self.makeargs     = makeargs
        self.supports_non_srcdir_builds = supports_non_srcdir_builds

    def get_localfile(self, buildscript):
        localfile = os.path.join(buildscript.config.tarballdir,
                                 os.path.basename(self.source_url))
        return localfile

    def get_srcdir(self, buildscript):
        localdir = os.path.join(buildscript.config.checkoutroot,
                                os.path.basename(self.source_url))
        # strip off packaging extension ...
        if localdir.endswith('.tar.gz'):
            localdir = localdir[:-7]
        elif localdir.endswith('.tar.bz2'):
            localdir = localdir[:-8]
        elif localdir.endswith('.tgz'):
            localdir = localdir[:-4]
        return localdir
    def get_builddir(self, buildscript):
        srcdir = self.get_srcdir(buildscript)
        if buildscript.config.buildroot and \
               self.supports_non_srcdir_builds:
            d = buildscript.config.builddir_pattern % os.path.basename(srcdir)
            return os.path.join(buildscript.config.buildroot, d)
        else:
            return srcdir

    def get_revision(self):
        return self.version

    def check_localfile(self, buildscript):
        '''returns None if local copy of tarball is okay.  Otherwise,
        returns a string error message.'''
        localfile = self.get_localfile(buildscript)
        if not os.path.exists(localfile):
            return 'file not downloaded'
        if self.source_size:
            local_size = os.stat(localfile)[6]
            if local_size != self.source_size:
                return 'downloaded file of incorrect size ' \
                       '(expected %d, got %d)' % (self.source_size, local_size)
        if self.source_md5:
            import md5
            sum = md5.new()
            fp = open(localfile, 'rb')
            data = fp.read(4096)
            while data:
                sum.update(data)
                data = fp.read(4096)
            fp.close()
            if sum.hexdigest() != self.source_md5:
                return 'file MD5 sum incorrect (expected %s, got %s)' % \
                       (self.source_md5, sum.hexdigest())

    def do_start(self, buildscript):
        # check if jhbuild previously built it ...
        checkoutdir = self.get_builddir(buildscript)
        if buildscript.packagedb.check(self.name, self.version):
            return (self.STATE_DONE, None, None)

        return (self.STATE_DOWNLOAD, None, None)

    def do_download(self, buildscript):
        localfile = self.get_localfile(buildscript)
        if not os.path.exists(buildscript.config.tarballdir):
            os.makedirs(buildscript.config.tarballdir)
        if not buildscript.config.nonetwork:
            if self.check_localfile(buildscript) is not None:
                # don't have a local copy
                buildscript.set_action('Downloading', self, action_target=self.source_url)
                res = buildscript.execute('wget "%s" -O "%s"' %
                                          (self.source_url, localfile))
                if res:
                    return (self.STATE_UNPACK, 'error downloading file', [])

        status = self.check_localfile(buildscript)
        if status is not None:
            return (self.STATE_UNPACK, status, [])
        return (self.STATE_UNPACK, None, None)

    def do_unpack(self, buildscript):
        os.chdir(buildscript.config.checkoutroot)
        localfile = self.get_localfile(buildscript)
        srcdir = self.get_srcdir(buildscript)

        buildscript.set_action('Unpacking', self)
        if localfile.endswith('.bz2'):
            res = buildscript.execute('bunzip2 -dc "%s" | tar xf -' % localfile)
        elif localfile.endswith('.gz'):
            res = buildscript.execute('gunzip -dc "%s" | tar xf -' % localfile)
        else:
            raise FatalError("don't know how to handle: %s" % localfile)
        
        if res or not os.path.exists(srcdir):
            return (self.STATE_PATCH, 'could not unpack tarball', [])

        return (self.STATE_PATCH, None, None)

    def do_patch(self, buildscript):
        os.chdir(self.get_srcdir(buildscript))
        
        for (patch, patchstrip) in self.patches:
            patchfile = os.path.join(jhbuild_directory, 'patches', patch)
            buildscript.set_action('Applying Patch', self, action_target=patch)
            res = buildscript.execute('patch -p%d < "%s"' % (patchstrip,
                                                             patchfile))
            if res:
                return (self.STATE_CONFIGURE, 'could not apply patch', [])
            
        if buildscript.config.nobuild:
            return (self.STATE_DONE, None, None)
        else:
            return (self.STATE_CONFIGURE, None, None)

    def do_configure(self, buildscript):
        builddir = self.get_builddir(buildscript)
        if buildscript.config.buildroot and not os.path.exists(builddir):
            os.makedirs(builddir)
        os.chdir(builddir)
        buildscript.set_action('Configuring', self)
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            cmd = self.get_srcdir(buildscript) + '/configure'
        else:
            cmd = './configure'
        cmd += ' --prefix %s' % buildscript.config.prefix
        if buildscript.config.use_lib64:
            cmd += " --libdir '${exec_prefix}/lib64'"
        cmd += ' %s' % self.autogenargs
        res = buildscript.execute(cmd)
        error = None
        if res != 0:
            error = 'could not configure package'
        return (self.STATE_BUILD, error, [])

    def do_build(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Building', self)
        cmd = '%s %s' % (os.environ.get('MAKE', 'make'), self.makeargs)
        if buildscript.execute(cmd) == 0:
            return (self.STATE_INSTALL, None, None)
        else:
            return (self.STATE_INSTALL, 'could not build module', [])

    def do_install(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Installing', self)
        cmd = '%s %s install' % (os.environ.get('MAKE', 'make'), self.makeargs)
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
    source_md5 = None
    patches = []
    autogenargs = ''
    makeargs = ''
    supports_non_srcdir_builds = True
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
    if node.hasAttribute('supports-non-srcdir-builds'):
        supports_non_srcdir_builds = \
            (node.getAttribute('supports-non-srcdir-builds') != 'no')
    for childnode in node.childNodes:
        if childnode.nodeType != childnode.ELEMENT_NODE: continue
        if childnode.nodeName == 'source':
            source_url = childnode.getAttribute('href')
            if childnode.hasAttribute('size'):
                source_size = int(childnode.getAttribute('size'))
            if childnode.hasAttribute('md5sum'):
                source_md5 = childnode.getAttribute('md5sum')
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

    autogenargs += ' ' + config.module_autogenargs.get(name,
                                                       config.autogenargs)
    makeargs += ' ' + config.module_makeargs.get(name, makeargs)

    # for tarballs, don't ever pass --enable-maintainer-mode
    autogenargs = autogenargs.replace('--enable-maintainer-mode', '')

    return Tarball(name, version, source_url, source_size, source_md5,
                   patches, autogenargs, makeargs, dependencies, suggests,
                   supports_non_srcdir_builds=supports_non_srcdir_builds)

base.register_module_type('tarball', parse_tarball)
