# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2008  Igalia S.L., John Carr, Frederic Peters
#
#   factory.py: procedures to update, build and check modules
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
from buildbot.process import factory
from steps import JHBuildSource, JHBuildCommand, JHBuildModulePathCommand, JHBuildCheckCommand

class JHBuildFactory(factory.BuildFactory):
    module = None
    moduleset = None
    targets = []
    steps = []

    def __init__(self, module, slave):
        factory.BuildFactory.__init__(self)
        self.moduleset = jhbuild_config.moduleset
        self.module = module
        self.slave = slave
        self.getSteps()

    def getSteps(self):
        self.addStep(JHBuildSource, moduleset=self.moduleset, module=self.module)
        self.addStep(JHBuildCommand, stage='build', moduleset=self.moduleset, module=self.module)
        if self.slave.run_checks:
            self.addStep(JHBuildCheckCommand, moduleset=self.moduleset, module=self.module)
        if self.slave.run_coverage_report:
            self.addStep(JHBuildModulePathCommand, moduleset=self.moduleset,
                    module=self.module, action='module-reports.sh',
                    actionName='Coverage')
        if self.slave.run_clean_afterwards:
            self.addStep(JHBuildCommand, stage='clean', moduleset=self.moduleset,
                    module=self.module)

    def newBuild(self, request):
        return factory.BuildFactory.newBuild(self, request)
