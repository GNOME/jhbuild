from twisted.application import service
from buildbot.master import BuildMaster
import os

basedir = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(os.path.join(basedir, 'builddir')):
    os.makedirs(os.path.join(basedir, 'builddir'))
configfile = r'master.cfg'

application = service.Application('buildmaster')
BuildMaster(basedir, configfile).setServiceParent(application)

