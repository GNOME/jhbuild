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
import md5
import urlparse
import urllib2

from jhbuild.errors import FatalError, CommandError, BuildStateError
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.utils.cmds import has_command, get_output
from jhbuild.modtypes import get_branch
from jhbuild.utils.unpack import unpack_archive
from jhbuild.utils import httpcache

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
               size=None, md5sum=None, branch_id=None):
        if name in self.config.branches:
            module = self.config.branches[name]
        else:
            if module is None:
                module = name
            module = urlparse.urljoin(self.href, module)
        if size is not None:
            size = int(size)
        return TarballBranch(self, module=module, version=version,
                             checkoutdir=checkoutdir,
                             source_size=size, source_md5=md5sum,
                             branch_id=branch_id)

    def branch_from_xml(self, name, branchnode, repositories, default_repo):
        branch = Repository.branch_from_xml(self, name, branchnode, repositories, default_repo)
        # patches represented as children of the branch node
        for childnode in branchnode.childNodes:
            if childnode.nodeType != childnode.ELEMENT_NODE: continue
            if childnode.nodeName == 'patch':
                patchfile = childnode.getAttribute('file')
                if childnode.hasAttribute('strip'):
                    patchstrip = int(childnode.getAttribute('strip'))
                else:
                    patchstrip = 0
                branch.patches.append((patchfile, patchstrip))
            elif childnode.nodeName == 'quilt':
                branch.quilt = get_branch(childnode, repositories, default_repo)
        return branch


class TarballBranch(Branch):
    """A class representing a Tarball."""

    def __init__(self, repository, module, version, checkoutdir,
                 source_size, source_md5, branch_id):
        Branch.__init__(self, repository, module, checkoutdir)
        self.version = version
        self.source_size = source_size
        self.source_md5 = source_md5
        self.patches = []
        self.quilt = None
        self.branch_id = branch_id

    def _local_tarball(self):
        basename = os.path.basename(self.module)
        if not basename:
            raise FatalError('URL has no filename component: %s' % self.module)
        localfile = os.path.join(self.config.tarballdir, basename)
        return localfile
    _local_tarball = property(_local_tarball)

    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)

        localdir = os.path.join(self.checkoutroot,
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
            if has_command('wget'):
                res = buildscript.execute(
                        ['wget', self.module, '-O', localfile])
            elif has_command('curl'):
                res = buildscript.execute(
                        ['curl', '-L', self.module, '-o', localfile])
            else:
                raise FatalError("unable to find wget or curl")

            self._check_tarball()

        # now to unpack it
        try:
            unpack_archive(buildscript, localfile, self.checkoutroot)
        except CommandError:
            raise FatalError('failed to unpack %s' % localfile)

        if not os.path.exists(self.srcdir):
            raise BuildStateError('could not unpack tarball')

        if self.patches:
            self._do_patches(buildscript)

    def _do_patches(self, buildscript):
        # now patch the working tree
        for (patch, patchstrip) in self.patches:
            patchfile = ''
            if urlparse.urlparse(patch)[0]:
                # patch name has scheme, get patch from network
                try:
                    patchfile = httpcache.load(patch, nonetwork=buildscript.config.nonetwork)
                except urllib2.HTTPError, e:
                    return (self.STATE_CONFIGURE,
                            'could not download patch (error: %s)' % e.code, [])
                except urllib2.URLError, e:
                    return (self.STATE_CONFIGURE, 'could not download patch', [])
            elif self.repository.moduleset_uri:
                # get it relative to the moduleset uri, either in the same
                # directory or a patches/ subdirectory
                for patch_prefix in ('.', 'patches'):
                    uri = urlparse.urljoin(self.repository.moduleset_uri,
                            os.path.join(patch_prefix, patch))
                    try:
                        patchfile = httpcache.load(uri, nonetwork=buildscript.config.nonetwork)
                    except Exception, e:
                        continue
                    if not os.path.isfile(patchfile):
                        continue
                    break
                else:
                    # not found, fallback to jhbuild provided patches
                    patchfile = os.path.join(jhbuild_directory, 'patches', patch)
            else:
                # nothing else, use jbuild provided patches
                patchfile = os.path.join(jhbuild_directory, 'patches', patch)

            buildscript.set_action('Applying patch', self, action_target=patch)
            buildscript.execute('patch -p%d < "%s"'
                                % (patchstrip, patchfile),
                                cwd=self.srcdir)

    def _quilt_checkout(self, buildscript):
        if not has_command('quilt'):
            raise FatalError("unable to find quilt")

        if os.path.exists(self.quilt.srcdir) and \
           os.path.exists(os.path.join(self.srcdir, '.pc/applied-patches')):
            buildscript.execute('quilt pop -a',
                                cwd=self.srcdir,
                                extra_env={'QUILT_PATCHES' : self.quilt.srcdir})

        self.quilt.checkout(buildscript)

        if not os.path.exists(self.quilt.srcdir):
            raise FatalError('could not checkout quilt patch set')

        buildscript.execute('quilt push -a',
                            cwd=self.srcdir,
                            extra_env={'QUILT_PATCHES' : self.quilt.srcdir})

    def checkout(self, buildscript):
        if self.checkout_mode == 'clobber':
            self._wipedir(buildscript)
        if not os.path.exists(self.srcdir):
            self._download_and_unpack(buildscript)
        if self.quilt:
            self._quilt_checkout(buildscript)

    def force_checkout(self, buildscript):
        self._wipedir(buildscript)
        self._download_and_unpack(buildscript)
        if self.quilt:
            self._quilt_checkout(buildscript)

    def tree_id(self):
        md5sum = md5.new()
        if self.patches:
            for patch in self.patches:
                md5sum.update(patch[0])
        if self.quilt:
            md5sum.update(get_output('quilt files',
                        cwd=self.srcdir,
                        extra_env={'QUILT_PATCHES' : self.quilt.srcdir}))
        return '%s-%s' % (self.version, md5sum.hexdigest())

register_repo_type('tarball', TarballRepository)
