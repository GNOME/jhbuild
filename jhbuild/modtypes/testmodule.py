# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   testmodule.py: testmodule type definitions.
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

__metaclass__ = type

import os, time, signal, subprocess, random, tempfile
import hashlib

from jhbuild.errors import CommandError, BuildStateError
from jhbuild.modtypes import \
     Package, DownloadableModule, register_module_type

import xml.dom.minidom

__all__ = ['TestModule']
__test_types__ = ['ldtp' , 'dogtail']

class TestModule(Package, DownloadableModule):
    type = 'test'
    
    PHASE_CHECKOUT = DownloadableModule.PHASE_CHECKOUT
    PHASE_FORCE_CHECKOUT = DownloadableModule.PHASE_FORCE_CHECKOUT
    PHASE_TEST           = 'test'
    
    def __init__(self, name, branch=None, test_type=None, tested_pkgs=[]):
        Package.__init__(self, name, branch=branch)
        self.test_type    = test_type
        self.tested_pkgs  = tested_pkgs

        # modify environ for tests to be working
        if 'LDTP_DEBUG' in os.environ:
            del os.environ['LDTP_DEBUG'] # get rid of verbose LDTP output
        if 'GNOME_ACCESSIBILITY' not in os.environ or os.environ['GNOME_ACCESSIBILITY'] != 1:
            os.environ['GNOME_ACCESSIBILITY'] = '1'

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def _get_display(self):
        # get free display
        servernum = 99
        while True:
            if not os.path.exists('/tmp/.X%s-lock' % servernum):
                break
            servernum += 1
        return str(servernum)

    def _set_xauth(self, servernum):
        # create auth file
        paths = os.environ.get('PATH').split(':')
        flag = False
        for path in paths:
            if os.path.exists(os.path.join(path, 'xauth')):
                flag = True
                break
        tmpdir = tempfile.gettempdir()
        if not flag or os.path.exists(os.path.join(tmpdir,'jhbuild.%s' % os.getpid())):
            return ''

        try:
            os.mkdir(os.path.join(tmpdir,'jhbuild.%s' % os.getpid()))
            new_xauth = os.path.join(tmpdir, 'jhbuild.%s' % os.getpid(),'Xauthority')
            open(new_xauth, 'w').close()
            hexdigest = hashlib.md5(str(random.random())).hexdigest()
            os.system('xauth -f "%s" add ":%s" "." "%s"' % (
                        new_xauth, servernum, hexdigest))
        except OSError:
            return ''
        return new_xauth
    
    def do_test(self, buildscript):
        buildscript.set_action('Testing', self)
        if not buildscript.config.noxvfb:
            # start Xvfb
            old_display = os.environ.get('DISPLAY')
            old_xauth   = os.environ.get('XAUTHORITY')
            xvfb_pid = self._start_xvfb(buildscript.config.xvfbargs)
            if xvfb_pid == -1:
                raise BuildStateError('Unable to start Xvfb')

        # either do_ldtp_test or do_dogtail_test
        method = getattr(self, 'do_' + self.test_type + '_test')
        try:
            method(buildscript)
        finally:
            if not buildscript.config.noxvfb:
                # kill Xvfb if it has been started
                self._stop_xvfb(xvfb_pid)
                if old_display:
                    os.environ['DISPLAY'] = old_display
                else:
                    os.unsetenv('DISPLAY')
                if old_xauth:
                    os.environ['XAUTHORITY'] = old_xauth
                else:
                    os.unsetenv('XAUTHORITY')
    do_test.depends = [PHASE_CHECKOUT]

    def get_ldtp_log_file(self, filename):
        # <ldtp>
        # |
        # -- <logfile>filename</logfile>
        run_file = xml.dom.minidom.parse(filename)
        try:
            return run_file.getElementsByTagName('ldtp')[0].getElementsByTagName(
                    'logfile')[0].childNodes[0].data
        except IndexError:
            return None

    def _get_ldtp_info(self, node):
        infos = []
        errors = []
        warnings = []
        causes = []
        for info in node.getElementsByTagName('info'):
            for child in info.childNodes:
                infos.append(child.data)
        for cause in node.getElementsByTagName('cause'):
            for child in cause.childNodes:
                causes.append(child.data)
        for error in node.getElementsByTagName('error'):
            for child in error.childNodes:
                errors.append(child.data)
        for warning in node.getElementsByTagName('warning'):
            for child in warning.childNodes:
                warnings.append(child.data)
        return infos, errors, causes, warnings
        
    def _check_ldtp_log_file(self, logfile):
        log_file = xml.dom.minidom.parse(logfile)
        ldtp_node = log_file.getElementsByTagName('ldtp')[0]

        groups = []
        for group in ldtp_node.getElementsByTagName('group'):
            scr = []
            for script in group.getElementsByTagName('script'):
                tests = {}
                for test in script.getElementsByTagName('test'):
                    test_name = test.getAttribute('name')
                    
                    pass_status = test.getElementsByTagName('pass')[0].childNodes[0].data
                    infos, errors, causes, warnings = self._get_ldtp_info(test)
                    tests[test_name] = {
                        'pass': pass_status,
                        'info': infos,
                        'error': errors,
                        'cause': causes,
                        'warning': warnings
                    }

                infos, errors, causes, warnings = self._get_ldtp_info(script)
                scr.append({
                        'tests': tests,
                        'info': infos,
                        'error': errors,
                        'cause': causes,
                        'warning': warnings})

            groupstatus = group.getElementsByTagName('groupstatus')[0].childNodes[0].data
            groups.append({'script': scr, 'groupstatus': groupstatus})
        return groups

    def check_groups(self, groups):
        group_num = 1
        flag = False
        status = ''
        for group in groups:
            status += 'In Group #%s (%s)\n' % (group_num, group['groupstatus'])
            for script in group['script']:
                for test in script['tests'].keys():
                    status += 'Test \'%s\' ' % test
                    if script['tests'][test]['pass'] == '0': # failed
                        status += 'failed\n\tErrors'
                        for error in script['tests'][test]['error']:
                            status += ', '
                            status += error

                        status += '\n\tCauses'
                        for cause in script['tests'][test]['cause']:
                            status += ', '
                            status += cause

                        status += '\n\tWarnings'
                        for warning in script['tests'][test]['warning']:
                            status += ', '
                            status += warning

                        status += '\n\tInfos'
                        for info in script['tests'][test]['info']:
                            status += ', '
                            status += info                        
                    else:
                        status += 'passed'
                    status += '\n'

            group_num += 1
            if self._check_ldtp_group_status(group['groupstatus']):
                flag = True
        return flag, status
    
    def _check_ldtp_group_status(self, status):
        status = status.split()
        if status[0] != status[-1]:
            return True
        return False

    def _start_xvfb(self, xvfbargs):
        new_display = self._get_display()
        new_xauth   = self._set_xauth(new_display)
        if new_xauth == '':
            return -1

        os.environ['DISPLAY'] = ':' + new_display
        os.environ['XAUTHORITY'] = new_xauth
        try:
            xvfb = subprocess.Popen(
                    ['Xvfb',':'+new_display] + xvfbargs.split(), shell=False)
            self.screennum = new_display
            self.xauth = new_xauth
        except OSError:
            return -1
        
        time.sleep(2) # allow Xvfb to start
        if xvfb.poll() is not None:
            return -1
        return xvfb.pid

    def _stop_xvfb(self, xvfb_pid):
        os.kill(xvfb_pid, signal.SIGINT)
        os.system('xauth remove ":%s"' % self.screennum)
        os.system('rm -r %s' % os.path.split(self.xauth)[0])
            
    def _start_ldtp(self):
        try:
            ldtp = subprocess.Popen('ldtp', shell=False)
        except OSError:
            return -1
        time.sleep(1)
        if ldtp.poll() is not None:
            return -1
        return ldtp.pid
    
    def do_ldtp_test(self, buildscript):
        src_dir = self.get_srcdir(buildscript)
        old_debug = os.getenv('LDTP_DEBUG')
        if old_debug is not None:
            del os.environ['LDTP_DEBUG']

        ldtp_pid = self._start_ldtp()
        if ldtp_pid == -1:
            raise BuildStateError('Unable to start ldtp server')

        try:
            if buildscript.config.noxvfb:
                buildscript.execute('ldtprunner run.xml', cwd=src_dir)
            else:
                buildscript.execute('ldtprunner run.xml', cwd=src_dir,
                        extra_env={'DISPLAY': ':%s' % self.screennum})
        except CommandError as e:
            os.kill(ldtp_pid, signal.SIGINT)
            if e.returncode == 32512:        # ldtprunner not installed
                raise BuildStateError('ldtprunner not available')
            raise BuildStateError('error %s during test' % e.returncode)
        os.kill(ldtp_pid, signal.SIGINT)
        
        if old_debug is not None:
            os.environ['LDTP_DEBUG'] = old_debug
        
        log_file = self.get_ldtp_log_file(os.path.join (src_dir,'run.xml'))
        if not log_file:
            raise BuildStateError('missing log file')
        try:
            groups = self._check_ldtp_log_file(log_file)
            flag, status = self.check_groups(groups)
            if flag:
                raise BuildStateError(status)
        except Exception:
            raise BuildStateError('malformed log file')

    def do_dogtail_test(self, buildscript):
        src_dir = self.get_srcdir(buildscript)
        test_cases = []
        all_files = os.listdir(src_dir)
        for file in all_files:
            if file[-3:] == '.py':
                test_cases.append(file)

        if buildscript.config.noxvfb:
            extra_env = {}
        else:
            extra_env = {'DISPLAY': ':%s' % self.screennum}

        for test_case in test_cases:
            try:
                buildscript.execute('python %s' % test_case,
                        cwd=src_dir, extra_env=extra_env)
            except CommandError as e:
                if e.returncode != 0:
                    raise BuildStateError('%s failed' % test_case)

    def xml_tag_and_attrs(self):
        return 'testmodule', [('id', 'name', None),
                              ('type', 'test_type', None)]

def get_tested_packages(node):
    tested_pkgs = []
    for tested_module in node.getElementsByTagName('testedmodules'):
        for mod in tested_module.getElementsByTagName('tested'):
            tested_pkgs.append(mod.getAttribute('package'))
    return tested_pkgs

def parse_testmodule(node, config, uri, repositories, default_repo):
    instance = TestModule.parse_from_xml(node, config, uri, repositories, default_repo)

    test_type = node.getAttribute('type')
    if test_type not in __test_types__:
        # FIXME: create an error here
        pass
    instance.test_type = test_type

    instance.tested_pkgs = get_tested_packages(node)
    
    return instance
                                   
register_module_type('testmodule', parse_testmodule)
