# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2008  apinheiro@igalia.com, John Carr, Frederic Peters
#
#   steps.py: custom buildbot steps
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

import os, commands, re, StringIO

from buildbot.process import factory
from buildbot.process import buildstep
from buildbot import steps
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION

class JHBuildSource(steps.source.Source):
    name = "jhbuild"

    def __init__ (self, moduleset=None, module=None, stage=None, **kwargs):
        steps.source.Source.__init__(self, **kwargs)
        self.moduleset = moduleset
        self.module = module
        self.name = module + ' update'
        self.description = [module + ' updating']
        self.descriptionDone = [module + ' updated']

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        return max([int(c.revision) for c in changes])

    def startVC(self, branch, revision, patch):
        command = ['jhbuild']
        if (self.moduleset is not None):
            command += ['--moduleset='+self.moduleset]
        command += ['bot', '--step', 'updateone', self.module]
        properties = self.build.getProperties()
        kwargs = {}
        kwargs['workdir'] = './'
        #kwargs = properties.render(self.remote_kwargs)
        kwargs['command'] = properties.render(command)
        kwargs['env'] = {}
        cmd = buildstep.RemoteShellCommand(**kwargs)
        self.startCommand(cmd)

class UnitTestsObserver(buildstep.LogLineObserver):

    def __init__(self):
        self.regroupfailed = []
        self.regrouppassed = []
        self.reunittest = []
        self.unittests = []
        buildstep.LogLineObserver.__init__(self)
        if len(self.regroupfailed) == 0:
            self.regroupfailed.append((re.compile('^(FAIL:) (.*)$'), 1))
        if len(self.regrouppassed) == 0:
            self.regrouppassed.append((re.compile('^(PASS:) (.*)$'), 1))
        if len(self.reunittest) == 0:
            self.reunittest.append((re.compile('^([^:]*):([^:]*):([^:]*):([^:]*):([^:]*):([^:]*).*$'), 4, 5))

    def outLineReceived(self, line):
        matched = False
        for r in self.regroupfailed:
            result = r[0].search(line)
            if result:
                self.step.failedTestsCount += 1
                self.step.testsResults.append((result.groups()[r[1]].strip(), False, self.unittests))
                self.unittests = []
                matched = True
        if not matched:
            for r in self.regrouppassed:
                result = r[0].search(line)
                if result:
                    self.step.passedTestsCount += 1
                    self.step.testsResults.append((result.groups()[r[1]].strip(), True, self.unittests))
                    self.unittests = []
                    matched = True
        if not matched:
            for r in self.reunittest:
                result = r[0].search(line)
                if result:
                    err_msg = result.groups()[r[2]].strip()
                    if err_msg == "Passed":
                        self.unittests.append((result.groups()[r[1]].strip(), True, err_msg))
                    else:
                        self.unittests.append((result.groups()[r[1]].strip(), False, err_msg))
                    matched = True

class JHBuildCommand(steps.shell.ShellCommand):
    name = "jhbuild_stage"
    haltOnFailure = 1
    description = ["jhbuild command"]
    descriptionDone = ["jhbuild"]
    command = None
    OFFprogressMetrics = ('output',)

    # things to track: number of files compiled, number of directories
    # traversed (assuming 'make' is being used)
    def __init__(self, stage=None,module=None, moduleset=None, **kwargs):
        assert module is not None
        kwargs['workdir'] = "./"
        #workdir = "./"
        command = ['jhbuild']
        if (moduleset is not None):
            command += ['--moduleset='+moduleset]
        command += ['bot', '--step', stage, module]
        self.name = module + ' ' + stage
        self.description = [module + ' ' + stage + ' (running)']
        self.descriptionDone = [module + ' ' + stage]
        steps.shell.ShellCommand.__init__(self, description=self.description,
                              descriptionDone=self.descriptionDone, command=command, **kwargs)

    def getText(self, cmd, results):
        text = self.describe(True)[:]
        return text

