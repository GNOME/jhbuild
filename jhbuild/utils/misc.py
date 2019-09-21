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
import sys
import importlib
import pkgutil


def inpath(filename, path):
    for dir in path:
        if os.path.isfile(os.path.join(dir, filename)):
            return True
        # also check for filename.exe on Windows
        if sys.platform.startswith('win') and os.path.isfile(os.path.join(dir, filename + '.exe')):
            return True
    return False


def try_import_module(module_name):
    """Like importlib.import_module() but doesn't raise if the module doesn't exist"""

    if pkgutil.get_loader(module_name) is None:
        return
    return importlib.import_module(module_name)