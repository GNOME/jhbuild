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
try:
    import hashlib
except ImportError:
    import md5 as hashlib
import urlparse
import urllib2
import logging

from jhbuild.errors import FatalError, CommandError, BuildStateError
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.utils.cmds import has_command, get_output
from jhbuild.modtypes import get_branch
from jhbuild.utils.unpack import unpack_archive
from jhbuild.utils import httpcache
from jhbuild.utils.sxml import sxml


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
                        'size', 'md5sum', 'source-subdir',
                        'hash']

    def branch(self, name, version, module=None, checkoutdir=None,
               size=None, md5sum=None, hash=None, branch_id=None,
               source_subdir=None):
        if name in self.config.branches:
            module = self.config.branches[name]
            if not module:
                raise FatalError(_('branch for %s has wrong override, check your .jhbuildrc') % name)
        else:
            if module is None:
                module = name
            module = urlparse.urljoin(self.href, module)
        if size is not None:
            size = int(size)
        if md5sum and (not hash or hashlib.__name__ == 'md5'):
            hash = 'md5:' + md5sum
        return TarballBranch(self, module=module, version=version,
                             checkoutdir=checkoutdir,
                             source_size=size, source_hash=hash,
                             branch_id=branch_id, source_subdir=source_subdir)

    def branch_from_xml(self, name, branchnode, repositories, default_repo):
        try:
            branch = Repository.branch_from_xml(self, name, branchnode, repositories, default_repo)
        except TypeError:
            raise FatalError(_('branch for %s is not correct, check the moduleset file.') % name)
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

    def to_sxml(self):
        return [sxml.repository(type='tarball', name=self.name, href=self.href)]