class JHBuildModulePathCommand(steps.shell.ShellCommand):
    name = "jhbuild_stage"
    haltOnFailure = 1
    description = ["jhbuild command"]
    descriptionDone = ["jhbuild"]
    command = None
    OFFprogressMetrics = ('output',)

    # things to track: number of files compiled, number of directories
    # traversed (assuming 'make' is being used)
    def __init__(self, module=None, moduleset=None, action=[], **kwargs):
        assert module is not None
        kwargs['workdir'] = "./"
        #workdir = "./"
        command = ["jhbuild"]
        if (moduleset is not None):
            command += ['--moduleset='+moduleset]
        command += ['bot', '--step', 'run', '--in-builddir', module,
                '--', action]
        self.name=module+" "+" ".join(action)
        self.description = [" ".join(action) + '(run)']
        self.descriptionDone = [" ".join(action)]
        steps.shell.ShellCommand.__init__(self, description=self.description,
                                   descriptionDone=self.descriptionDone, command=command, **kwargs)

    def createSummary(self, log):
        output = StringIO.StringIO(log.getText())
        warnings = []
        for line in output.readlines():
            if "warning:" in line:
                warnings.append(line)
            if "buildbot-url:" in line:
                arr = line.split()
                if len(arr) == 3:
                    self.addURL(arr[1], arr[2])
        if (len(warnings) > 0):
            self.addCompleteLog('warnings', "".join(warnings))

    def getText(self, cmd, results):
        text = self.describe(True)[:]
        return text

class JHBuildModulePathTestCommand(JHBuildModulePathCommand):

    def __init__(self, module=None, moduleset=None, action=[], **kwargs):
        JHBuildModulePathCommand.__init__(self, module, moduleset, action, **kwargs)
        self.failedTestsCount = 0
        self.passedTestsCount = 0
        self.testsResults = []
        testFailuresObserver = UnitTestsObserver ()
        self.addLogObserver('stdio', testFailuresObserver)

    def createSummary(self, log):
        if self.failedTestsCount > 0 or self.passedTestsCount > 0:
            self.addHTMLLog ('tests summary', self.createTestsSummary())

    def getText(self, cmd, results):
        text = JHBuildModulePathCommand.getText(self, cmd, results)
        if self.failedTestsCount > 0 or self.passedTestsCount > 0:
            text.append("tests failed: " + str(self.failedTestsCount))
            text.append("tests passed: " + str(self.passedTestsCount))
        return text

    def evaluateCommand(self, cmd):
        if self.failedTestsCount > 0:
            return WARNINGS
        else:
            return SUCCESS

    def createTestsSummary (self):
        html = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"'
        html += '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
        html += '<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">\n'
        html += '<head>\n'
        html += ' <title>BuildBot: tests summary</title>\n'
        html += '<link href="/buildbot.css" rel="stylesheet" type="text/css"/>\n'
        html += '</head>\n'
        html += '<body vlink="#800080">\n'

        # Show summary
        html += '<table width="720" class="TestsSummary" cellspacing="0" cellpadding="4" align="center">\n'
        col = 0
        maxcolumns = 5

        for t in self.testsResults:
            if col == 0:
                html += '<tr>\n'
            if t[1]:
                ttdclass = "success"
            else:
                ttdclass = "failure"
            html += '<td width="20%" class="TestsSummary '+ ttdclass + '"><a href="#' + t[0] + '">' + t[0] + '</a></td>\n'
            col += 1
            if col >= maxcolumns:
                col = 0
                html += '</tr>\n'
        html += '</table>\n'

        html += '<br><hr>\n'

        # Show details
        for t in self.testsResults:
            html += '<br><br>\n'
            html += '<table align="center" width="720" class="TestsDetail" cellspacing="0" cellpadding="4">\n'
            if t[1]:
                ttdclass = "success"
            else:
                ttdclass = "failure"
            html += '<tr><td colspan="2" class="TestsDetailHeader ' + ttdclass + '"><a name="' + t[0]+ '"></a>' + t[0] + '</td></tr>\n'

            if len(t[2]) > 0:
                for ut in t[2]:
                    if ut[1]:
                        uttdclass = "success"
                    else:
                        uttdclass = "failure"
                    html += '<tr><td width="15" class="TestsDetail ' + uttdclass+ '">&nbsp;</td>\n'
                    html += '<td class="TestsDetail">' + ut[0]
                    if ut[1] == False:
                        html += '<br><span class="text' + uttdclass+ '">' + ut[2] + '</span>'
                    html += '</td></tr>'
            else:
                html += '<tr><td colspan="2" class="TestDetail">No unit tests found.</td></tr>\n'
            html += '</table>\n'

        html += '</body>\n'
        html += '</html>\n'

        return html

