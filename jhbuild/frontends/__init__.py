# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   __init__.py: a package holding the various build frontends
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

import sys
import importlib

def get_buildscript(config, module_list=None, module_set=None):
    modname = 'jhbuild.frontends.%s' % config.buildscript
    importlib.import_module(modname)
    BuildScript = sys.modules[modname].BUILD_SCRIPT
    return BuildScript(config, module_list, module_set=module_set)
