# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2008 Igalia S.L., John Carr, Frederic Peters
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
        try:
            return max([int(c.revision) for c in changes])
        except ValueError:
            # in git, revisions are not integers, return last.
            return changes[-1].revision

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
        kwargs['timeout'] = 60*60
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


class JHBuildCheckCommand(JHBuildCommand):
    def __init__(self, **kwargs):
        JHBuildCommand.__init__(self, stage='check', **kwargs)
        self.failedTestsCount = 0
        self.passedTestsCount = 0
        self.testsResults = []
        self.addLogObserver('stdio', UnitTestsObserver())

    def evaluateCommand(self, cmd):
        if self.failedTestsCount > 0 or cmd.rc != 0:
            return WARNINGS
        else:
            return SUCCESS

    def getText(self, cmd, results):
        text = JHBuildCommand.getText(self, cmd, results)
        if self.failedTestsCount > 0 or self.passedTestsCount > 0:
            text.append('failed: %s' % self.failedTestsCount)
            text.append('passed: %s' % self.passedTestsCount)
        return text

    def createSummary(self, log):
        if self.failedTestsCount > 0 or self.passedTestsCount > 0:
            self.addHTMLLog('summary', self.createTestsSummary())

    def createTestsSummary (self):
        html = '<html>\n'
        html += '<head>\n'
        html += ' <title>Tests summary</title>\n'
        html += ' <link rel="stylesheet" type="text/css" href="/lgo.css">\n'
        html += ' <title>Tests summary</title>\n'
        html += '</head>\n'
        html += '<body>\n'

        # Show summary
        has_details = False
        html += '<ul id="tests-summary">\n'
        for t in self.testsResults:
            if t[1]:
                ttdclass = "success"
            else:
                ttdclass = "failure"
            if len(t[2]) > 0:
                html += '<li class="%s"><a href="#%s">%s</a></li>\n' % (ttdclass, t[0], t[0])
                has_details = True
            else:
                html += '<li class="%s">%s</a></li>\n' % (ttdclass, t[0])
        html += '</ul>\n'

        if has_details:
            # Show details
            html += '<dl id="test-details">\n'
            for t in self.testsResults:
                if len(t[2]) == 0:
                    continue
                if t[1]:
                    ttdclass = "success"
                else:
                    ttdclass = "failure"
                html += '<dt class="%s">%s</dt>\n' % (ttdclass, t[0])
                html += '<dd><ul>\n'

                for ut in t[2]:
                    if ut[1]:
                        uttdclass = "success"
                    else:
                        uttdclass = "failure"
                    html += '<li class="%s">' % uttdclass
                    html += ut[0]
                    if ut[1] == False:
                        html += ' ' + ut[2]
                    html += '</li>'
                html += '</ul></dd>\n'
            html += '</dl\n'

        html += '</body>\n'
        html += '</html>\n'

        return html


class JHBuildModulePathCommand(steps.shell.ShellCommand):
    name = "jhbuild_stage"
    haltOnFailure = 1
    description = ["jhbuild command"]
    descriptionDone = ["jhbuild"]
    command = None
    OFFprogressMetrics = ('output',)

    # things to track: number of files compiled, number of directories
    # traversed (assuming 'make' is being used)
    def __init__(self, module=None, moduleset=None, action='', actionName='', **kwargs):
        assert module is not None
        kwargs['workdir'] = "./"
        #workdir = "./"
        command = ["jhbuild"]
        if (moduleset is not None):
            command += ['--moduleset='+moduleset]
        actionParts = action.split(" ")
        command += ['run', '--in-builddir', module, '--']
        command += actionParts
        self.name = module + " " + actionName
        self.description = actionName + ' (running)'
        self.descriptionDone = [actionName]
        steps.shell.ShellCommand.__init__(self, description=self.description,
                                   descriptionDone=self.descriptionDone, command=command, **kwargs)

    def evaluateCommand(self, cmd):
        if self.haltOnFailure and cmd.rc != 0:
            return FAILURE
        elif cmd.rc != 0:
            return WARNINGS
        else:
            return SUCCESS	

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

