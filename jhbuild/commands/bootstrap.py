# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   bootstrap.py: code to check whether prerequisite modules are installed
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
import sys
import urllib
from optparse import make_option
import logging

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.commands import Command, register_command
import jhbuild.commands.base
from jhbuild.commands.base import cmd_build
from jhbuild.utils.cmds import check_version

class cmd_bootstrap(cmd_build):
    doc = _('Build required support tools')

    name = 'bootstrap'

    def __init__(self):
        cmd_build.__init__(self)
        self.options.append(
            make_option('--ignore-system',
                        action='store_true', dest='ignore_system', default=False,
                        help=_('do not use system installed modules')))

    def run(self, config, options, args):
        config.moduleset = 'bootstrap'
        # load the bootstrap module set
        if not args:
            args = ['meta-bootstrap']

        for item in options.skip:
            config.skip += item.split(',')
        options.skip = []

        ignored_modules = []
        if not options.ignore_system:
            # restore system PATH to check for system-installed programs
            path = os.environ.get('PATH')
            os.environ['PATH'] = path.replace(
                    os.path.join(config.prefix, 'bin'), '')

            module_set = jhbuild.moduleset.load(config)
            modules = args or config.modules
            module_list = module_set.get_module_list(modules)

            for module in module_list:
                if module.type == 'meta':
                    continue
                for version_regex in (r'.*?[ \(]([\d.]+)', r'^([\d.]+)'):
                    if check_version([module.name, '--version'],
                            version_regex, module.branch.version):
                        ignored_modules.append(module.name)
                        break

            os.environ['PATH'] = path
            config.skip.extend(ignored_modules)

        # cancel the bootstrap updateness check as it has no sense (it *is*
        # running bootstrap right now)
        jhbuild.commands.base.check_bootstrap_updateness = lambda x: x
        rc = cmd_build.run(self, config, options, args)

        if ignored_modules:
            logging.info(
                    _('some modules (%s) were automatically ignored as a '
                      'sufficient enough version was found installed on '
                      'your system. Use --ignore-system if you want to build '
                      'them nevertheless.' % ', '.join(ignored_modules)))

        return rc

register_command(cmd_bootstrap)
