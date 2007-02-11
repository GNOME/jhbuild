# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   tarball.py: some code to handle tarball repositories
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

__all__ = []
__metaclass__ = type

import os
import urlparse

from jhbuild.errors import FatalError, BuildStateError
from jhbuild.versioncontrol import Repository, Branch, register_repo_type

jhbuild_directory = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 '..', '..'))


class TarballRepository(Repository):
    """A class representing a Tarball repository.

    A repository implementation representing a web or ftp site hosting
    one or more tarballs for download.  The user can override the
    download location similar to how they can for other repository
    implementations.
    """

    init_xml_attrs = ['href']

    def __init__(self, config, name, href):
        Repository.__init__(self, config, name)
        # allow user to adjust location of branch.
        self.href = config.repos.get(name, href)

    branch_xml_attrs = ['version', 'module', 'checkoutdir',
                        'size', 'md5sum']

    def branch(self, name, version, module=None, checkoutdir=None,
               size=None, md5sum=None):
        if name in self.config.branches:
            module = self.config.branches[module]
        else:
            if module is None:
                module = name
            module = urlparse.urljoin(self.href, module)
        if size is not None:
            size = int(size)
        return TarballBranch(self, module=module, version=version,
                             checkoutdir=checkoutdir,
                             source_size=size, source_md5=md5sum)

    def branch_from_xml(self, name, branchnode):
        branch = Repository.branch_from_xml(self, name, branchnode)
        # patches represented as children of the branch node
        for childnode in branchnode.childNodes:
            if (childnode.nodeType == childnode.ELEMENT_NODE and
                childnode.nodeName == 'patch'):
                patchfile = childnode.getAttribute('file')
                if childnode.hasAttribute('strip'):
                    patchstrip = int(childnode.getAttribute('strip'))
                else:
                    patchstrip = 0
                branch.patches.append((patchfile, patchstrip))
        return branch


class TarballBranch(Branch):
    """A class representing a Tarball."""

    def __init__(self, repository, module, version, checkoutdir,
                 source_size, source_md5):
        self.repository = repository
        self.config = repository.config
        self.module = module
        self.version = version
        self.checkoutdir = checkoutdir
        self.source_size = source_size
        self.source_md5 = source_md5
        self.patches = []

    def _local_tarball(self):
        basename = os.path.basename(self.module)
        if not basename:
            raise FatalError('URL has no filename component: %s' % self.module)
        localfile = os.path.join(self.config.tarballdir, basename)
        return localfile
    _local_tarball = property(_local_tarball)

    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.config.checkoutroot, self.checkoutdir)

        localdir = os.path.join(self.config.checkoutroot,
                                os.path.basename(self.module))
        # strip off packaging extension ...
        if localdir.endswith('.tar.gz'):
            localdir = localdir[:-7]
        elif localdir.endswith('.tar.bz2'):
            localdir = localdir[:-8]
        elif localdir.endswith('.tgz'):
            localdir = localdir[:-4]
        elif localdir.endswith('.zip'):
            localdir = localdir[:-4]
        return localdir
    srcdir = property(srcdir)

    def branchname(self):
        return self.version
    branchname = property(branchname)

    def _check_tarball(self):
        """Check whether the tarball has been downloaded correctly."""
        localfile = self._local_tarball
        if not os.path.exists(localfile):
            raise BuildStateError('file not downloaded')
        if self.source_size is not None:
            local_size = os.stat(localfile).st_size
            if local_size != self.source_size:
                raise BuildStateError('downloaded file size is incorrect '
                                      '(expected %d, got %d)'
                                      % (self.source_size, local_size))
        if self.source_md5 is not None:
            import md5
            local_md5 = md5.new()
            fp = open(localfile, 'rb')
            data = fp.read(32768)
            while data:
                local_md5.update(data)
                data = fp.read(32768)
            fp.close()
            if local_md5.hexdigest() != self.source_md5:
                raise BuildStateError('file MD5 sum is incorrect '
                                      '(expected %s, got %s)'
                                      % (self.source_md5,
                                         local_md5.hexdigest()))

    def _download_and_unpack(self, buildscript):
        localfile = self._local_tarball
        if not os.path.exists(self.config.tarballdir):
            os.makedirs(self.config.tarballdir)
        try:
            self._check_tarball()
        except BuildStateError:
            # don't have the tarball, try downloading it and check again
            has_wget = not os.system('which wget > /dev/null')
            if not has_wget:
                has_curl = not os.system('which curl > /dev/null')

            if has_wget:
                res = buildscript.execute(
                        ['wget', self.module, '-O', localfile])
            elif has_curl:
                res = buildscript.execute(
                        ['curl', '-L', self.module, '-o', localfile])
            else:
                raise FatalError("unable to find wget or curl")

            self._check_tarball()

        # now to unpack it
        if localfile.endswith('.bz2'):
            buildscript.execute('bunzip2 -dc "%s" | tar xf -' % localfile,
                                cwd=self.config.checkoutroot)
        elif localfile.endswith('.gz') or localfile.endswith('.tgz'):
            buildscript.execute('gunzip -dc "%s" | tar xf -' % localfile,
                                cwd=self.config.checkoutroot)
        elif localfile.endswith('.zip'):
            buildscript.execute('unzip "%s"' % localfile,
                                cwd=self.config.checkoutroot)
        else:
            raise FatalError("don't know how to handle: %s" % localfile)

        if not os.path.exists(self.srcdir):
            raise BuildStateError('could not unpack tarball')

        # now patch the working tree
        for (patch, patchstrip) in self.patches:
            patchfile = os.path.join(jhbuild_directory, 'patches', patch)
            buildscript.execute('patch -p%d < "%s"'
                                % (patchstrip, patchfile),
                                cwd=self.srcdir)
                

    def checkout(self, buildscript):
        if not os.path.exists(self.srcdir):
            self._download_and_unpack(buildscript)

    def force_checkout(self, buildscript):
        self._download_and_unpack(buildscript)

    def tree_id(self):
        return self.version

register_repo_type('tarball', TarballRepository)
