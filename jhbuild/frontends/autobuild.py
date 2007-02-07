# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   autobuild.py: build logic for a non-interactive reporting build
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
import time
import subprocess
import sys
import locale
import socket

from jhbuild.utils import cmds
from jhbuild.errors import CommandError
import buildscript

import xmlrpclib
import zlib
from cStringIO import StringIO

from tinderbox import get_distro
from terminal import TerminalBuildScript, trayicon, t_bold, t_reset

def escape(string):
    return string.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def fix_encoding(string):
    charset = locale.getpreferredencoding()
    s = 'VERY BORKEN ENCODING'
    for encoding in [charset, 'utf-8', 'iso-8859-15']:
        try:
            s = unicode(string, encoding)
        except:
            continue
        break
    return s.encode('us-ascii', 'xmlcharrefreplace')

def compress_data(data):
    c_data = zlib.compress(data)
    return xmlrpclib.Binary(c_data)

class ServerProxy(xmlrpclib.ServerProxy):
    verbose_timeout = False

    def __request(self, methodname, params):
        ITERS = 10
        for i in range(ITERS):
            try:
                return xmlrpclib.ServerProxy.__request(self, methodname, params)
            except xmlrpclib.ProtocolError, e:
                if e.errcode != 500:
                    raise
            except socket.error, e:
                pass
            if i < ITERS-1:
                if self.verbose_timeout:
                    print >> sys.stderr, 'Server Error, retrying in %d seconds' % ((i+1)**2)
                time.sleep((i+1)**2)
            else:
                if self.verbose_timeout:
                    print >> sys.stderr, 'Server Error, aborting'
                raise e
            

class AutobuildBuildScript(buildscript.BuildScript, TerminalBuildScript):
    xmlrpc_report_url = None
    verbose = False

    def __init__(self, config, module_list):
        buildscript.BuildScript.__init__(self, config, module_list)
        self.xmlrpc_report_url = config.autobuild_report_url
        self.verbose = config.verbose
        self.server = None
        self.modulefp = None
        self.phasefp = None

        # cleanup environment
        os.environ['TERM'] = 'dumb'
        os.environ['LANG'] = 'C'
        for k in os.environ.keys():
            if k.startswith('LC_'):
                os.environ[k] = 'C'

        if self.verbose:
            self.trayicon = trayicon.TrayIcon()

    def message(self, msg, module_num=-1, skipfp = False):
        '''Display a message to the user'''
        if not skipfp:
            if self.phasefp:
                fp = self.phasefp
            elif self.modulefp:
                fp = self.modulefp
            else:
                fp = None

            if fp:
                fp.write(msg + '\n')

        if self.verbose:
            TerminalBuildScript.message(self, msg, module_num)

    def set_action(self, action, module, module_num=-1, action_target=None):
        if module_num == -1:
            module_num = self.module_num
        if not action_target:
            action_target = module.name
        self.message('%s %s' % (action, action_target), module_num, skipfp = True)

    def execute(self, command, hint=None, cwd=None, extra_env=None):
        '''executes a command, and returns the error code'''
        kws = {
            'close_fds': True
            }
        if isinstance(command, (str, unicode)):
            displayed_command = command
            kws['shell'] = True
        else:
            displayed_command = ' '.join(command)

        self.phasefp.write('<span class="command">%s</span>\n' % escape(displayed_command))
        if self.verbose:
            print ' $', displayed_command

        kws['stdin'] = subprocess.PIPE
        kws['stdout'] = subprocess.PIPE
        kws['stderr'] = subprocess.PIPE
        if hint in ('cvs', 'svn'):
            def format_line(line, error_output, fp=self.phasefp):
                if line[-1] == '\n': line = line[:-1]
                if self.verbose:
                    print line
                if line.startswith('C '):
                    fp.write('<span class="conflict">%s</span>\n'
                                        % escape(line))
                else:
                    fp.write('%s\n' % escape(line))
            kws['stderr'] = subprocess.STDOUT
        else:
            def format_line(line, error_output, fp=self.phasefp):
                if line[-1] == '\n': line = line[:-1]
                if self.verbose:
                    if error_output:
                        print >> sys.stderr, line
                    else:
                        print line
                if error_output:
                    fp.write('<span class="error">%s</span>\n'
                                        % escape(line))
                else:
                    fp.write('%s\n' % escape(line))

        if cwd is not None:
            kws['cwd'] = cwd

        if extra_env is not None:
            kws['env'] = os.environ.copy()
            kws['env'].update(extra_env)

        try:
            p = subprocess.Popen(command, **kws)
        except OSError, e:
            self.phasefp.write('<span class="error">Error: %s</span>\n' % escape(str(e)))
            raise CommandError(str(e))

        cmds.pprint_output(p, format_line)
        if p.returncode != 0:
            raise CommandError('Error running %s' % command, p.returncode)

    def start_build(self):
        self.server = ServerProxy(self.xmlrpc_report_url, allow_none = True)
        if self.verbose:
            self.server.verbose_timeout = True

        # close stdin
        os.close(0)

        info = {}
        import socket
        un = os.uname()

        info['build_host'] = socket.gethostname()
        info['architecture'] = (un[0], un[2], un[4])

        distro = get_distro()
        if distro:
            info['distribution'] = distro

        info['module_set'] = self.config.moduleset

        try:
            self.build_id = self.server.start_build(info)
        except xmlrpclib.ProtocolError, e:
            if e.errcode == 403:
                print >> sys.stderr, 'ERROR: Wrong credentials, please check username/password'
                sys.exit(1)
            raise

        
        if self.verbose:
            s = 'Starting Build #%s' % self.build_id
            print s
            print '=' * len(s)
            print ''


    def end_build(self, failures):
        self.server.end_build(self.build_id, failures)
        if self.verbose:
            TerminalBuildScript.end_build(self, failures)


    def start_module(self, module):
        if self.verbose:
            print '\n%s**** Starting module %s ****%s' % (t_bold, module, t_reset)
        self.server.start_module(self.build_id, module)
        self.current_module = module
        self.modulefp = StringIO()
        

    def end_module(self, module, failed):
        log = fix_encoding(self.modulefp.getvalue())
        self.modulefp = None
        self.server.end_module(self.build_id, module, compress_data(log), failed)

    def start_phase(self, module, state):
        self.server.start_phase(self.build_id, module, state)
        if self.verbose:
            TerminalBuildScript.start_phase(self, module, state)
        self.phasefp = StringIO()


    def end_phase(self, module, state, error):
        log = fix_encoding(self.phasefp.getvalue())
        self.phasefp = None
        self.server.end_phase(self.build_id, module, state, compress_data(log), error)

    def handle_error(self, module, state, nextstate, error, altstates):
        '''handle error during build'''
        print 'handle error!'
        return 'fail'


BUILD_SCRIPT = AutobuildBuildScript
