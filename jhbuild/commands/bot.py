# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2008 Frederic Peters
#
#   bot.py: buildbot control commands
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
#
# Some methods are derived from Buildbot own methods (when it was not possible
# to override just some parts of them).  Buildbot is also licensed under the
# GNU General Public License.

from optparse import make_option

from jhbuild.commands import Command, register_command
from jhbuild.errors import FatalError
from jhbuild.utils import N_, _


class cmd_bot(Command):
    doc = N_('Control buildbot')

    name = 'bot'
    usage_args = N_('[ options ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('--setup',
                        action='store_true', dest='setup', default=False,
                        help=_('setup a buildbot environment')),
            make_option('--start',
                        action='store_true', dest='start', default=False,
                        help=_('start a buildbot slave server')),
            make_option('--stop',
                        action='store_true', dest='stop', default=False,
                        help=_('stop a buildbot slave server')),
            make_option('--start-server',
                        action='store_true', dest='start_server', default=False,
                        help=_('start a buildbot master server')),
            make_option('--reload-server-config',
                        action='store_true', dest='reload_server_config', default=False,
                        help=_('reload a buildbot master server configuration')),
            make_option('--stop-server',
                        action='store_true', dest='stop_server', default=False,
                        help=_('stop a buildbot master server')),
            make_option('--daemon',
                        action='store_true', dest='daemon', default=False,
                        help=_('start as daemon')),
            make_option('--pidfile', metavar='PIDFILE',
                        action='store', dest='pidfile', default=None,
                        help=_('PID file location')),
            make_option('--logfile', metavar='LOGFILE',
                        action='store', dest='logfile', default=None,
                        help=_('log file location')),
            make_option('--slaves-dir', metavar='SLAVESDIR',
                        action='store', dest='slaves_dir', default=None,
                        help=_('directory with slave files (only with --start-server)')),
            make_option('--buildbot-dir', metavar='BUILDBOTDIR',
                        action='store', dest='buildbot_dir', default=None,
                        help=_('directory with buildbot work files (only with --start-server)')),
            make_option('--mastercfg', metavar='CFGFILE',
                        action='store', dest='mastercfgfile', default=None,
                        help=_('master cfg file location (only with --start-server)')),
            make_option('--step',
                        action='store_true', dest='step', default=False,
                        help=_('exec a buildbot step (internal use only)')),
            ])

    def run(self, config, options, args, help=None):
        raise FatalError(_('buildbot commands are no longer supported'))

register_command(cmd_bot)
