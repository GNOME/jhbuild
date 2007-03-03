# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
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
from optparse import make_option

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import UsageError, FatalError
from jhbuild.commands import Command, register_command


class cmd_update(Command):
    """Pull updates from the version control system for one or more modules,
    plus its dependencies."""

    name = 'update'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help='treat the given modules as up to date'),
            make_option('-t', '--start-at', metavar='MODULE',
                        action='store', dest='startat', default=None,
                        help='start building at the given module'),
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help='set a sticky date when checking out modules'),
            ])

    def run(self, config, options, args):
        for item in options.skip:
            config.skip += item.split(',')
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date

        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules,
                                                 config.skip)
        # remove modules up to startat
        if options.startat:
            while module_list and module_list[0].name != options.startat:
                del module_list[0]
            if not module_list:
                raise FatalError('%s not in module list' % options.startat)

        # don't actually perform build ...
        config.nobuild = True
        config.nonetwork = False

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_update)


class cmd_updateone(Command):
    """Pull updates from the version control system for one or more modules."""

    name = 'updateone'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help='set a sticky date when checking out modules'),
            ])

    def run(self, config, options, args):
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date

        module_set = jhbuild.moduleset.load(config)
        try:
            module_list = [module_set.modules[modname] for modname in args]
        except KeyError, e:
            raise FatalError("A module called '%s' could not be found."
                             % str(e))

        # don't actually perform build ...
        config.nobuild = True
        config.nonetwork = False

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_updateone)


class cmd_build(Command):
    """Pull updates from the version control system for one or more modules,
    plus its dependencies."""

    name = 'build'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='autogen', default=False,
                        help='always run autogen.sh'),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help='run make clean before make'),
            make_option('-d', '--dist',
                        action='store_true', dest='dist', default=False,
                        help='run make dist after building'),
            make_option('--distcheck',
                        action='store_true', dest='distcheck', default=False,
                        help='run make distcheck after building'),
            make_option('-n', '--no-network',
                        action='store_true', dest='nonetwork', default=False,
                        help='skip version control update'),
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help='treat the given modules as up to date'),
            make_option('-t', '--start-at', metavar='MODULE',
                        action='store', dest='startat', default=None,
                        help='start building at the given module'),
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help='set a sticky date when checking out modules'),
            ])

    def run(self, config, options, args):
        if options.autogen:
            config.alwaysautogen = True
        if options.clean:
            config.makeclean = True
        if options.dist:
            config.makedist = True
        if options.distcheck:
            config.makedistcheck = True
        if options.nonetwork:
            config.nonetwork = True
        for item in options.skip:
            config.skip += item.split(',')
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date

        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules,
                                                 config.skip)
        # remove modules up to startat
        if options.startat:
            while module_list and module_list[0].name != options.startat:
                del module_list[0]
            if not module_list:
                raise FatalError('%s not in module list' % options.startat)

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_build)


class cmd_buildone(Command):
    """Pull updates from the version control system for one or more modules."""

    name = 'buildone'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='autogen', default=False,
                        help='always run autogen.sh'),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help='run make clean before make'),
            make_option('-d', '--dist',
                        action='store_true', dest='dist', default=False,
                        help='run make dist after building'),
            make_option('--distcheck',
                        action='store_true', dest='distcheck', default=False,
                        help='run make distcheck after building'),
            make_option('-n', '--no-network',
                        action='store_true', dest='nonetwork', default=False,
                        help='skip version control update'),
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help='set a sticky date when checking out modules'),
            ])

    def run(self, config, options, args):
        if options.autogen:
            config.alwaysautogen = True
        if options.clean:
            config.makeclean = True
        if options.dist:
            config.makedist = True
        if options.distcheck:
            config.makedistcheck = True
        if options.nonetwork:
            config.nonetwork = True
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date

        module_set = jhbuild.moduleset.load(config)
        try:
            module_list = [module_set.modules[modname] for modname in args]
        except KeyError, e:
            raise FatalError("A module called '%s' could not be found."
                             % str(e))

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_buildone)


class cmd_run(Command):
    """Run a command under the jhbuild environment"""

    name = 'run'
    usage_args = 'program [ arguments ... ]'

    def execute(self, config, args):
        os.execlp(args[0], *args)

register_command(cmd_run)


class cmd_shell(Command):
    """Run a command under the jhbuild environment"""

    name = 'shell'
    usage_args = ''

    def execute(self, config, args):
        user_shell = os.environ.get('SHELL', '/bin/sh')
        os.execlp(user_shell, user_shell)

register_command(cmd_shell)


class cmd_list(Command):
    """List the modules that would be built."""

    name = 'list'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-r', '--show-revision',
                        action='store_true', dest='show_rev', default=False,
                        help='show which revision will be built'),
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help='treat the given modules as up to date'),
            ])

    def run(self, config, options, args):
        for item in options.skip:
            config.skip += item.split(',')
        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules,
                                                 config.skip)

        for mod in module_list:
            if options.show_rev:
                rev = mod.get_revision()
                if rev:
                    print '%s (%s)' % (mod.name, rev)
                else:
                    print mod.name
            else:
                print mod.name

register_command(cmd_list)


class cmd_dot(Command):
    """Output a Graphviz input file for the given modules"""

    name = 'dot'
    usage_args = '[ modules ... ]'

    def run(self, config, options, args):
        module_set = jhbuild.moduleset.load(config)
        if args:
            modules = args
        elif config.modules == 'all':
            modules = None
        else:
            modules = config.modules
        module_set.write_dot(modules)

register_command(cmd_dot)
