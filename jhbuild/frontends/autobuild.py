# jhbuild - a tool to ease building collections of source packages
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

from jhbuild.utils import cmds, _
from jhbuild.errors import CommandError
from . import buildscript

import xmlrpclib
import zlib
from cStringIO import StringIO

from .tinderbox import get_distro
from .terminal import TerminalBuildScript, trayicon, t_bold, t_reset
import jhbuild.moduleset

def escape(string):
    return string.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def fix_encoding(string):
    charset = locale.getpreferredencoding()
    s = 'VERY BORKEN ENCODING'
    for encoding in [charset, 'utf-8', 'iso-8859-15']:
        try:
            s = str(string, encoding)
        except ValueError:
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
            err = None
            try:
                return xmlrpclib.ServerProxy.__request(self, methodname, params)
            except xmlrpclib.ProtocolError as e:
                err = e
                if e.errcode != 500:
                    raise
            except socket.error as e:
                err = e
                pass
            if i < ITERS-1:
                if self.verbose_timeout:
                    print(_('Server Error, retrying in %d seconds') % ((i+1)**2), file=sys.stderr)
                time.sleep((i+1)**2)
            else:
                if self.verbose_timeout:
                    print(_('Server Error, aborting'), file=sys.stderr)
                raise err
            

class AutobuildBuildScript(buildscript.BuildScript, TerminalBuildScript):
    xmlrpc_report_url = None
    verbose = False

    def __init__(self, config, module_list, module_set=None):
        buildscript.BuildScript.__init__(self, config, module_list, module_set=module_set)
        self.xmlrpc_report_url = config.autobuild_report_url
        self.verbose = config.verbose
        self.server = None
        self.modulefp = None
        self.phasefp = None
        self.modules = {}

        # cleanup environment
        os.environ['TERM'] = 'dumb'
        os.environ['LANG'] = 'C'
        for k in os.environ.keys():
            if k.startswith('LC_'):
                os.environ[k] = 'C'

        if self.verbose:
            self.trayicon = trayicon.TrayIcon(config)

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
        kws = {
            'close_fds': True
            }
        if isinstance(command, str):
            displayed_command = command
            kws['shell'] = True
        else:
            displayed_command = ' '.join(command)

        self.phasefp.write('<span class="command">%s</span>\n' % escape(displayed_command))
        if self.verbose:
            print(' $', displayed_command)

        kws['stdin'] = subprocess.PIPE
        kws['stdout'] = subprocess.PIPE
        kws['stderr'] = subprocess.PIPE
        if hint in ('cvs', 'svn', 'hg-update.py'):
            def format_line(line, error_output, fp=self.phasefp):
                if line[-1] == '\n':
                    line = line[:-1]
                if self.verbose:
                    print(line)
                if line.startswith('C '):
                    fp.write('<span class="conflict">%s</span>\n'
                             % escape(line))
                else:
                    fp.write('%s\n' % escape(line))
            kws['stderr'] = subprocess.STDOUT
        else:
            def format_line(line, error_output, fp=self.phasefp):
                if line[-1] == '\n':
                    line = line[:-1]
                if self.verbose:
                    if error_output:
                        print(line, file=sys.stderr)
                    else:
                        print(line)
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

        command = self._prepare_execute(command)

        try:
            p = subprocess.Popen(command, **kws)
        except OSError as e:
            self.phasefp.write('<span class="error">' + _('Error: %s') % escape(str(e)) + '</span>\n')
            raise CommandError(str(e))

        cmds.pprint_output(p, format_line)
        if p.returncode != 0:
            raise CommandError(_('Error running %s') % command, p.returncode)

    def start_build(self):
        self.server = ServerProxy(self.xmlrpc_report_url, allow_none = True)
        if self.verbose:
            self.server.verbose_timeout = True

        # close stdin
        sys.stdin.close()

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
        except xmlrpclib.ProtocolError as e:
            if e.errcode == 403:
                print(_('ERROR: Wrong credentials, please check username/password'), file=sys.stderr)
                sys.exit(1)
            raise

        
        if self.verbose:
            s = _('Starting Build #%s') % self.build_id
            print(s)
            print('=' * len(s))
            print('')


    def end_build(self, failures):
        self.server.end_build(self.build_id, failures)
        if self.verbose:
            TerminalBuildScript.end_build(self, failures)


    def start_module(self, module):
        if self.verbose:
            print('\n%s' % t_bold + _('**** Starting module %s ****' % module) + t_reset)
        self.server.start_module(self.build_id, module)
        self.current_module = module
        self.modulefp = StringIO()
        

    def end_module(self, module, failed):
        log = fix_encoding(self.modulefp.getvalue())
        self.modulefp = None
        self.server.end_module(self.build_id, module, compress_data(log), failed)

    def start_phase(self, module, phase):
        self.server.start_phase(self.build_id, module, phase)
        if self.verbose:
            TerminalBuildScript.start_phase(self, module, phase)
        self.phasefp = StringIO()


    def end_phase(self, module, phase, error):
        log = fix_encoding(self.phasefp.getvalue())
        self.phasefp = None

        if phase == 'test':
            if self.modules == {}:
                self.modules = jhbuild.moduleset.load_tests(self.config)

            if module in self.modules.modules.keys() \
                    and self.modules.modules[module].test_type == 'ldtp':
                self._upload_logfile(module)

        if isinstance(error, Exception):
            error = str(error)
        self.server.end_phase(self.build_id, module, phase, compress_data(log), error)

    def handle_error(self, module, phase, nextphase, error, altphases):
        '''handle error during build'''
        print('FIXME: handle error! (failed build: %s: %s)' % (module, error))
        return 'fail'

    def _upload_ldtp_logfile (self, module):
        test_module = self.modules.modules[module]
        src_dir = test_module.get_srcdir()
        if not os.path.exists (os.path.join(src_dir,'run.xml')):
            return
        logfile = test_module.get_ldtp_log_file (os.path.join(src_dir,'run.xml'))
        if not os.path.exists (logfile):
            return
        self._upload_logfile (module, logfile, 'application/x-ldtp+xml')

    def _upload_logfile (self, module, logfile, mimetype):
        log = open (logfile, 'r')
        basename = os.path.basename (logfile)
        self.server.attach_file (self.build_id, module, 'test', basename,
                                 compress_data(log.read()), mimetype)
        log.close()

BUILD_SCRIPT = AutobuildBuildScript
