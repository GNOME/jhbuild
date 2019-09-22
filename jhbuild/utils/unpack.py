# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2007  Alberto Ruiz <aruiz@gnome.org>
#
#   unpack.py: helper functions for unpacking compressed packages
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

import tarfile
import zipfile
import os.path
import tempfile

from jhbuild.utils.cmds import has_command
from jhbuild.errors import CommandError
from jhbuild.utils import fileutils, _


def unpack_tar_file(localfile, target_directory):
    pkg = tarfile.open(localfile, 'r|*')
    pkg.extractall(target_directory)
    pkg.close()


def unpack_zip_file(localfile, target_directory):
    # Attributes are stored in ZIP files in a host-dependent way.
    # The zipinfo.create_system value describes the host OS.
    # Known values:
    #   * 3 (UNIX)
    #   * 11 (undefined, seems to be UNIX)
    #   * 0 (MSDOS)
    # Reference: http://www.opennet.ru/docs/formats/zip.txt

    def attr_check_symlink(host, attr):
        if host == 0:
            return False
        return attr == 0xA1ED0000

    def attr_to_file_perm(host, attr):
        if host == 0:
            if attr & 1:
                perm = 0o444
            else:
                perm = 0o666
        else:
            perm = attr
            perm &= 0x08FF0000
            perm >>= 16
            perm |= 0x00000100
        return perm

    def attr_to_dir_perm(host, attr):
        if host == 0:
            # attr & 16 should be true (this is directory bit)
            if attr & 1:
                perm = 0o444
            else:
                perm = 0o666
        else:
            perm = attr
            perm &= 0xFFFF0000
            perm >>= 16
            perm |= 0x00000100
        return perm

    def makedirs(dir):
        if not os.path.isdir(dir):
            os.makedirs(dir)

    pkg = zipfile.ZipFile(localfile, 'r')
    for pkg_fileinfo in pkg.filelist:
        pkg_file = pkg_fileinfo.filename
        attr = pkg_fileinfo.external_attr
        chost = pkg_fileinfo.create_system

        # symbolic link
        if attr_check_symlink(chost, attr):
            # TODO: support symlinks in zipfiles
            continue

        # directory
        if pkg_file.endswith('/'):
            dir = os.path.join(target_directory, pkg_file)
            makedirs(dir)
            os.chmod(dir, attr_to_dir_perm(chost, attr))
            continue

        # file
        if '/' in pkg_file:
            dir = os.path.dirname(pkg_file)
            dir = os.path.join(target_directory, dir)
            makedirs(dir)

        data = pkg.read(pkg_file)
        file = open(os.path.join(target_directory, pkg_file), 'wb')
        file.write(data)
        file.close()

        os.chmod(os.path.join(target_directory, pkg_file), attr_to_file_perm(chost, attr))


def unpack_archive(buildscript, localfile, target_directory, checkoutdir=None):
    """
    Unpack @localfile to @target_directory; if @checkoutdir is specified make
    sure the unpacked content gets into a directory by that name
    """
    if checkoutdir:
        final_target_directory = target_directory
        target_directory = tempfile.mkdtemp(dir=final_target_directory)

    ext = os.path.splitext(localfile)[-1]
    if ext == '.lzma' and has_command('lzcat') and has_command('tar'):
        buildscript.execute('lzcat -d "%s" | tar xf -' % localfile,
                cwd=target_directory)
    elif ext == '.xz' and has_command('xzcat') and has_command('tar'):
        buildscript.execute('xzcat -d "%s" | tar xf -' % localfile,
                cwd=target_directory)
    elif ext == '.bz2' and has_command('bunzip2') and has_command('tar'):
        buildscript.execute('bunzip2 -dc "%s" | tar xf -' % localfile,
                cwd=target_directory)
    elif ext in ('.gz', '.tgz') and has_command('gzip') and has_command('tar'):
        buildscript.execute('gzip -dc "%s" | tar xf -' % localfile,
                cwd=target_directory)
    elif ext == '.zip' and has_command('unzip'):
        buildscript.execute('unzip "%s"' % localfile,
                cwd=target_directory)
    else:
        try:
            if tarfile.is_tarfile(localfile):
                unpack_tar_file(localfile, target_directory)
            elif zipfile.is_zipfile(localfile):
                unpack_zip_file(localfile, target_directory)
            else:
                raise CommandError(_('Failed to unpack %s (unknown archive type)') % localfile)
        except Exception:
            raise CommandError(_('Failed to unpack %s') % localfile)

    if checkoutdir:
        # tarball has been extracted in $destdir/$tmp/, check, then move the
        # content of that directory
        if len(os.listdir(target_directory)) == 0:
            raise CommandError(_('Failed to unpack %s (empty file?)') % localfile)
        if len(os.listdir(target_directory)) == 1:
            # a single directory, just move it
            tmpdirname = os.path.join(target_directory, os.listdir(target_directory)[0])
            fileutils.rename(tmpdirname, os.path.join(final_target_directory, checkoutdir))
            os.rmdir(target_directory)
        else:
            # more files, just rename the temporary directory to the final name
            fileutils.rename(target_directory, os.path.join(final_target_directory, checkoutdir))
