# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2003  James Henstridge
# Copyright (C) 2003  Seth Nickell
#
#   buildscript.py: base class of the various interface types
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
import string

class _Struct:
    pass

class BuildScript:
    def __init__(self, configdict, module_list, derived_class = 0):
        if (derived_class == 0):
            raise Exception()
        
        self.modulelist = module_list
        self.module_num = 0

        self.config = _Struct
        self.config.autogenargs = configdict.get('autogenargs',
                                                 '--disable-static ' +
                                                 '--disable-gtk-doc')
        self.config.makeargs = configdict.get('makeargs', '')
        self.config.prefix = configdict.get('prefix', '/opt/gtk2')
        self.config.nobuild = configdict.get('nobuild', False)
        self.config.nonetwork = configdict.get('nonetwork', False)
        self.config.alwaysautogen = configdict.get('alwaysautogen', False)
        self.config.makeclean = configdict.get('makeclean', True)

        self.config.checkoutroot = configdict.get('checkoutroot')
        if not self.config.checkoutroot:
            self.config.checkoutroot = os.path.join(os.environ['HOME'],
                                                    'cvs','gnome')
        assert os.access(self.config.checkoutroot, os.R_OK|os.W_OK|os.X_OK), \
               'checkout root must be writable'
        assert os.access(self.config.prefix, os.R_OK|os.W_OK|os.X_OK), \
               'install prefix must be writable'

    def message(self, msg, module_num):
        '''shows a message to the screen'''
        raise Exception()

    def setAction(self, action, module, module_num=-1, action_target=None):
        '''inform the buildscript of a new stage of the build'''
        raise Exception()

    def execute(self, command):
        '''executes a command, and returns the error code'''
        raise Exception()

    def build(self, interact=1):
        '''start the build of the current configuration'''
        raise Exception()

    def handle_error(self, module, state, nextstate, error, altstates):
        '''handle error during build'''
        raise Exception()
