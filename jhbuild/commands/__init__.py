# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   __init__.py: a package holding the various jhbuild subcommands
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

__metaclass__ = type
__all__ = [
    'Command',
    'register_command',
    'run'
    ]

import optparse

from jhbuild.errors import UsageError, FatalError


class Command:
    """Base class for Command objects"""

    name = None
    usage_args = '[ options ... ]'

    def __init__(self, options=[]):
        self.options = options

    def execute(self, config, args):
        options, args = self.parse_args(args)
        return self.run(config, options, args)

    def parse_args(self, args):
        parser = optparse.OptionParser(
            usage='%%prog %s %s' % (self.name, self.usage_args),
            description=self.__doc__)
        parser.add_options(self.options)
        return parser.parse_args(args)

    def run(self, config, options, args):
        """The body of the command"""
        raise NotImplementedError


# handle registration of new commands
_commands = {}
def register_command(command_class):
    _commands[command_class.name] = command_class

def run(command, config, args):
    # if the command hasn't been registered, load a module by the same name
    if command not in _commands:
        try:
            __import__('jhbuild.commands.%s' % command)
        except ImportError:
            pass
    if command not in _commands:
        raise FatalError('command not found')

    command_class = _commands[command]
    cmd = command_class()
    return cmd.execute(config, args)


from jhbuild.commands import base
