# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2003  James Henstridge
# Copyright (C) 2003  Seth Nickell
#
#   terminal_buildscript.py: build logic for a terminal interface
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
import buildscript

term = os.environ.get('TERM', '')
_isxterm = term.find('xterm') >= 0 or term == 'rxvt'
del term
_boldcode = os.popen('tput bold', 'r').read()
_normal = os.popen('tput sgr0', 'r').read()
user_shell = os.environ.get('SHELL', '/bin/sh')

class TerminalBuildScript(buildscript.BuildScript):

    def __init__(self, configdict, module_list):
        buildscript.BuildScript.__init__(self, configdict, module_list, derived_class=1)

    def message(self, msg, module_num = -1):
        '''shows a message to the screen'''
        
        if (module_num == -1):
            module_num = self.module_num
            
        if module_num > 0:
            percent = ' [%d/%d]' % (module_num, len(self.modulelist))
        else:
            percent = ''
        print '%s*** %s ***%s%s' % (_boldcode, msg, percent, _normal)
        if _isxterm:
            print '\033]0;jhbuild: %s%s\007' % (msg, percent)

    def setAction(self, action, module, module_num=-1, action_target=None):
        if (module_num == -1):
            module_num = self.module_num
        if (action_target == None):
            action_target = module.name
        self.message('%s %s' % (action, action_target), module_num)        

    def execute(self, command):
        '''executes a command, and returns the error code'''
        print command
        ret = os.system(command)
        return ret

    def build(self,interact):
        poison = [] # list of modules that couldn't be built

        self.module_num = 0
        for module in self.modulelist:
            self.module_num = self.module_num + 1
            poisoned = 0
            for dep in module.dependencies:
                if dep in poison:
                    self.message('module %s not built due to non buildable %s'
                                 % (module.name, dep))
                    poisoned = True
            if poisoned:
                poison.append(module.name)
                continue

            state = module.STATE_START
            while state != module.STATE_DONE:
                nextstate, error, altstates = module.run_state(self, state)

                if error:
                    newstate = self.handle_error(module, state,
                                                 nextstate, error,
                                                 altstates, interact)
                    if newstate == 'poison':
                        poison.append(module.name)
                        state = module.STATE_DONE
                    else:
                        state = newstate
                else:
                    state = nextstate
        if len(poison) == 0:
            self.message('success')
        else:
            self.message('the following modules were not built')
            for module in poison:
                print module,
            print

    def handle_error(self, module, state, nextstate, error, altstates, interact=1):
        '''handle error during build'''
        self.message('error during stage %s of %s: %s' % (state, module.name,
                                                          error))

        if interact == 0:
            return 'poison'
        while True:
            print
            print '  [1] rerun stage %s' % state
            print '  [2] ignore error and continue to %s' % nextstate
            print '  [3] give up on module'
            print '  [4] start shell'
            i = 5
            for altstate in altstates:
                print '  [%d] go to stage %s' % (i, altstate)
                i = i + 1
            val = raw_input('choice: ')
            val = val.strip()
            if val == '1':
                return state
            elif val == '2':
                return nextstate
            elif val == '3':
                return 'poison'
            elif val == '4':
                os.chdir(module.get_builddir(self))
                print 'exit shell to continue with build'
                os.system(user_shell)
            else:
                try:
                    val = int(val)
                    return altstates[val - 5]
                except:
                    print 'invalid choice'


