#!/usr/bin/env python
# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
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

import sys, os, string, getopt

import jhbuild.config
import jhbuild.commands

BuildScript = None

usage = 'usage: jhbuild [ -f config ] command [ options ... ]'
help = '''Build a set of CVS modules (such as GNOME).

Global options:
  -f, --file=CONFIG            specify an alternative configuration file
      --no-interact            do not prompt for input

Commands:
  gui                          build targets from a gui app
  update                       update from cvs
  updateone modules            update a fixed set of modules.
  build [ opts... ] [modules]  update and compile (the default)
  buildone [ opts... ] modules build a single module
  run program [ args... ]      run a command in the build environment
  shell                        start a shell in the build environment
  bootstrap                    build required support tools.
  list [ opts ... ] [modules]  list what modules would be built
  dot [modules]                output a dot file of dependencies suitable
                               for processing with graphviz.

Options valid for the update, build and buildone commands:
  -s, --skip=MODULES           treat the given modules (and deps) as up to date
  -t, --start-at=MODULE        start building at the given module

Options valid for the build and buildone commands:
  -a, --autogen                Always run autogen.sh
  -c, --clean                  run make clean before make
  -n, --no-network             skip cvs update

Options valid for the list command:
  -r, --show-branch            show which revision will be built
''' # for xemacs/jed "

def main(args):
    try:
        opts, args = getopt.getopt(args, 'f:',
                                   ['file=', 'no-interact', 'help'])
    except getopt.error, exc:
        sys.stderr.write('jhbuild: %s\n' % str(exc))
        sys.stderr.write(usage + '\n')
        sys.exit(1)


    nointeract = False
    configfile = os.path.join(os.environ['HOME'], '.jhbuildrc')

    for opt, arg in opts:
        if opt == '--help':
            print usage
            print help
            sys.exit(0)
        elif opt in ('-f', '--file'):
            configfile = arg
        elif opt == '--no-interact':
            nointeract = True

    config = jhbuild.config.Config(configfile)
    if nointeract: config.interact = False

    if not args or args[0][0] == '-':
        command = 'build' # default to cvs update + compile
    else:
        command = args[0]
        args = args[1:]

    try:
        jhbuild.commands.run(command, config, args)
    except KeyboardInterrupt:
        print "Interrupted"
        sys.exit(1)
    except EOFError:
        print "EOF"
        sys.exit(1)
    except SystemExit:
        raise
    except Exception, exc:
        import traceback
        traceback.print_exc()
        sys.stderr.write('jhbuild %s: %s\n' % (command, exc))
        sys.stderr.write(usage + '\n')
        sys.exit(1)
