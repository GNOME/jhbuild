from buildbot.process import factory
from steps import JHBuildSource, JHBuildCommand, JHBuildModulePathTestCommand, JHBuildModulePathCommand

# This is the JHBuild factory. It creates a standard procedure to compile modules, run
# checks and create reports.

class JHBuildFactory(factory.BuildFactory):
    module = None
    moduleset = None
    targets = []
    steps = []

    def __init__(self, module):
        factory.BuildFactory.__init__(self)
        self.moduleset = jhbuild_config.moduleset
        self.module = module
        self.getSteps()

    def getSteps(self):
        self.addStep(JHBuildSource, moduleset=self.moduleset, module=self.module)
        self.addStep(JHBuildCommand, stage='build', moduleset=self.moduleset, module=self.module)
        self.addStep(JHBuildCommand, stage='check', moduleset=self.moduleset, module=self.module)
        #self.addStep(JHBuildModulePathTestCommand, moduleset=self.moduleset, module=self.module, action=['make-check.sh'], haltOnFailure = False)
        #self.addStep(JHBuildModulePathCommand, moduleset=self.moduleset, module=self.module, action=['module-reports.sh'], haltOnFailure = False)

    def newBuild(self, request):
        return factory.BuildFactory.newBuild(self, request)
