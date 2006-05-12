# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   errors.py: definitions of exceptions used by jhbuild modules
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

class UsageError(Exception):
    '''An exception that should result in a usage message rather than
    a full traceback.'''


class ConfigError(Exception):
    '''A problem in a configuration file.'''


class FatalError(Exception):
    '''An error not related to the user input.'''


class CommandError(Exception):
    '''An error occurred in an external command.'''

    def __init__(self, message, returncode=None):
        Exception.__init__(self, message)
        self.returncode = returncode

class BuildStateError(Exception):
    '''An error occurred while processing a build state.'''