class TarballBranch(Branch):
    """A class representing a Tarball."""

    def __init__(self, repository, module, version, checkoutdir,
                 source_size, source_hash, branch_id, source_subdir=None):
        Branch.__init__(self, repository, module, checkoutdir)
        self.version = version
        self.source_size = source_size
        self.source_hash = source_hash
        self.patches = []
        self.quilt = None
        self.branch_id = branch_id
        self.source_subdir = source_subdir

    def _local_tarball(self):
        basename = os.path.basename(self.module)
        if not basename:
            raise FatalError(_('URL has no filename component: %s') % self.module)
        localfile = os.path.join(self.config.tarballdir, basename)
        return localfile
    _local_tarball = property(_local_tarball)

    def raw_srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)

        localdir = os.path.join(self.checkoutroot,
                                os.path.basename(self.module))
        # strip off packaging extension ...
        if localdir.endswith('.tar.gz'):
            localdir = localdir[:-7]
        elif localdir.endswith('.tar.bz2'):
            localdir = localdir[:-8]
        elif localdir.endswith('.tar.lzma'):
            localdir = localdir[:-9]
        elif localdir.endswith('.tar.xz'):
            localdir = localdir[:-7]
        elif localdir.endswith('.tgz'):
            localdir = localdir[:-4]
        elif localdir.endswith('.zip'):
            localdir = localdir[:-4]
        if localdir.endswith('.src'):
            localdir = localdir[:-4]
        return localdir
    raw_srcdir = property(raw_srcdir)

    def srcdir(self):
        if self.source_subdir:
            return os.path.join(self.raw_srcdir, self.source_subdir)
        return self.raw_srcdir
    srcdir = property(srcdir)

    def branchname(self):
        return self.version
    branchname = property(branchname)

    def _check_tarball(self):
        """Check whether the tarball has been downloaded correctly."""
        localfile = self._local_tarball
        if not os.path.exists(localfile):
            raise BuildStateError(_('file not downloaded'))
        if self.source_size is not None:
            local_size = os.stat(localfile).st_size
            if local_size != self.source_size:
                raise BuildStateError(
                        _('downloaded file size is incorrect (expected %(size1)d, got %(size2)d)')
                                      % {'size1':self.source_size, 'size2':local_size})
        if self.source_hash is not None:
            try:
                algo, hash = self.source_hash.split(':')
            except ValueError:
                logging.warning(_('invalid hash attribute on module %s') % self.module)
                return
            if hasattr(hashlib, algo):
                local_hash = getattr(hashlib, algo)()

                fp = open(localfile, 'rb')
                data = fp.read(32768)
                while data:
                    local_hash.update(data)
                    data = fp.read(32768)
                fp.close()
                if local_hash.hexdigest() != hash:
                    raise BuildStateError(
                            _('file hash is incorrect (expected %(sum1)s, got %(sum2)s)')
                            % {'sum1':hash, 'sum2':local_hash.hexdigest()})
            else:
                logging.warning(_('skipped hash check (missing support for %s)') % algo)

    def _download_tarball(self, buildscript, localfile):
        """Downloads the tarball off the internet, using wget or curl."""
        extra_env = {
            'LD_LIBRARY_PATH': os.environ.get('UNMANGLED_LD_LIBRARY_PATH'),
            'PATH': os.environ.get('UNMANGLED_PATH')
            }
        lines = [
            ['wget', '--continue', self.module, '-O', localfile],
            ['curl', '--continue-at', '-', '-L', self.module, '-o', localfile]
            ]
        lines = [line for line in lines if has_command(line[0])]
        if not lines:
            raise FatalError(_("unable to find wget or curl"))
        try:
            return buildscript.execute(lines[0], extra_env = extra_env)
        except CommandError:
            # Cleanup potential leftover file
            if os.path.exists(localfile):
                os.remove(localfile)
            raise

    def _download_and_unpack(self, buildscript):
        localfile = self._local_tarball
        if not os.path.exists(self.config.tarballdir):
            try:
                os.makedirs(self.config.tarballdir)
            except OSError:
                raise FatalError(
                        _('tarball dir (%s) can not be created') % self.config.tarballdir)
        if not os.access(self.config.tarballdir, os.R_OK|os.W_OK|os.X_OK):
            raise FatalError(_('tarball dir (%s) must be writable') % self.config.tarballdir)
        try:
            self._check_tarball()
        except BuildStateError:
            # don't have the tarball, try downloading it and check again
            res = self._download_tarball(buildscript, localfile)
            self._check_tarball()

        # now to unpack it
        try:
            unpack_archive(buildscript, localfile, self.checkoutroot, self.checkoutdir)
        except CommandError:
            raise FatalError(_('failed to unpack %s') % localfile)

        if not os.path.exists(self.srcdir):
            raise BuildStateError(_('could not unpack tarball (expected %s dir)'
                        ) % os.path.basename(self.srcdir))

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
                    raise BuildStateError(_('could not download patch (error: %s)') % e.code)
                except urllib2.URLError, e:
                    raise BuildStateError(_('could not download patch'))
            elif self.repository.moduleset_uri:
                # get it relative to the moduleset uri, either in the same
                # directory or a patches/ subdirectory
                for patch_prefix in ('.', 'patches', '../patches'):
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
                    patchfile = ''

            if not patchfile:
                # nothing else, use jhbuild provided patches
                possible_locations = []
                if self.config.modulesets_dir:
                    possible_locations.append(os.path.join(self.config.modulesets_dir, 'patches'))
                    possible_locations.append(os.path.join(self.config.modulesets_dir, '../patches'))
                if PKGDATADIR:
                    possible_locations.append(os.path.join(PKGDATADIR, 'patches'))
                if SRCDIR:
                    possible_locations.append(os.path.join(SRCDIR, 'patches'))
                for dirname in possible_locations:
                    patchfile = os.path.join(dirname, patch)
                    if os.path.exists(patchfile):
                        break
                else:
                    raise CommandError(_('Failed to find patch: %s') % patch)

            buildscript.set_action(_('Applying patch'), self, action_target=patch)
            # patchfile can be a relative file
            buildscript.execute('patch -p%d < "%s"'
                                % (patchstrip, os.path.abspath(patchfile)),
                                cwd=self.raw_srcdir)

    def _quilt_checkout(self, buildscript):
        if not has_command('quilt'):
            raise FatalError(_("unable to find quilt"))

        if os.path.exists(self.quilt.srcdir) and \
           os.path.exists(os.path.join(self.srcdir, '.pc/applied-patches')):
            buildscript.execute('quilt pop -a',
                                cwd=self.srcdir,
                                extra_env={'QUILT_PATCHES' : self.quilt.srcdir})

        self.quilt.checkout(buildscript)

        if not os.path.exists(self.quilt.srcdir):
            raise FatalError(_('could not checkout quilt patch set'))

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

    def tree_id(self):
        md5sum = hashlib.md5()
        if self.patches:
            for patch in self.patches:
                md5sum.update(patch[0])
        if self.quilt:
            md5sum.update(get_output('quilt files',
                        cwd=self.srcdir,
                        extra_env={'QUILT_PATCHES' : self.quilt.srcdir}))
        return '%s-%s' % (self.version, md5sum.hexdigest())

    def to_sxml(self):
        return ([sxml.branch(module=self.module,
                             repo=self.repository.name,
                             version=self.version,
                             size=str(self.source_size),
                             hash=self.source_hash)]
                + [[sxml.patch(file=patch, strip=str(strip))]
                   for patch, strip in self.patches])


register_repo_type('tarball', TarballRepository)
