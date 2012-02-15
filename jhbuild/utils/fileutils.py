# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2011 Red Hat, Inc.
#
#   fileutils.py - Helper functions for filesystem operations
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
#
# Author: Colin Walters <walters@verbum.org>

import os
import sys

def _accumulate_dirtree_contents_recurse(path, contents):
    names = os.listdir(path)
    for name in names:
        subpath = os.path.join(path, name)
        if os.path.isdir(subpath):
            previous_len = len(contents)
            _accumulate_dirtree_contents_recurse(subpath, contents)
            new_len = len(contents)
            # Only add if the directory is empty, otherwise, its existence
            # is implicit.
            if previous_len == new_len:
                contents.append(subpath + os.sep)
        else:
            contents.append(subpath)

def accumulate_dirtree_contents(path):
    """Return a list of files and empty directories in the directory at PATH.  Each item
in the returned list is relative to the root path."""
    contents = []
    _accumulate_dirtree_contents_recurse(path, contents)
    if not path.endswith(os.sep):
        path = path + os.sep
    pathlen = len(path)
    for i,subpath in enumerate(contents):
        assert subpath.startswith(path)
        contents[i] = subpath[pathlen:]
    return contents

def remove_files_and_dirs(file_paths, allow_nonempty_dirs=False):
    """Given a list of file paths in any order, attempt to delete
them.  The main intelligence in this function is removing files
in a directory before removing the directory.

Returns a list, where each item is a 2-tuple:
(path, error_string or None)"""

    results = []

    for path in reversed(sorted(file_paths)):
        isdir = os.path.isdir(path)
        try:
            if isdir:
                os.rmdir(path)
            else:
                os.unlink(path)
            results.append((path, True, ''))
        except OSError, e:
            if (isdir
                and allow_nonempty_dirs
                and len(os.listdir(path)) > 0):
                results.append((path, False, None))
            else:
                results.append((path, False, e.strerror))
    return results

def filter_files_by_prefix(config, file_paths):
    """Return the set of files in file_paths that are inside the prefix."""
    canon_prefix = config.prefix
    if not canon_prefix.endswith(os.sep):
        canon_prefix = canon_prefix + os.sep
    result = []
    for path in file_paths:
        if path == canon_prefix or (not path.startswith(canon_prefix)):
            continue
        result.append(path)
    return result

