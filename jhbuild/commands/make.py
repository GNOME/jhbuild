# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2011 Colin Walters <walters@verbum.org>
#
#   make.py: Run build for cwd
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

import logging
import os
import shlex
from optparse import make_option

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.commands import Command, register_command
from jhbuild.utils import N_, _

class cmd_make(Command):
    doc = N_('Compile and install the module for the current directory')

    name = 'make'
    usage_args = N_('[ options ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='autogen', default=False,
                        help=_('always run autogen.sh')),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help=_('run make clean before make')),
            make_option('--check',
                        action='store_true', dest='check', default=False,
                        help=_('run make check after building')),
            make_option('-q', '--quiet',
                        action='store_true', dest='quiet', default=False,
                        help=_('quiet (no output)')),
            ])

    def run(self, config, options, args, help=None):
        # Grab the cwd before anything changes it
        cwd = os.path.realpath(self.get_cwd())
        checkoutroot = os.path.realpath(config.checkoutroot)

        # Explicitly don't touch the network for this
        options.nonetwork = True
        options.force_policy = True
        config.set_from_cmdline_options(options)

        makeargs = config.makeargs
        for arg in args:
            # if uninstalling, skip install.
            if arg == 'uninstall' or arg.startswith('uninstall-'):
                config.noinstall = True
            # pipes.quote (and really, trying to safely quote shell arguments) is
            # broken, but executing commands as strings is pervasive throughout
            # jhbuild...this is a hack that will probably live until someone just
            # replaces jhbuild entirely.
            makeargs = '%s %s' % (makeargs, shlex.quote(arg))
        config.makeargs = makeargs

        module_set = jhbuild.moduleset.load(config)

        if not cwd.startswith(checkoutroot):
            logging.error(_('The current directory is not in the checkout root %r') % (checkoutroot, ))
            return False

        cwd = cwd[len(checkoutroot):]
        cwd = cwd.lstrip(os.sep)
        modname, _slash, _rest = cwd.partition(os.sep)

        try:
            module = module_set.get_module(modname, ignore_case=True)
        except KeyError:
            default_repo = jhbuild.moduleset.get_default_repo()
            if not default_repo:
                logging.error(_('No module matching current directory %r in the moduleset') % (modname, ))
                return False

            # Try distutils, then meson, then autotools (if autogen.sh exists), then
            # cmake and fallback to autotools
            if os.path.exists(os.path.join(self.get_cwd(), 'setup.py')):
                from jhbuild.modtypes.distutils import DistutilsModule
                module = DistutilsModule(modname, default_repo.branch(modname))
                module.python = os.environ.get('PYTHON3', 'python3')
            elif os.path.exists(os.path.join(self.get_cwd(), 'meson.build')):
                from jhbuild.modtypes.meson import MesonModule
                module = MesonModule(modname, default_repo.branch(modname))
            elif os.path.exists(os.path.join(self.get_cwd(), 'autogen.sh')):
                from jhbuild.modtypes.autotools import AutogenModule
                module = AutogenModule(modname, default_repo.branch(modname))
            elif os.path.exists(os.path.join(self.get_cwd(), 'CMakeLists.txt')):
                from jhbuild.modtypes.cmake import CMakeModule
                module = CMakeModule(modname, default_repo.branch(modname))
            else:
                from jhbuild.modtypes.autotools import AutogenModule
                module = AutogenModule(modname, default_repo.branch(modname))

            module.config = config
            logging.info(_('module "%(modname)s" does not exist, created automatically using repository "%(reponame)s"') % \
                         {'modname': modname, 'reponame': default_repo.name})

        build = jhbuild.frontends.get_buildscript(config, [module], module_set=module_set)
        return build.build()

register_command(cmd_make)

