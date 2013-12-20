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
import traceback
import logging

import gettext
import __builtin__
__builtin__.__dict__['N_'] = lambda x: x

import jhbuild.config
import jhbuild.commands
from jhbuild.errors import UsageError, FatalError
from jhbuild.utils.cmds import get_output
from jhbuild.moduleset import warn_local_modulesets


if sys.platform == 'darwin':
    # work around locale.getpreferredencoding() returning an empty string in
    # Mac OS X, see http://bugzilla.gnome.org/show_bug.cgi?id=534650 and
    # http://bazaar-vcs.org/DarwinCommandLineArgumentDecoding
    sys.platform = 'posix'
    try:
        import locale
    finally:
        sys.platform = 'darwin'
else:
    import locale

try:
    _encoding = locale.getpreferredencoding()
    assert _encoding
except (locale.Error, AssertionError):
    _encoding = 'ascii'

def uencode(s):
    if type(s) is unicode:
        return s.encode(_encoding, 'replace')
    else:
        return s

def udecode(s):
    if type(s) is not unicode:
        return s.decode(_encoding, 'replace')
    else:
        return s

def uprint(*args):
    '''Print Unicode string encoded for the terminal'''
    for s in args[:-1]:
        print uencode(s),
    s = args[-1]
    print uencode(s)

__builtin__.__dict__['uprint'] = uprint
__builtin__.__dict__['uencode'] = uencode
__builtin__.__dict__['udecode'] = udecode

class LoggingFormatter(logging.Formatter):
    def __init__(self):
        logging.Formatter.__init__(self, '%(level_name_initial)s: %(message)s')

    def format(self, record):
        record.level_name_initial = record.levelname[0]
        return logging.Formatter.format(self, record)

def print_help(parser):
    parser.print_help()
    print
    jhbuild.commands.print_help()
    parser.exit()

def main(args):
    localedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mo'))
    if not os.path.exists(localedir):
        localedir = None
    gettext.install('jhbuild', localedir=localedir, unicode=True)

    if hasattr(os, 'getuid') and os.getuid() == 0:
        sys.stderr.write(_('You should not run jhbuild as root.\n').encode(_encoding, 'replace'))
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
    parser.add_option('--conditions', action='append',
                      dest='conditions', default=[],
                      help=_('modify the condition set'))

    options, args = parser.parse_args(args)

    try:
        config = jhbuild.config.Config(options.configfile, options.conditions)
    except FatalError, exc:
        sys.stderr.write('jhbuild: %s\n' % exc.args[0].encode(_encoding, 'replace'))
        sys.exit(1)

    if options.moduleset: config.moduleset = options.moduleset
    if options.nointeract: config.interact = False

    if not args or args[0][0] == '-':
        command = 'build' # default to cvs update + compile
    else:
        command = args[0]
        args = args[1:]

    warn_local_modulesets(config)

    try:
        rc = jhbuild.commands.run(command, config, args, help=lambda: print_help(parser))
    except UsageError, exc:
        sys.stderr.write('jhbuild %s: %s\n' % (command, exc.args[0].encode(_encoding, 'replace')))
        parser.print_usage()
        sys.exit(1)
    except FatalError, exc:
        sys.stderr.write('jhbuild %s: %s\n' % (command, exc.args[0].encode(_encoding, 'replace')))
        sys.exit(1)
    except KeyboardInterrupt:
        uprint(_('Interrupted'))
        sys.exit(1)
    except EOFError:
        uprint(_('EOF'))
        sys.exit(1)
    except IOError, e:
        if e.errno != errno.EPIPE:
            raise
        sys.exit(0)
    if rc:
        sys.exit(rc)

