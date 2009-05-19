# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2009  Codethink Ltd.
#
#   ldtp.py: Helper methods for running LDTP/gnome-desktop-testing tests
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
#
#  Authors:
#    John Carr <john.carr@unrouted.co.uk>

# The LDTP and Dogtail helpers are inspired by the work done in GSOC on
# testmodule.py by Prashanth Mohan.

class TestingHelper(object):

    def execute(self, buildscript):
        if not buildscript.config.noxvfb:
            x = XvfbWrapper(buildscript.config.xvfbargs)
            x.execute(self._execute, buildscript)
        else:
            self._execute(buildscript)


class GDTHelper(TestingHelper):
    """
    Helper object for running gnome-destop-testing tests

    gnome-desktop-testing is different to LDTP and dogtail in that we can
    do 'desktop-testing -a gedit' to run just the gedit tests. And because
    the tests are installable, we can easily add additional tests seperately
    to the g-d-t repository.

    Eventually we might be able to move the tests to the applications
    themselves and even go as far as distros packaging them.
    """

    def __init__(self, application=None):
        self.application = application

    def _execute(self, buildscript):
        testargs = ['desktop-testing']

        if self.application:
            testargs.extend(['-a', self.application])

        buildscript.execute(testargs)


class LDTPHelper(TestingHelper):
    """
    Helper object for running ldtprunner

    For running ldtp tests we expect a directory of tests with a run.xml
    specifying which tests to run. They are executed with ldtprunner.
    """

    def __init__(self, directory):
        self.directory = directory

    def _start_ldtp(self):
        ldtp = subprocess.Popen('ldtp', shell=False)
        time.sleep(1)
        if ldtp.poll() != None:
            raise FatalError(_("Unable to start ldtp"))
        return ldtp

    def _execute(self, buildscript):
        ldtp = self._start_ldtp()
        try:
            buildscript.execute("ldtprunner run.xml", cwd=self.directory)
        finally:
            os.kill(ldtp.pid, signal.SIGINT)


class DogtailHelper(TestingHelper):
    """
    Helper object for running dogtail tests

    For dogtail, we expect a directory of tests as .py files. We run them
    directly with python.
    """

    def __init__(self, directory):
        self.directory = directory

    def _execute(self, buildscript):
        testcases = [f for f in os.listdir(self.directory) if f.endswith('.py')]
        for testcase in testcases:
            buildscript.execute('python %s' % testcase, cwd=self.directory)


