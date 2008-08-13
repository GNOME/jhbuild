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

