# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
# Copyright (C) 2003-2004  Seth Nickell
#
#   terminal.py: build logic for a terminal interface
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
import buildscript

term = os.environ.get('TERM', '')
_isxterm = term.find('xterm') >= 0 or term == 'rxvt'
del term
_boldcode = os.popen('tput bold', 'r').read()
_normal = os.popen('tput sgr0', 'r').read()
user_shell = os.environ.get('SHELL', '/bin/sh')

class TerminalBuildScript(buildscript.BuildScript):
    def message(self, msg, module_num=-1):
        '''Display a message to the user'''
        
        if module_num == -1:
            module_num = self.module_num
        if module_num > 0:
            progress = ' [%d/%d]' % (module_num, len(self.modulelist))
        else:
            progress = ''
        print '%s*** %s ***%s%s' % (_boldcode, msg, progress, _normal)
        if _isxterm:
            print '\033]0;jhbuild: %s%s\007' % (msg, progress)

    def set_action(self, action, module, module_num=-1, action_target=None):
        if module_num == -1:
            module_num = self.module_num
        if not action_target:
            action_target = module.name
        self.message('%s %s' % (action, action_target), module_num)        

    def execute(self, command, hint=None):
        '''executes a command, and returns the error code'''
        print command
        ret = os.system(command)
        return ret

    def end_build(self, failures):
        if len(failures) == 0:
            self.message('success')
        else:
            self.message('the following modules were not built')
            for module in failures:
                print module,
            print

    def handle_error(self, module, state, nextstate, error, altstates):
        '''handle error during build'''
        self.message('error during stage %s of %s: %s' % (state, module.name,
                                                          error))

        if not self.config.interact:
            return 'fail'
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
                return 'fail'
            elif val == '4':
                try:
                    os.chdir(module.get_builddir(self))
                except OSError:
                    os.chdir(self.config.checkoutroot)
                print 'exit shell to continue with build'
                os.system(user_shell)
            else:
                try:
                    val = int(val)
                    return altstates[val - 5]
                except:
                    print 'invalid choice'
        assert False, 'not reached'

BUILD_SCRIPT = TerminalBuildScript
