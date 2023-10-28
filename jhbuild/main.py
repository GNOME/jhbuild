# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   main.py: parses command line arguments and starts the build
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

import sys, os, errno
import optparse
import logging

import gettext

import jhbuild.config
import jhbuild.commands
from jhbuild.errors import UsageError, FatalError
from jhbuild.utils import uprint, install_translation, _
from jhbuild.moduleset import warn_local_modulesets


class LoggingFormatter(logging.Formatter):
    def __init__(self):
        logging.Formatter.__init__(self, '%(level_name_initial)s: %(message)s')

    def format(self, record):
        record.level_name_initial = record.levelname[0]
        return logging.Formatter.format(self, record)

def print_help(parser):
    parser.print_help()
    print()
    jhbuild.commands.print_help()
    parser.exit()

def main(args):
    if DATADIR is not None:
        localedir = os.path.join(DATADIR, 'locale')
    else:
        localedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mo'))

    if not os.path.exists(localedir):
        localedir = None
    install_translation(gettext.translation('jhbuild', localedir=localedir, fallback=True))

    if 'JHBUILD_RUN_AS_ROOT' not in os.environ and hasattr(os, 'getuid') and os.getuid() == 0:
        uprint(_('You should not run jhbuild as root.\n'), file=sys.stderr)
        sys.exit(1)

    logging.getLogger().setLevel(logging.INFO)
    logging_handler = logging.StreamHandler()
    logging_handler.setFormatter(LoggingFormatter())
    logging.getLogger().addHandler(logging_handler)
    parser = optparse.OptionParser(
        usage=_('%prog [ -f config ] command [ options ... ]'),
        add_help_option=False,
        description=_('Build a set of modules from diverse repositories in correct dependency order (such as GNOME).'))
    parser.disable_interspersed_args()

    parser.add_option('-h', '--help', action='callback',
                      callback=lambda *args: print_help(parser),
                      help=_("Display this help and exit"))
    parser.add_option('--help-commands', action='callback',
                      callback=lambda *args: print_help(parser),
                      help=optparse.SUPPRESS_HELP)
    parser.add_option('-f', '--file', action='store', metavar='CONFIG',
                      type='string', dest='configfile',
                      default=os.environ.get("JHBUILDRC"),
                      help=_('use a non default configuration file'))
    parser.add_option('-m', '--moduleset', action='store', metavar='URI',
                      type='string', dest='moduleset', default=None,
                      help=_('use a non default module set'))
    parser.add_option('--no-interact', action='store_true',
                      dest='nointeract', default=False,
                      help=_('do not prompt for input'))
    parser.add_option('--exit-on-error', action='store_true',
                      dest='exit_on_error', default=False,
                      help=_('exit immediately when the build fails'))
    parser.add_option('--conditions', action='append',
                      dest='conditions', default=[],
                      help=_('modify the condition set'))

    options, args = parser.parse_args(args)

    try:
        config = jhbuild.config.Config(options.configfile, options.conditions)
    except FatalError as exc:
        uprint('jhbuild: %s\n' % exc.args[0], file=sys.stderr)
        sys.exit(1)

    if options.moduleset:
        config.moduleset = options.moduleset
    if options.nointeract:
        config.interact = False
    if options.exit_on_error:
        config.exit_on_error = True

    if not args or args[0][0] == '-':
        command = 'help'
    else:
        command = args[0]
        args = args[1:]

    warn_local_modulesets(config)

    try:
        rc = jhbuild.commands.run(command, config, args, help=lambda: print_help(parser))
    except UsageError as exc:
        uprint('jhbuild %s: %s\n' % (command, exc.args[0]), file=sys.stderr)
        parser.print_usage()
        sys.exit(1)
    except FatalError as exc:
        uprint('jhbuild %s: %s\n' % (command, exc.args[0]), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        uprint(_('Interrupted'))
        sys.exit(1)
    except EOFError:
        uprint(_('EOF'))
        sys.exit(1)
    except IOError as e:
        if e.errno != errno.EPIPE:
            raise
        sys.exit(0)
    if rc:
        sys.exit(rc)

