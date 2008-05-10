#!/usr/bin/env python
# jhbuild - a build script for GNOME 1.x and 2.x
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

import gettext
localedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../mo'))
gettext.install('messages', localedir=localedir, unicode=True)
import __builtin__
__builtin__.__dict__['N_'] = lambda x: x

import jhbuild.config
import jhbuild.commands
from jhbuild.errors import UsageError, FatalError

def help_commands(option, opt_str, value, parser):
    thisdir = os.path.abspath(os.path.dirname(__file__))
    
    # import all available commands
    for fname in os.listdir(os.path.join(thisdir, 'commands')):
        name, ext = os.path.splitext(fname)
        if not ext == '.py':
            continue
        try:
            __import__('jhbuild.commands.%s' % name)
        except ImportError:
            pass
    
    print _('JHBuild commands are:')
    commands = [(x.name, x.doc) for x in jhbuild.commands.get_commands().values()]
    commands.sort()
    for name, description in commands:
        print '  %-15s %s' % (name, description)
    print
    print _('For more information run "jhbuild <command> --help"')
    parser.exit()

def main(args):
    parser = optparse.OptionParser(
        usage=_('%prog [ -f config ] command [ options ... ]'),
        description=_('Build a set of modules from diverse repositories in correct dependency order (such as GNOME).'))
    parser.disable_interspersed_args()
    parser.add_option('--help-commands', action='callback',
                      callback=help_commands,
                      help=_('Information about available jhbuild commands'))
    parser.add_option('-f', '--file', action='store', metavar='CONFIG',
                      type='string', dest='configfile',
                      default=os.path.join(os.environ['HOME'], '.jhbuildrc'),
                      help=_('use a non default configuration file'))
    parser.add_option('-m', '--moduleset', action='store', metavar='URI',
                      type='string', dest='moduleset', default=None,
                      help=_('use a non default module set'))
    parser.add_option('--no-interact', action='store_true',
                      dest='nointeract', default=False,
                      help=_('do not prompt for input'))

    options, args = parser.parse_args(args)

    try:
        config = jhbuild.config.Config(options.configfile)
    except FatalError, exc:
        sys.stderr.write('jhbuild: %s\n' % (str(exc)))
        sys.exit(1)

    if options.moduleset: config.moduleset = options.moduleset
    if options.nointeract: config.interact = False

    if not args or args[0][0] == '-':
        command = 'build' # default to cvs update + compile
    else:
        command = args[0]
        args = args[1:]

    try:
        rc = jhbuild.commands.run(command, config, args)
    except UsageError, exc:
        sys.stderr.write('jhbuild %s: %s\n' % (command, str(exc)))
        parser.print_usage()
        sys.exit(1)
    except FatalError, exc:
        sys.stderr.write('jhbuild %s: %s\n' % (command, str(exc)))
        sys.exit(1)
    except KeyboardInterrupt:
        print "Interrupted"
        sys.exit(1)
    except EOFError:
        print "EOF"
        sys.exit(1)
    except IOError, e:
        if e.errno != errno.EPIPE:
            raise
        sys.exit(0)
    if rc:
        sys.exit(rc)

