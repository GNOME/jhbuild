# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2008  apinheiro@igalia.com, John Carr, Frederic Peters
#
#   scheduler.py: jhbuild jobs scheduler 
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
from twisted.application import service, internet

from buildbot.scheduler import Periodic, BaseUpstreamScheduler
from buildbot.sourcestamp import SourceStamp
from buildbot import buildset

def SerialScheduler(name, builderNames, periodicBuildTimer=60*60*12, upstream=None, branch=None):
    if not upstream:
        return StartSerial(name, builderNames, periodicBuildTimer, branch)
    return Serial(name, upstream, builderNames, branch)

class StartSerial(Periodic):

    def __init__(self, name, builderNames, periodicBuildTimer,
                 branch=None):
        Periodic.__init__(self,name,builderNames,periodicBuildTimer,branch)
        self.finishedWatchers = []

    def subscribeToFinishedBuilds(self, watcher):
        self.finishedWatchers.append(watcher)

    def unsubscribeToFinishedBuilds(self, watcher):
        self.finishedWatchers.remove(watcher)

    def buildSetFinished(self, bss):
        if not self.running:
            return
        ss = bss.getSourceStamp()
        for w in self.finishedWatchers:
            w(ss)
        Periodic.buildSetFinished(self,bss)

class Serial(BaseUpstreamScheduler):
    """This scheduler runs some set of builds that should be run
    after the 'upstream' scheduler has completed (successfully or not)."""
    compare_attrs = ('name', 'upstream', 'builders', 'branch')

    def __init__(self, name, upstream, builderNames, branch):
        BaseUpstreamScheduler.__init__(self, name)
        self.upstream = upstream
        self.branch = branch
        self.builderNames = builderNames
        self.finishedWatchers = []

    def subscribeToFinishedBuilds(self, watcher):
        self.finishedWatchers.append(watcher)

    def unsubscribeToFinishedBuilds(self, watcher):
        self.finishedWatchers.remove(watcher)

    def buildSetFinished(self, bss):
        if not self.running:
            return
        ss = bss.getSourceStamp()
        for w in self.finishedWatchers:
            w(ss)
        BaseUpstreamScheduler.buildSetFinished(self,bss)

    def listBuilderNames(self):
        return self.builderNames

    def getPendingBuildTimes(self):
        # report the upstream's value
        return self.upstream.getPendingBuildTimes()

    def startService(self):
        service.MultiService.startService(self)
        self.upstream.subscribeToFinishedBuilds(self.upstreamBuilt)

    def stopService(self):
        d = service.MultiService.stopService(self)
        self.upstream.unsubscribeToFinishedBuilds(self.upstreamBuilt)
        return d

    def upstreamBuilt(self, ss):
        bs = buildset.BuildSet(self.builderNames, SourceStamp(branch=self.branch))
        self.submitBuildSet(bs)

