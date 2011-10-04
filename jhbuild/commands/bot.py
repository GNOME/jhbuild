# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2008 Frederic Peters
#
#   bot.py: buildbot control commands
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
#
# Some methods are derived from Buildbot own methods (when it was not possible
# to override just some parts of them).  Buildbot is also licensed under the
# GNU General Public License.

import os
import signal
import sys
import urllib
from optparse import make_option
import socket
import __builtin__
import csv
import logging

try:
    import elementtree.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.commands import Command, register_command
from jhbuild.commands.base import cmd_build
from jhbuild.config import addpath
from jhbuild.errors import UsageError, FatalError, CommandError

try:
    import buildbot
except ImportError:
    buildbot = None

class cmd_bot(Command):
    doc = N_('Control buildbot')

    name = 'bot'
    usage_args = N_('[ options ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('--setup',
                        action='store_true', dest='setup', default=False,
                        help=_('setup a buildbot environment')),
            make_option('--start',
                        action='store_true', dest='start', default=False,
                        help=_('start a buildbot slave server')),
            make_option('--stop',
                        action='store_true', dest='stop', default=False,
                        help=_('stop a buildbot slave server')),
            make_option('--start-server',
                        action='store_true', dest='start_server', default=False,
                        help=_('start a buildbot master server')),
            make_option('--reload-server-config',
                        action='store_true', dest='reload_server_config', default=False,
                        help=_('reload a buildbot master server configuration')),
            make_option('--stop-server',
                        action='store_true', dest='stop_server', default=False,
                        help=_('stop a buildbot master server')),
            make_option('--daemon',
                        action='store_true', dest='daemon', default=False,
                        help=_('start as daemon')),
            make_option('--pidfile', metavar='PIDFILE',
                        action='store', dest='pidfile', default=None,
                        help=_('pid file location')),
            make_option('--logfile', metavar='LOGFILE',
                        action='store', dest='logfile', default=None,
                        help=_('log file location')),
            make_option('--slaves-dir', metavar='SLAVESDIR',
                        action='store', dest='slaves_dir', default=None,
                        help=_('directory with slave files (only with --start-server)')),
            make_option('--buildbot-dir', metavar='BUILDBOTDIR',
                        action='store', dest='buildbot_dir', default=None,
                        help=_('directory with buildbot work files (only with --start-server)')),
            make_option('--mastercfg', metavar='CFGFILE',
                        action='store', dest='mastercfgfile', default=None,
                        help=_('master cfg file location (only with --start-server)')),
            make_option('--step',
                        action='store_true', dest='step', default=False,
                        help=_('exec a buildbot step (internal use only)')),
            ])

    def run(self, config, options, args, help=None):
        if options.setup:
            return self.setup(config)

        global buildbot
        if buildbot is None:
            import site
            pythonversion = 'python' + str(sys.version_info[0]) + '.' + str(sys.version_info[1])
            pythonpath = os.path.join(config.prefix, 'lib', pythonversion, 'site-packages')
            site.addsitedir(pythonpath)
            if config.use_lib64:
                pythonpath = os.path.join(config.prefix, 'lib64', pythonversion, 'site-packages')
                site.addsitedir(pythonpath)
            try:
                import buildbot
            except ImportError:
                raise FatalError(_('buildbot and twisted not found, run jhbuild bot --setup'))

        # make jhbuild config file accessible to buildbot files
        # (master.cfg , steps.py, etc.)
        __builtin__.__dict__['jhbuild_config'] = config

        daemonize = False
        pidfile = None
        logfile = None
        slaves_dir = config.jhbuildbot_slaves_dir
        mastercfgfile = config.jhbuildbot_mastercfg
        buildbot_dir = config.jhbuildbot_dir

        if options.daemon:
            daemonize = True
        if options.pidfile:
            pidfile = options.pidfile
        if options.logfile:
            logfile = options.logfile
        if options.slaves_dir:
            slaves_dir = options.slaves_dir
        if options.mastercfgfile:
            mastercfgfile = options.mastercfgfile
        if options.buildbot_dir:
            buildbot_dir = os.path.abspath(options.buildbot_dir)

        if options.start:
            return self.start(config, daemonize, pidfile, logfile)

        if options.step:
            os.environ['JHBUILDRC'] = config.filename
            os.environ['LC_ALL'] = 'C'
            os.environ['LANGUAGE'] = 'C'
            os.environ['LANG'] = 'C'
            __builtin__.__dict__['_'] = lambda x: x
            config.interact = False
            config.nonetwork = True
            os.environ['TERM'] = 'dumb'
            if args[0] in ('update', 'build', 'check', 'clean'):
                module_set = jhbuild.moduleset.load(config)
                buildscript = jhbuild.frontends.get_buildscript(config,
                        [module_set.get_module(x, ignore_case=True) for x in args[1:]],
                                                                module_set=module_set)
                phases = None
                if args[0] == 'update':
                    config.nonetwork = False
                    phases = ['checkout']
                elif args[0] == 'build':
                    # make check will be run in another step
                    config.makecheck = False
                    config.build_targets = ['install']
                elif args[0] == 'check':
                    config.makecheck = True
                    config.build_targets = ['check']
                    phases = ['check']
                elif args[0] == 'clean':
                    phases = ['clean']
                rc = buildscript.build(phases=phases)
            else:
                command = args[0]
                rc = jhbuild.commands.run(command, config, args[1:], help=None)
            sys.exit(rc)

        if options.start_server:
            return self.start_server(config, daemonize, pidfile, logfile,
                    slaves_dir, mastercfgfile, buildbot_dir)

        if options.stop or options.stop_server:
            return self.stop(config, pidfile)

        if options.reload_server_config:
            return self.reload_server_config(config, pidfile)

    def setup(self, config):
        module_set = jhbuild.moduleset.load(config, 'buildbot')
        module_list = module_set.get_module_list('all', config.skip)
        build = jhbuild.frontends.get_buildscript(config, module_list, module_set=module_set)
        return build.build()
    
    def start(self, config, daemonize, pidfile, logfile):
        from twisted.application import service
        application = service.Application('buildslave')
        if ':' in config.jhbuildbot_master:
            master_host, master_port = config.jhbuildbot_master.split(':')
            master_port = int(master_port)
        else:
            master_host, master_port = config.jhbuildbot_master, 9070

        slave_name = config.jhbuildbot_slavename or socket.gethostname()

        keepalive = 600
        usepty = 0
        umask = None
        basedir = os.path.join(config.checkoutroot, 'jhbuildbot')
        if not os.path.exists(os.path.join(basedir, 'builddir')):
            os.makedirs(os.path.join(basedir, 'builddir'))
        os.chdir(basedir)

        from buildbot.slave.bot import BuildSlave
        s = BuildSlave(master_host, master_port,
                slave_name, config.jhbuildbot_password, basedir,
                keepalive, usepty, umask=umask)
        s.setServiceParent(application)


        from twisted.scripts._twistd_unix import UnixApplicationRunner, ServerOptions

        opts = ['--no_save']
        if not daemonize:
            opts.append('--nodaemon')
        if pidfile:
            opts.extend(['--pidfile', pidfile])
        if logfile:
            opts.extend(['--logfile', logfile])
        options = ServerOptions()
        options.parseOptions(opts)

        class JhBuildbotApplicationRunner(UnixApplicationRunner):
            application = None

            def createOrGetApplication(self):
                return self.application

        JhBuildbotApplicationRunner.application = application
        JhBuildbotApplicationRunner(options).run()

    def start_server(self, config, daemonize, pidfile, logfile, slaves_dir,
            mastercfgfile, buildbot_dir):

        from twisted.scripts._twistd_unix import UnixApplicationRunner, ServerOptions

        opts = ['--no_save']
        if not daemonize:
            opts.append('--nodaemon')
        if pidfile:
            opts.extend(['--pidfile', pidfile])
        if pidfile:
            opts.extend(['--logfile', logfile])
        options = ServerOptions()
        options.parseOptions(opts)

        class JhBuildbotApplicationRunner(UnixApplicationRunner):
            application = None

            def createOrGetApplication(self):
                return self.application

        from twisted.application import service, strports
        from buildbot.master import BuildMaster
        application = service.Application('buildmaster')
        from buildbot.buildslave import BuildSlave

        from twisted.python import log
        from twisted.internet import defer
        from buildbot import interfaces
        from buildbot.process.properties import Properties

        class JhBuildSlave(BuildSlave):
            contact_name = None
            contact_email = None
            url = None
            distribution = None
            architecture = None
            version = None

            max_builds = 2
            scheduler = None

            run_checks = True
            run_coverage_report = False
            run_clean_afterwards = False

            def load_extra_configuration(self, slaves_dir):
                from twisted.python import log
                slave_xml_file = os.path.join(slaves_dir, self.slavename + '.xml')
                if not os.path.exists(slave_xml_file):
                    log.msg(_('No description for slave %s.') % self.slavename)
                    return
                try:
                    cfg = ET.parse(slave_xml_file)
                except: # parse error
                    log.msg(_('Failed to parse slave config for %s.') % self.slavename)
                    return

                for attribute in ('config/max_builds', 'config/missing_timeout',
                            'config/run_checks', 'config/run_coverage_report',
                            'config/run_clean_afterwards',
                            'config/scheduler',
                            'nightly_scheduler/minute',
                            'nightly_scheduler/hour',
                            'nightly_scheduler/dayOfMonth',
                            'nightly_scheduler/month',
                            'nightly_scheduler/dayOfWeek',
                            'info/contact_name', 'info/contact_email',
                            'info/url', 'info/distribution', 'info/architecture',
                            'info/version'):
                    attr_name = attribute.split('/')[-1]
                    try:
                        value = cfg.find(attribute).text
                    except AttributeError:
                        continue

                    if attr_name in ('max_builds', 'missing_timeout'): # int value
                        try:
                            value = int(value)
                        except ValueError:
                            continue

                    if attr_name in ('run_checks', 'run_coverage_report', 'run_clean_afterwards'):
                        value = (value == 'yes')

                    if attr_name in ('minute', 'hour', 'dayOfMonth', 'month', 'dayOfWeek'):
                        try:
                            value = int(value)
                        except ValueError:
                            value = '*'

                    setattr(self, attr_name, value)

                if self.scheduler == 'nightly':
                    self.nightly_kwargs = {}
                    for attr_name in ('minute', 'hour', 'dayOfMonth', 'month', 'dayOfWeek'):
                        if hasattr(self, attr_name):
                            self.nightly_kwargs[attr_name] = getattr(self, attr_name)

        class JhBuildMaster(BuildMaster):
            jhbuild_config = config
            def loadConfig(self, f):
                # modified from parent method to get slaves, projects, change
                # sources, schedulers, builders and web status ouf of
                # master.cfg [it would have been cleaner if jhbuild didn't
                # have to copy all that code.]
                localDict = {'basedir': os.path.expanduser(self.basedir)}
                try:
                    exec f in localDict
                except:
                    log.msg("error while parsing config file")
                    raise

                jhbuild_config.load()

                try:
                    config = localDict['BuildmasterConfig']
                except KeyError:
                    log.err("missing config dictionary")
                    log.err("config file must define BuildmasterConfig")
                    raise

                known_keys = ("bots", "slaves",
                              "sources", "change_source",
                              "schedulers", "builders", "mergeRequests",
                              "slavePortnum", "debugPassword", "logCompressionLimit",
                              "manhole", "status", "projectName", "projectURL",
                              "buildbotURL", "properties", "prioritizeBuilders",
                              "eventHorizon", "buildCacheSize", "logHorizon", "buildHorizon",
                              "changeHorizon", "logMaxSize", "logMaxTailSize",
                              "logCompressionMethod",
                              )
                for k in config.keys():
                    if k not in known_keys:
                        log.msg("unknown key '%s' defined in config dictionary" % k)

                # the 'slaves' list is read from the 'slaves.csv' file in the
                # current directory (unless instructed different from command line) 
                # it is a CSV file structured like this:
                #   slavename,password
                config['slaves'] = []
                slaves_csv_file = os.path.join(slaves_dir, 'slaves.csv')
                if os.path.exists(slaves_csv_file):
                    for x in csv.reader(file(slaves_csv_file)):
                        if not x or x[0].startswith('#'):
                            continue
                        kw = {}
                        build_slave = JhBuildSlave(x[0], x[1])
                        build_slave.load_extra_configuration(slaves_dir)
                        config['slaves'].append(build_slave)

                if len(config['slaves']) == 0:
                    log.msg('you must fill slaves.csv with slaves')

                module_set = jhbuild.moduleset.load(self.jhbuild_config)
                module_list = module_set.get_module_list(
                        self.jhbuild_config.modules,
                        self.jhbuild_config.skip,
                        include_optional_modules=True)
                config['projects'] = [x.name for x in module_list \
                                      if not x.name.startswith('meta-')]

                if self.jhbuild_config.jhbuildbot_svn_commits_box:
                    # trigger builds from mails to svn-commit-list
                    # (note Maildir must be correct, or everything will fail)
                    from jhbuild.buildbot.changes import GnomeMaildirSource
                    config['change_source'] = GnomeMaildirSource(
                            self.jhbuild_config.jhbuildbot_svn_commits_box,
                            modules=module_list,
                            prefix=None)
                else:
                    # support injection (use 'buildbot sendchange')
                    from buildbot.changes.pb import PBChangeSource
                    config['change_source'] = PBChangeSource()

                # Schedulers
                from jhbuild.buildbot.scheduler import SerialScheduler, NightlySerialScheduler, OnCommitScheduler
                config['schedulers'] = []
                for slave in config['slaves']:
                    s = None
                    for project in config['projects']:
                        buildername = str('%s-%s' % (project, slave.slavename))
                        scheduler_kwargs = {}
                        if slave.scheduler == 'nightly':
                            scheduler_class = NightlySerialScheduler
                            scheduler_kwargs = slave.nightly_kwargs
                        else:
                            scheduler_class = SerialScheduler
                        s = scheduler_class(buildername, project, upstream=s,
                                            builderNames=[buildername],
                                            **scheduler_kwargs)
                        config['schedulers'].append(s)
                        if self.jhbuild_config.jhbuildbot_svn_commits_box:
                            # schedulers that will launch job when receiving
                            # change notifications
                            s2 = OnCommitScheduler('oc-' + buildername,
                                    project, builderNames=[buildername])
                            config['schedulers'].append(s2)

                # Builders
                from jhbuild.buildbot.factory import JHBuildFactory
                config['builders'] = []
                for project in config['projects']:
                    for slave in config['slaves']:
                        f = JHBuildFactory(project, slave)
                        config['builders'].append({
                            'name' : "%s-%s" % (project, slave.slavename),
                            'slavename' : slave.slavename,
                            'builddir' : 'builddir/%s.%s' % (project, slave.slavename),
                            'factory' : f,
                            'category' : project
                        })

                # Status targets
                if not config.has_key('status'):
                    # let it be possible to define additional status in
                    # master.cfg
                    config['status'] = []

                from jhbuild.buildbot.status.web import JHBuildWebStatus
                config['status'].append(
                    JHBuildWebStatus(
                        self.jhbuild_config.moduleset,
                        config['projects'],
                        [x.slavename for x in config['slaves']],
                        http_port=8080, allowForce=True)
                )

                # remaining of the method is a straight copy from buildbot
                # ...
                try:
                    # required
                    schedulers = config['schedulers']
                    builders = config['builders']
                    slavePortnum = config['slavePortnum']
                    #slaves = config['slaves']
                    #change_source = config['change_source']

                    # optional
                    debugPassword = config.get('debugPassword')
                    manhole = config.get('manhole')
                    status = config.get('status', [])
                    projectName = config.get('projectName')
                    projectURL = config.get('projectURL')
                    buildbotURL = config.get('buildbotURL')
                    properties = config.get('properties', {})
                    buildCacheSize = config.get('buildCacheSize', None)
                    eventHorizon = config.get('eventHorizon', None)
                    logHorizon = config.get('logHorizon', None)
                    buildHorizon = config.get('buildHorizon', None)
                    logCompressionLimit = config.get('logCompressionLimit', 4*1024)
                    if logCompressionLimit is not None and not \
                            isinstance(logCompressionLimit, int):
                        raise ValueError("logCompressionLimit needs to be bool or int")
                    logCompressionMethod = config.get('logCompressionMethod', "bz2")
                    if logCompressionMethod not in ('bz2', 'gz'):
                        raise ValueError("logCompressionMethod needs to be 'bz2', or 'gz'")
                    logMaxSize = config.get('logMaxSize')
                    if logMaxSize is not None and not \
                            isinstance(logMaxSize, int):
                        raise ValueError("logMaxSize needs to be None or int")
                    logMaxTailSize = config.get('logMaxTailSize')
                    if logMaxTailSize is not None and not \
                            isinstance(logMaxTailSize, int):
                        raise ValueError("logMaxTailSize needs to be None or int")
                    mergeRequests = config.get('mergeRequests')
                    if mergeRequests is not None and not callable(mergeRequests):
                        raise ValueError("mergeRequests must be a callable")
                    prioritizeBuilders = config.get('prioritizeBuilders')
                    if prioritizeBuilders is not None and not callable(prioritizeBuilders):
                        raise ValueError("prioritizeBuilders must be callable")
                    changeHorizon = config.get("changeHorizon")
                    if changeHorizon is not None and not isinstance(changeHorizon, int):
                        raise ValueError("changeHorizon needs to be an int")

                except KeyError, e:
                    log.msg("config dictionary is missing a required parameter")
                    log.msg("leaving old configuration in place")
                    raise

                #if "bots" in config:
                #    raise KeyError("c['bots'] is no longer accepted")

                slaves = config.get('slaves', [])
                if "bots" in config:
                    m = ("c['bots'] is deprecated as of 0.7.6 and will be "
                         "removed by 0.8.0 . Please use c['slaves'] instead.")
                    log.msg(m)
                    warnings.warn(m, DeprecationWarning)
                    for name, passwd in config['bots']:
                        slaves.append(JhBuildSlave(name, passwd))

                if "bots" not in config and "slaves" not in config:
                    log.msg("config dictionary must have either 'bots' or 'slaves'")
                    log.msg("leaving old configuration in place")
                    raise KeyError("must have either 'bots' or 'slaves'")

                #if "sources" in config:
                #    raise KeyError("c['sources'] is no longer accepted")

                if changeHorizon is not None:
                    self.change_svc.changeHorizon = changeHorizon

                change_source = config.get('change_source', [])
                if isinstance(change_source, (list, tuple)):
                    change_sources = change_source
                else:
                    change_sources = [change_source]
                if "sources" in config:
                    m = ("c['sources'] is deprecated as of 0.7.6 and will be "
                         "removed by 0.8.0 . Please use c['change_source'] instead.")
                    log.msg(m)
                    warnings.warn(m, DeprecationWarning)
                    for s in config['sources']:
                        change_sources.append(s)

                # do some validation first
                for s in slaves:
                    assert interfaces.IBuildSlave.providedBy(s)
                    if s.slavename in ("debug", "change", "status"):
                        raise KeyError(
                            "reserved name '%s' used for a bot" % s.slavename)
                if config.has_key('interlocks'):
                    raise KeyError("c['interlocks'] is no longer accepted")

                assert isinstance(change_sources, (list, tuple))
                for s in change_sources:
                    assert interfaces.IChangeSource(s, None)
                # this assertion catches c['schedulers'] = Scheduler(), since
                # Schedulers are service.MultiServices and thus iterable.
                errmsg = "c['schedulers'] must be a list of Scheduler instances"
                assert isinstance(schedulers, (list, tuple)), errmsg
                for s in schedulers:
                    assert interfaces.IScheduler(s, None), errmsg
                assert isinstance(status, (list, tuple))
                for s in status:
                    assert interfaces.IStatusReceiver(s, None)

                slavenames = [s.slavename for s in slaves]
                buildernames = []
                dirnames = []

                # convert builders from objects to config dictionaries
                builders_dicts = []
                for b in builders:
                    if isinstance(b, buildbot.config.BuilderConfig):
                        builders_dicts.append(b.getConfigDict())
                    elif type(b) is dict:
                        builders_dicts.append(b)
                    else:
                        raise ValueError("builder %s is not a BuilderConfig object (or a dict)" % b)
                builders = builders_dicts

                for b in builders:
                    if b.has_key('slavename') and b['slavename'] not in slavenames:
                        raise ValueError("builder %s uses undefined slave %s" \
                                         % (b['name'], b['slavename']))
                    for n in b.get('slavenames', []):
                        if n not in slavenames:
                            raise ValueError("builder %s uses undefined slave %s" \
                                             % (b['name'], n))
                    if b['name'] in buildernames:
                        raise ValueError("duplicate builder name %s"
                                         % b['name'])
                    buildernames.append(b['name'])

                    # sanity check name (BuilderConfig does this too)
                    if b['name'].startswith("_"):
                        errmsg = ("builder names must not start with an "
                                  "underscore: " + b['name'])
                        log.err(errmsg)
                        raise ValueError(errmsg)

                    # Fix the dictionnary with default values, in case this wasn't
                    # specified with a BuilderConfig object (which sets the same defaults)
                    b.setdefault('builddir', buildbot.util.safeTranslate(b['name']))
                    b.setdefault('slavebuilddir', b['builddir'])

                    if b['builddir'] in dirnames:
                        raise ValueError("builder %s reuses builddir %s"
                                         % (b['name'], b['builddir']))
                    dirnames.append(b['builddir'])

                unscheduled_buildernames = buildernames[:]
                schedulernames = []
                for s in schedulers:
                    for b in s.listBuilderNames():
                        assert b in buildernames, \
                               "%s uses unknown builder %s" % (s, b)
                        if b in unscheduled_buildernames:
                            unscheduled_buildernames.remove(b)

                    if s.name in schedulernames:
                        # TODO: schedulers share a namespace with other Service
                        # children of the BuildMaster node, like status plugins, the
                        # Manhole, the ChangeMaster, and the BotMaster (although most
                        # of these don't have names)
                        msg = ("Schedulers must have unique names, but "
                               "'%s' was a duplicate" % (s.name,))
                        raise ValueError(msg)
                    schedulernames.append(s.name)

                if unscheduled_buildernames:
                    log.msg("Warning: some Builders have no Schedulers to drive them:"
                            " %s" % (unscheduled_buildernames,))

                # assert that all locks used by the Builds and their Steps are
                # uniquely named.
                lock_dict = {}
                for b in builders:
                    for l in b.get('locks', []):
                        if isinstance(l, locks.LockAccess): # User specified access to the lock
                            l = l.lockid
                        if lock_dict.has_key(l.name):
                            if lock_dict[l.name] is not l:
                                raise ValueError("Two different locks (%s and %s) "
                                                 "share the name %s"
                                                 % (l, lock_dict[l.name], l.name))
                        else:
                            lock_dict[l.name] = l
                    # TODO: this will break with any BuildFactory that doesn't use a
                    # .steps list, but I think the verification step is more
                    # important.
                    for s in b['factory'].steps:
                        for l in s[1].get('locks', []):
                            if isinstance(l, locks.LockAccess): # User specified access to the lock
                                l = l.lockid
                            if lock_dict.has_key(l.name):
                                if lock_dict[l.name] is not l:
                                    raise ValueError("Two different locks (%s and %s)"
                                                     " share the name %s"
                                                     % (l, lock_dict[l.name], l.name))
                            else:
                                lock_dict[l.name] = l

                if not isinstance(properties, dict):
                    raise ValueError("c['properties'] must be a dictionary")

                # slavePortnum supposed to be a strports specification
                if type(slavePortnum) is int:
                    slavePortnum = "tcp:%d" % slavePortnum

                # now we're committed to implementing the new configuration, so do
                # it atomically
                # TODO: actually, this is spread across a couple of Deferreds, so it
                # really isn't atomic.

                d = defer.succeed(None)

                self.projectName = projectName
                self.projectURL = projectURL
                self.buildbotURL = buildbotURL

                self.properties = Properties()
                self.properties.update(properties, self.configFileName)

                self.status.logCompressionLimit = logCompressionLimit
                self.status.logCompressionMethod = logCompressionMethod
                self.status.logMaxSize = logMaxSize
                self.status.logMaxTailSize = logMaxTailSize
                # Update any of our existing builders with the current log parameters.
                # This is required so that the new value is picked up after a
                # reconfig.
                for builder in self.botmaster.builders.values():
                    builder.builder_status.setLogCompressionLimit(logCompressionLimit)
                    builder.builder_status.setLogCompressionMethod(logCompressionMethod)
                    builder.builder_status.setLogMaxSize(logMaxSize)
                    builder.builder_status.setLogMaxTailSize(logMaxTailSize)

                if mergeRequests is not None:
                    self.botmaster.mergeRequests = mergeRequests
                if prioritizeBuilders is not None:
                    self.botmaster.prioritizeBuilders = prioritizeBuilders

                self.buildCacheSize = buildCacheSize
                self.eventHorizon = eventHorizon
                self.logHorizon = logHorizon
                self.buildHorizon = buildHorizon

                # self.slaves: Disconnect any that were attached and removed from the
                # list. Update self.checker with the new list of passwords, including
                # debug/change/status.
                d.addCallback(lambda res: self.loadConfig_Slaves(slaves))

                # self.debugPassword
                if debugPassword:
                    self.checker.addUser("debug", debugPassword)
                    self.debugPassword = debugPassword

                # self.manhole
                if manhole != self.manhole:
                    # changing
                    if self.manhole:
                        # disownServiceParent may return a Deferred
                        d.addCallback(lambda res: self.manhole.disownServiceParent())
                        def _remove(res):
                            self.manhole = None
                            return res
                        d.addCallback(_remove)
                    if manhole:
                        def _add(res):
                            self.manhole = manhole
                            manhole.setServiceParent(self)
                        d.addCallback(_add)

                # add/remove self.botmaster.builders to match builders. The
                # botmaster will handle startup/shutdown issues.
                d.addCallback(lambda res: self.loadConfig_Builders(builders))

                d.addCallback(lambda res: self.loadConfig_status(status))

                # Schedulers are added after Builders in case they start right away
                d.addCallback(lambda res: self.loadConfig_Schedulers(schedulers))
                # and Sources go after Schedulers for the same reason
                d.addCallback(lambda res: self.loadConfig_Sources(change_sources))

                # self.slavePort
                if self.slavePortnum != slavePortnum:
                    if self.slavePort:
                        def closeSlavePort(res):
                            d1 = self.slavePort.disownServiceParent()
                            self.slavePort = None
                            return d1
                        d.addCallback(closeSlavePort)
                    if slavePortnum is not None:
                        def openSlavePort(res):
                            self.slavePort = strports.service(slavePortnum,
                                                              self.slaveFactory)
                            self.slavePort.setServiceParent(self)
                        d.addCallback(openSlavePort)
                        log.msg("BuildMaster listening on port %s" % slavePortnum)
                    self.slavePortnum = slavePortnum

                log.msg("configuration update started")
                def _done(res):
                    self.readConfig = True
                    log.msg("configuration update complete")
                d.addCallback(_done)
                d.addCallback(lambda res: self.botmaster.maybeStartAllBuilds())
                return d

        if buildbot_dir:
            basedir = buildbot_dir
        else:
            if PKGDATADIR:
                basedir = os.path.join(PKGDATADIR, 'buildbot')
            else:
                basedir = os.path.join(SRCDIR, 'buildbot')
        os.chdir(basedir)
        if not os.path.exists(os.path.join(basedir, 'builddir')):
            os.makedirs(os.path.join(basedir, 'builddir'))
        master_cfg_path = mastercfgfile

        JhBuildMaster(basedir, master_cfg_path).setServiceParent(application)

        JhBuildbotApplicationRunner.application = application
        JhBuildbotApplicationRunner(options).run()

    def stop(self, config, pidfile):
        try:
            pid = int(file(pidfile).read())
        except:
            raise FatalError(_('failed to get buildbot PID'))

        os.kill(pid, signal.SIGTERM)

    def reload_server_config(self, config, pidfile):
        try:
            pid = int(file(pidfile).read())
        except:
            raise FatalError(_('failed to get buildbot PID'))

        os.kill(pid, signal.SIGHUP)


register_command(cmd_bot)

