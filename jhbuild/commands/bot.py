# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2008 Frederic Peters
#
#   bot.py: buildbot slave commands
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

import os
import urllib
from optparse import make_option

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.commands import Command, register_command
from jhbuild.commands.base import cmd_build

class cmd_bot(Command):
    doc = _('Control buildbot slave')

    name = 'bot'
    usage_args = '[ options ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('--setup',
                        action='store_true', dest='setup', default=False,
                        help=_('create a new instance')),
            make_option('--start',
                        action='store_true', dest='start', default=False,
                        help=_('start an instance')),
            make_option('--stop',
                        action='store_true', dest='stop', default=False,
                        help=_('stop an instance')),
            make_option('--log',
                        action='store_true', dest='log', default=False,
                        help=_('watch the log of a running instance')),
            ])

    def run(self, config, options, args):
        if options.setup:
            return self.setup(config)

    def setup(self, config):
        module_set = jhbuild.moduleset.load(config, 'buildbot')
        module_list = module_set.get_module_list('all', config.skip)
        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()


register_command(cmd_bot)

