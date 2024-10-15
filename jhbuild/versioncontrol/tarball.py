# jhbuild - a tool to ease building collections of source packages
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
import hashlib
import logging
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from jhbuild.errors import FatalError, CommandError, BuildStateError
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.utils.cmds import has_command, get_output
from jhbuild.utils.unpack import unpack_archive
from jhbuild.utils import _
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
                        'hash', 'rename-tarball']

    def branch(self, name, version, module=None, checkoutdir=None,
               size=None, md5sum=None, hash=None, branch_id=None,
               source_subdir=None, rename_tarball=None):
        if name in self.config.branches:
            module = self.config.branches[name]
            if not module:
                raise FatalError(_('branch for %(name)s has wrong override, check your %(filename)s') % \
                                 {'name'     : name,
                                  'filename' : self.config.filename})
        else:
            module = module or name
            module = urllib.parse.urljoin(self.href, module)

        module, checkoutdir = self.eval_version(module, checkoutdir, version)

        if size is not None:
            size = int(size)
        if md5sum and not hash:
            hash = 'md5:' + md5sum
        if rename_tarball is not None:
            rename_tarball = rename_tarball.replace('${name}', name).replace('${version}', version)
        return TarballBranch(self, module=module, version=version,
                             checkoutdir=checkoutdir,
                             source_size=size, source_hash=hash,
                             branch_id=branch_id, source_subdir=source_subdir,
                             tarball_name=rename_tarball)

    def to_sxml(self):
        return [sxml.repository(type='tarball', name=self.name, href=self.href)]


class TarballBranch(Branch):
    """A class representing a Tarball."""

    def __init__(self, repository, module, version, checkoutdir,
                 source_size, source_hash, branch_id, source_subdir=None,
                 tarball_name=None):
        Branch.__init__(self, repository, module, checkoutdir)
        self.version = version
        self.source_size = source_size
        self.source_hash = source_hash
        self.quilt = None
        self.branch_id = branch_id
        self.source_subdir = source_subdir
        self.tarball_name = tarball_name

    @property
    def _local_tarball(self):
        if self.tarball_name:
            return os.path.join(self.config.tarballdir, self.tarball_name)
        basename = os.path.basename(self.module)
        if not basename:
            raise FatalError(_('URL has no filename component: %s') % self.module)
        localfile = os.path.join(self.config.tarballdir, basename)
        return localfile

    @property
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

    @property
    def srcdir(self):
        if self.source_subdir:
            return os.path.join(self.raw_srcdir, self.source_subdir)
        return self.raw_srcdir

    @property
    def branchname(self):
        return self.version

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
        if not os.access(self.config.tarballdir, os.R_OK|os.W_OK|os.X_OK):
            raise FatalError(_('tarball dir (%s) must be writable') % self.config.tarballdir)
        """Downloads the tarball off the internet, using wget or curl."""
        extra_env = {
            'LD_LIBRARY_PATH': os.environ.get('UNMANGLED_LD_LIBRARY_PATH'),
            'PATH': os.environ.get('UNMANGLED_PATH')
            }
        lines = [
            ['wget', '--continue', self.module, '-O', localfile],
            ['curl', '--retry', '5', '--fail', '--continue-at', '-', '-L', self.module, '-o', localfile]
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
        try:
            self._check_tarball()
        except BuildStateError:
            # don't have the tarball, try downloading it and check again
            self._download_tarball(buildscript, localfile)
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
        patch_files = self.get_patch_files(buildscript)
        for (patchfile, patch, patchstrip) in patch_files:
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

    def _export(self, buildscript):
        filename = os.path.basename(self.raw_srcdir) + '.zip'

        if self.config.export_dir is not None:
            path = os.path.join(self.config.export_dir, filename)
        else:
            path = os.path.join(self.checkoutroot, filename)

        with zipfile.ZipFile(path, 'w') as zipped_path:
            patch_files = self.get_patch_files(buildscript)
            for (patchfile, patch, patchstrip) in patch_files:
                zipped_path.write(patchfile, arcname='patches/' + patch)

            zipped_path.write(self._local_tarball, arcname=os.path.basename(self._local_tarball))

    def checkout(self, buildscript):
        if self.checkout_mode == 'clobber':
            self._wipedir(buildscript, self.raw_srcdir)
        if not os.path.exists(self.srcdir):
            self._download_and_unpack(buildscript)
        if self.quilt:
            self._quilt_checkout(buildscript)

        if self.checkout_mode == 'export':
            self._export(buildscript)

    def may_checkout(self, buildscript):
        if os.path.exists(self._local_tarball):
            return True
        elif buildscript.config.nonetwork:
            return False
        return True

    def tree_id(self):
        md5sum = hashlib.md5()
        if self.patches:
            for patch in self.patches:
                md5sum.update(patch[0].encode("utf-8"))
        if self.quilt:
            md5sum.update(get_output('quilt files',
                        cwd=self.srcdir,
                        extra_env={'QUILT_PATCHES' : self.quilt.srcdir}).encode("utf-8"))
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
