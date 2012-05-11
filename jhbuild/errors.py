# jhbuild - a tool to ease building collections of source packages
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


class JhbuildException(Exception):
    pass


class UsageError(JhbuildException):
    '''An exception that should result in a usage message rather than
    a full traceback.'''


class ConfigError(JhbuildException):
    '''A problem in a configuration file.'''


class FatalError(JhbuildException):
    '''An error not related to the user input.'''


class CommandError(JhbuildException):
    '''An error occurred in an external command.'''

    def __init__(self, message, returncode=None):
        JhbuildException.__init__(self, message)
        self.returncode = returncode

class BuildStateError(JhbuildException):
    '''An error occurred while processing a build state.'''


class DependencyCycleError(JhbuildException):
    '''There is a dependency cycle in the module set'''

class UndefinedRepositoryError(FatalError):
    '''There is a module depending on an undefined repository'''

class SkipToPhase(Exception):
    def __init__(self, phase):
        Exception.__init__(self)
        self.phase = phase

class SkipToEnd(SkipToPhase):
    def __init__(self):
        SkipToPhase.__init__(self, None)
