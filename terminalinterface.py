# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2002 Seth Nickell
#
#   terminal-interface.py: terminal frontend for jhbuild
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

_isxterm = os.environ.get('TERM','') == 'xterm'
_boldcode = os.popen('tput bold', 'r').read()
_normal = os.popen('tput rmso', 'r').read()
user_shell = os.environ.get('SHELL', '/bin/sh')

class Interface:

    def setModuleList(self, list):
        self.module_list = list

    def runEventLoop(self):
        return

    def pauseBuild(self):
        return False

    def message(self, msg, modulenum):
        if modulenum > 0:
            percent = ' [%d/%d]' % (modulenum, len(self.module_list))
        else:
            percent = ''
        print '%s*** %s ***%s%s' % (_boldcode, msg, percent, _normal)
        if _isxterm:
            print '\033]0;jhbuild: %s%s\007' % (msg, percent)        


    def setAction(self, action, module, module_num):
        self.message('%s %s' % (action, module.name), module_num)



    def printToBuildOutput(self, output):
        print output,

    def printToWarningOutput(self, output):
        print output,

    def print_unbuilt_modules(self, unbuilt_modules):
        for module in unbuilt_modules:
            print module
        print

    ERR_RERUN = 0
    ERR_CONT = 1
    ERR_GIVEUP = 2
    ERR_CONFIGURE = 3
    def handle_error(self, module, stage, checkoutdir, modulenum, nummodules):
        '''Ask the user what to do about an error.

        Returns one of ERR_RERUN, ERR_CONT or ERR_GIVEUP.''' #"

        self.message('error during %s for module %s' % (stage, module.name),
                     modulenum)
        while 1:
            print
            print '  [1] rerun %s' % stage
            print '  [2] force checkout/autogen'
            print '  [3] start shell'
            print '  [4] give up on module'
            print '  [5] continue (ignore error)'
            val = raw_input('choice: ')
            if val == '1':
                return self.ERR_RERUN
            elif val == '2':
                return self.ERR_CONFIGURE
            elif val == '3':
                os.chdir(checkoutdir)
                print 'exit shell to continue with build'
                os.system(user_shell)
            elif val == '4':
                return self.ERR_GIVEUP
            elif val == '5':
                return self.ERR_CONT
            else:
                print 'invalid option'
        
