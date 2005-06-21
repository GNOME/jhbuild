# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2005  James Henstridge
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

# extras not found in old versions of Python

# add True and False constants, for the benefit of Python < 2.2.1
import __builtin__
if not hasattr(__builtin__, 'True'):
    __builtin__.True = (1 == 1)
    __builtin__.False = (1 != 1)

## if not hasattr(__builtin__, 'enumerate'):
##     def enumerate(iterable):
##         index = 0
##         for item in iterable:
##             yield (index, item)
##             index += 1
##     __builtin__.enumerate = enumerate

