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

import logging
from optparse import make_option

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import UsageError, FatalError
from jhbuild.commands import Command, register_command


class cmd_uninstall(Command):
    doc = _('Uninstall all modules')

    name = 'uninstall'
    usage_args = N_('[ modules ... ]')

    def run(self, config, options, args, help=None):
        config.set_from_cmdline_options(options)

        module_set = jhbuild.moduleset.load(config)
        try:
            module_list = [module_set.get_module(modname, ignore_case = True) \
                           for modname in args]
        except KeyError:
            raise FatalError(_('unknown module %s') % modname)

        if not module_list:
            self.parser.error(_('This command requires a module parameter.'))

        # remove modules that are not marked as installed
        packagedb = module_set.packagedb
        for module in module_list[:]:
            if not packagedb.check(module.name):
                logging.warn(_('Module %(mod)r is not installed') % {'mod': module.name })
                module_list.remove(module)
            else:
                packagedb.uninstall(module.name)


register_command(cmd_uninstall)
