# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   base.py: the most common jhbuild commands
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
import getopt
import jhbuild.moduleset
import jhbuild.frontends

from jhbuild.errors import UsageError, FatalError

__all__ = [ 'register_command', 'run' ]

# handle registration of new commands
_commands = {}
def register_command(name, function):
    _commands[name] = function
def run(command, config, args):
    # if the command hasn't been registered, load a module by the same name
    if not _commands.has_key(command):
        try:
            __import__('jhbuild.commands.%s' % command)
        except ImportError:
            pass
    if not _commands.has_key(command):
        raise FatalError('command not found')

    func = _commands[command]
    return func(config, args)

# standard commands:
def do_update(config, args):
    opts, args = getopt.getopt(args, 's:t:D:', ['skip=', 'start-at='])

    startat = None
    for opt, arg in opts:
        if opt in ('-s', '--skip'):
            config.skip = config.skip + arg.split(',')
        elif opt in ('-t', '--start-at'):
            startat = arg
        elif opt == '-D':
            config.sticky_date = arg

    module_set = jhbuild.moduleset.load(config)
    module_list = module_set.get_module_list(args or config.modules,
                                             config.skip)

    # remove modules up to startat
    if startat:
        while module_list and module_list[0].name != startat:
            del module_list[0]

    # don't actually perform build ...
    config.nobuild = True
    config.nonetwork = False

    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('update', do_update)

def do_update_one(config, args):
    opts, args = getopt.getopt(args, 'D:', [])

    for opt, arg in opts:
        if opt == '-D':
            config.sticky_date = arg

    module_set = jhbuild.moduleset.load(config)
    try:
        module_list = [ module_set.modules[modname] for modname in args ]
    except KeyError:
        raise FatalError("A module called '%s' could not be found." % modname)
	
    # don't actually perform build ...
    config.nobuild = True
    config.nonetwork = False

    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('updateone', do_update_one)

def do_build(config, args):
    opts, args = getopt.getopt(args, 'acns:t:D:',
                               ['autogen', 'clean', 'no-network', 'skip=',
                                'start-at='])

    startat = None
    for opt, arg in opts:
        if opt in ('-a', '--autogen'):
            config.alwaysautogen = True
        elif opt in ('-c', '--clean'):
            config.makeclean = True
        elif opt in ('-n', '--no-network'):
            config.nonetwork = True
        elif opt in ('-s', '--skip'):
            config.skip = config.skip + arg.split(',')
        elif opt in ('-t', '--start-at'):
            startat = arg
        elif opt == '-D':
            config.sticky_date = arg
    module_set = jhbuild.moduleset.load(config)
    module_list = module_set.get_module_list(args or config.modules,
                                             config.skip)

    # remove modules up to startat
    if startat:
        while module_list and module_list[0].name != startat:
            del module_list[0]

    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('build', do_build)

def do_build_one(config, args):
    opts, args = getopt.getopt(args, 'acnD:',
                               ['autogen', 'clean', 'no-network'])

    for opt, arg in opts:
        if opt in ('-a', '--autogen'):
            config.alwaysautogen = True
        elif opt in ('-c', '--clean'):
            config.makeclean = True
        elif opt in ('-n', '--no-network'):
            config.nonetwork = True
        elif opt == '-D':
            config.sticky_date = arg

    module_set = jhbuild.moduleset.load(config)
    try:
        module_list = [ module_set.modules[modname] for modname in args ]
    except KeyError:
        raise FatalError("A module called '%s' could not be found." % modname)
	
    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('buildone', do_build_one)

def do_run(config, args):
    os.execlp(args[0], *args)
register_command('run', do_run)

def do_shell(config, args):
    user_shell = os.environ.get('SHELL', '/bin/sh')
    os.execlp(user_shell, user_shell)
register_command('shell', do_shell)

def do_list(config, args):
    opts, args = getopt.getopt(args, 'rs:', ['show-revision', 'skip='])
    show_rev = False
    for opt, arg in opts:
        if opt in ('-r', '--show-revision'):
            show_rev = True
        if opt in ('-s', '--skip'):
            config.skip = config.skip + arg.split(',')
    module_set = jhbuild.moduleset.load(config)
    module_list = module_set.get_module_list(args or config.modules,
                                             config.skip)

    for mod in module_list:
        if show_rev:
            rev = mod.get_revision()
            if rev:
                print '%s (%s)' % (mod.name, rev)
            else:
                print mod.name
        else:
            print mod.name
register_command('list', do_list)

def do_dot(config, args):
    module_set = jhbuild.moduleset.load(config)
    if args:
        modules = args
    elif config.modules == 'all':
        modules = None
    else:
        modules = config.modules
    module_set.write_dot(modules)
register_command('dot', do_dot)
