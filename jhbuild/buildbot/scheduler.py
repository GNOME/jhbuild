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

import time

from twisted.application import service, internet
from twisted.python import log

from twisted.internet import reactor
from buildbot.scheduler import Periodic, BaseUpstreamScheduler
from buildbot.sourcestamp import SourceStamp
from buildbot import buildset, util

def SerialScheduler(name, project, builderNames, periodicBuildTimer=60*60*12,
        upstream=None, branch=None):
    if not upstream:
        return StartSerial(name, project, builderNames, periodicBuildTimer, branch)
    return Serial(name, project, upstream, builderNames, branch)


class ChangeNotification:
    fileIsImportant = None
    treeStableTimer = 180

    def __init__(self):
        self.importantChanges = []
        self.unimportantChanges = []
        self.nextBuildTime = None
        self.timer = None

    def addChange(self, change):
        log.msg('adding a change')
        if change.project != self.project:
            log.msg('ignoring change as %s != %s' % (change.project, self.project))
            return
        if change.branch != self.branch:
            return
        if not self.fileIsImportant:
            self.addImportantChange(change)
        elif self.fileIsImportant(change):
            self.addImportantChange(change)
        else:
            self.addUnimportantChange(change)

    def addImportantChange(self, change):
        log.msg("%s: change is important, adding %s" % (self, change))
        self.importantChanges.append(change)
        self.nextBuildTime = max(self.nextBuildTime,
                                 change.when + self.treeStableTimer)
        self.setTimer(self.nextBuildTime)

    def addUnimportantChange(self, change):
        log.msg("%s: change is not important, adding %s" % (self, change))
        self.unimportantChanges.append(change)

    def setTimer(self, when):
        log.msg("%s: setting timer to %s" %
                (self, time.strftime("%H:%M:%S", time.localtime(when))))
        now = util.now()
        if when < now:
            when = now + 1
        if self.timer:
            self.timer.cancel()
        self.timer = reactor.callLater(when - now, self.fireTimer)

    def stopTimer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def fireTimer(self):
        # clear out our state
        self.timer = None
        self.nextBuildTime = None
        changes = self.importantChanges + self.unimportantChanges
        self.importantChanges = []
        self.unimportantChanges = []

        # create a BuildSet, submit it to the BuildMaster
        bs = buildset.BuildSet(self.builderNames,
                               SourceStamp(changes=changes),
                               properties=self.properties)
        self.submitBuildSet(bs)


class StartSerial(ChangeNotification, Periodic):

    def __init__(self, name, project, builderNames, periodicBuildTimer,
                 branch=None):
        Periodic.__init__(self,name,builderNames,periodicBuildTimer,branch)
        ChangeNotification.__init__(self)
        self.project = project
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

class Serial(ChangeNotification, BaseUpstreamScheduler):
    """This scheduler runs some set of builds that should be run
    after the 'upstream' scheduler has completed (successfully or not)."""
    compare_attrs = ('name', 'upstream', 'builders', 'branch')

    def __init__(self, name, project, upstream, builderNames, branch):
        BaseUpstreamScheduler.__init__(self, name)
        ChangeNotification.__init__(self)
        self.project = project
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

