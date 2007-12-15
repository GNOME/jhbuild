# jhbuild - a build script for GNOME 1.x and 2.x
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

from jhbuild.utils.cmds import has_command
from jhbuild.errors import CommandError


def unpack_tar_file(localfile, target_directory):
    pkg = tarfile.open(localfile, 'r|*')
    pkg.extractall(target_directory)
    pkg.close()


def unpack_zip_file(localfile, target_directory):
    def attr_check_symlink(attr):
        return attr == 0xA1ED0000

    def attr_to_file_perm(attr):
        perm = attr
        perm &= 0x08FF0000
        perm >>= 16
        perm |= 0x00000100
        return perm

    def attr_to_dir_perm(attr):
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

        # symbolic link
        if attr_check_symlink(attr):
            # TODO: support symlinks in zipfiles
            continue

        # directory
        if pkg_file.endswith('/'):
            dir = os.path.join(target_directory, pkg_file)
            makedirs(dir)
            os.chmod(dir, attr_to_dir_perm(attr))
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

        os.chmod(os.path.join(target_directory, pkg_file), attr_to_file_perm(attr))
        

def unpack_archive(buildscript, localfile, target_directory):
    ext = os.path.splitext(localfile)[-1]
    if ext == '.bz2' and has_command('bunzip2') and has_command('tar'):
        buildscript.execute('bunzip2 -dc "%s" | tar xf -' % localfile,
                cwd = target_directory)
    elif ext in ('.gz', '.tgz') and has_command('gunzip') and has_command('tar'):
        buildscript.execute('gunzip -dc "%s" | tar xf -' % localfile,
                cwd = target_directory)
    elif ext == '.zip' and has_command('unzip'):
        buildscript.execute('unzip "%s"' % localfile,
                cwd = target_directory)
    else:
        try:
            if tarfile.is_tarfile(localfile):
                unpack_tar_file(localfile, target_directory)
            elif zipfile.is_zipfile(localfile):
                unpack_zip_file(localfile, target_directory)    
            else:
                raise CommandError('Failed to unpack %s (unknown archive type)' % localfile)
        except:
            raise CommandError('Failed to unpack %s' % localfile)
