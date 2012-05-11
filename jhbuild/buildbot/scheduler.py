# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2008  Igalia S.L., John Carr, Frederic Peters
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
from buildbot.scheduler import Periodic, BaseUpstreamScheduler, Scheduler, Nightly
from buildbot.sourcestamp import SourceStamp
from buildbot import buildset, util

def SerialScheduler(name, project, builderNames, periodicBuildTimer=60*60*12,
        upstream=None, branch=None):
    if not upstream:
        return StartSerial(name, project, builderNames, periodicBuildTimer, branch)
    return Serial(name, project, upstream, builderNames, branch)

def NightlySerialScheduler(name, project, builderNames,
        minute=0, hour='*', dayOfMonth='*', month='*', dayOfWeek='*',
        upstream=None, branch=None):
    if not upstream:
        return NightlyStartSerial(name, project, builderNames,
                minute, hour, dayOfMonth, month, dayOfWeek, branch)
    return Serial(name, project, upstream, builderNames, branch)


class OnCommitScheduler(Scheduler):
    '''
    Scheduler that will build a module when a change notification
    (on svn-commits-list) is received.
    '''
    def __init__(self, name, project, builderNames, properties={}):
        Scheduler.__init__(self, name, branch=None, treeStableTimer=180,
                builderNames=builderNames, properties=properties)
        self.project = project
        self.importantChanges = []
        self.unimportantChanges = []
        self.nextBuildTime = None
        self.timer = None

    def changeIsImportant(self, change):
        if not change.files:
            # strange, better be on the safe side
            return True
        non_po_files = [x for x in change.files if not '/po/' in x]
        if non_po_files:
            return True
        # changes are limited to translations, it is unlikely it would break
        # the build, mark them as unimportant.
        return False

    def addChange(self, change):
        if change.project != self.project:
            return
        if change.branch != self.branch:
            return
        log.msg('adding a change')
        if self.changeIsImportant(change):
            self.addImportantChange(change)
        else:
            self.addUnimportantChange(change)

class StartSerial(Periodic):

    def __init__(self, name, project, builderNames, periodicBuildTimer,
                 branch=None):
        Periodic.__init__(self,name,builderNames,periodicBuildTimer,branch)
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

class Serial(BaseUpstreamScheduler):
    """This scheduler runs some set of builds that should be run
    after the 'upstream' scheduler has completed (successfully or not)."""
    compare_attrs = ('name', 'upstream', 'builders', 'branch')

    def __init__(self, name, project, upstream, builderNames, branch):
        BaseUpstreamScheduler.__init__(self, name)
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


class NightlyStartSerial(Nightly):
    def __init__(self, name, project, builderNames,
                 minute=0, hour='*', dayOfMonth='*', month='*', dayOfWeek='*',
                 branch=None):
        Nightly.__init__(self, name, builderNames, minute, hour, dayOfMonth,
                         month, dayOfWeek, branch)
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
        Nightly.buildSetFinished(self,bss)

