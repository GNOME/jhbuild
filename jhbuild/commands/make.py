# jhbuild - a build script for GNOME 1.x and 2.x
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
import pipes
import sys
import time
from optparse import make_option

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import FatalError
from jhbuild.commands import Command, register_command

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
        cwd = os.getcwd()

        # Explicitly don't touch the network for this
        options.nonetwork = True
        options.force_policy = True
        config._internal_noautogen = not options.autogen
        config.set_from_cmdline_options(options)

        makeargs = config.makeargs
        for arg in args:
            # pipes.quote (and really, trying to safely quote shell arguments) is
            # broken, but executing commands as strings is pervasive throughout
            # jhbuild...this is a hack that will probably live until someone just
            # replaces jhbuild entirely.
            makeargs = '%s %s' % (makeargs, pipes.quote(arg))
        config.makeargs = makeargs

        module_set = jhbuild.moduleset.load(config)

        if not cwd.startswith(config.checkoutroot):
            logging.error(_('The current directory is not in the checkout root %r') % (config.checkoutroot, ))
            return False

        cwd = cwd[len(config.checkoutroot):]
        cwd = cwd.lstrip(os.sep)
        name, _slash, _rest = cwd.partition(os.sep)

        try:
            module = module_set.get_module(name, ignore_case=True)
        except KeyError, e:
            logging.error(_('No module matching current directory %r in the moduleset') % (name, ))
            return False

        build = jhbuild.frontends.get_buildscript(config, [module], module_set=module_set)
        return build.build()

register_command(cmd_make)

