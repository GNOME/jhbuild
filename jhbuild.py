# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2002  James Henstridge
#
#   jhbuild.py: parses command line arguments and starts the build
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

import sys, os, string, getopt

import module
import moduleinfo

if not hasattr(__builtins__, 'True'):
    True = (1 == 1)
    False = (1 != 1)

usage = 'usage: jhbuild [ -f config ] command [ options ... ]'
help = '''Build a set of CVS modules (such as GNOME).

Global options:
  -f, --file=CONFIG            specify an alternative configuration file
      --no-interact            do not prompt for input

Commands:
  update                       update from cvs
  build [ opts... ] [modules]  update and compile (the default)
  buildone [ opts... ] modules build a single module
  run program [ args... ]      run a command in the build environment
  shell                        start a shell in the build environment
  bootstrap                    build required support tools.
  list [ opts ... ] [modules]  list what modules would be built
  dot [modules]                output a dot file of dependencies suitable
                               for processing with graphviz.

Options for the build/buildone commands:
  -a, --autogen                Always run autogen.sh
  -c, --clean                  run make clean before make
  -n, --no-network             skip cvs update
  -s, --skip=MODULES           treat the given modules (and deps) as up to date
  -t, --start-at=MODULE        start building at the given module
''' # for xemacs/jed "

default_config = {
    'cvsroot': ':pserver:anonymous@anoncvs.gnome.org:/cvs/gnome',
    'moduleset': 'head',
    'modules': 'all',
    'checkoutroot': os.path.join(os.environ['HOME'], 'cvs', 'gnome2'),
    'prefix': '/opt/gtk2',
    'autogenargs': '',
    'cflags': None,
    'makeargs': '',
    'installprog': None,
    'skip': [],
}

def read_config_file(file=os.path.join(os.environ['HOME'], '.jhbuildrc')):
    config = default_config.copy()
    try:
	execfile(file, config)
    except IOError:
	raise SystemExit, 'Please create ' + file
    return config

def do_update(config, args, interact=1):
    if args:
        raise getopt.error, 'no extra arguments expected'

    module_set = getattr(moduleinfo, config['moduleset'])
    if config['modules'] == 'all':
        module_list = module_set.get_full_module_list(config['skip'])
    else:
        module_list = module_set.get_module_list(config['modules'],
                                                 config['skip'])

    # don't actually perform build ...
    config['nobuild'] = True
    config['nonetwork'] = False

    build = module.BuildScript(config, module_list=module_list)
    build.build()

def do_build(config, args, interact=1, cvsupdate=1):
    opts, args = getopt.getopt(args, 'acns:t:',
                               ['autogen', 'clean', 'no-network', 'skip=',
                                'start-at='])

    clean = False
    startat = None
    for opt, arg in opts:
        if opt in ('-a', '--autogen'):
            config['alwaysautogen'] = True
        elif opt in ('-c', '--clean'):
            clean = True
        elif opt in ('-n', '--no-network'):
            config['nonetwork'] = True
        elif opt in ('-s', '--skip'):
            config['skip'] = config.get('skip', []) + string.split(arg, ',')
        elif opt in ('-t', '--start-at'):
            startat = arg
    module_set = getattr(moduleinfo, config['moduleset'])
    if args:
        module_list = module_set.get_module_list(args, config['skip'])
    elif config['modules'] == 'all':
        module_list = module_set.get_full_module_list(config['skip'])
    else:
        module_list = module_set.get_module_list(config['modules'],
                                                 config['skip'])

    # remove modules up to startat
    if startat:
        while module_list[0].name != startat:
            del module_list[0]

    build = module.BuildScript(config, module_list=module_list)
    build.build()

def do_build_one(config, args, interact=1):
    opts, args = getopt.getopt(args, 'acn', ['autogen', 'clean', 'no-network'])

    clean = 0
    for opt, arg in opts:
        if opt in ('-a', '--autogen'):
            config['alwaysautogen'] = True
        elif opt in ('-c', '--clean'):
            clean = 1
        elif opt in ('-n', '--no-network'):
            config['nonetwork'] = True

    module_set = getattr(moduleinfo, config['moduleset'])
    module_list = [ module_set.modules[modname] for modname in args ]
	
    build = module.BuildScript(config, module_list=module_list)
    build.build()

def do_run(config, args, interact=1):
    # os.execlp(args[0], *args) # not python 1.5 compatible :(
    apply(os.execlp, [args[0]] + args)

def do_shell(config, args, interact=1):
    os.system(module.user_shell)

def do_bootstrap(config, args, interact=1):
    if args:
        raise getopt.error, 'no extra arguments expected'

    import bootstrap
    bootstrap.build_bootstraps(config)

def do_list(config, args, interact=1):
    opts, args = getopt.getopt(args, 's:', ['skip='])
    for opt, arg in opts:
        if opt in ('-s', '--skip'):
            config['skip'] = config.get('skip', []) + string.split(arg, ',')
    module_set = getattr(moduleinfo, config['moduleset'])
    if args:
        module_list = module_set.get_module_list(args, config['skip'])
    elif config['modules'] == 'all':
        module_list = module_set.get_full_module_list(config['skip'])
    else:
        module_list = module_set.get_module_list(config['modules'],
                                                 config['skip'])

    for module in module_list:
        print module.name

def do_dot(config, args, interact=1):
    module_set = getattr(moduleinfo, config['moduleset'])
    if args:
        modules = args
    elif config['modules'] == 'all':
        modules = None
    else:
        modules = config['modules']
    module_set.write_dot(modules)

commands = {
    'update':    do_update,
    'build':     do_build,
    'buildone':  do_build_one,
    'run':       do_run,
    'shell':     do_shell,
    'bootstrap': do_bootstrap,
    'list':      do_list,
    'dot':       do_dot,
}

def setup_env(config):
    '''set environment variables for using prefix'''

    def addpath(envvar, path):
        try:
            envval = os.environ[envvar]
            if string.find(envval, path) < 0:
                envval = path + ':' + envval
        except KeyError:
            envval = path
        os.environ[envvar] = envval

    prefix = config['prefix']
    if not os.path.exists(prefix):
	try:
	    os.mkdir(prefix)
	except:
	    raise "Can't create %s directory" % prefix
	        
    #includedir = os.path.join(prefix, 'include')
    #addpath('C_INCLUDE_PATH', includedir)
    libdir = os.path.join(prefix, 'lib')
    addpath('LD_LIBRARY_PATH', libdir)
    bindir = os.path.join(prefix, 'bin')
    addpath('PATH', bindir)
    pkgconfigdir = os.path.join(libdir, 'pkgconfig')
    addpath('PKG_CONFIG_PATH', pkgconfigdir)
    aclocaldir = os.path.join(prefix, 'share', 'aclocal')
    if not os.path.exists(aclocaldir):
	os.mkdir(os.path.split(aclocaldir)[0])
	os.mkdir(aclocaldir)
    
    try:
        val = os.environ['ACLOCAL_FLAGS']
        os.environ['ACLOCAL_FLAGS'] = '%s -I %s' % (val, aclocaldir)
    except KeyError:
	os.environ['ACLOCAL_FLAGS'] = '-I %s' % aclocaldir
    os.environ['ACLOCAL_AMFLAGS'] = os.environ['ACLOCAL_FLAGS']
    os.environ['CERTIFIED_GNOMIE'] = 'yes'

    installprog = config['installprog']
    if installprog:
        os.environ['INSTALL'] = installprog

    cflags = config['cflags']
    if cflags:
        os.environ['CFLAGS'] = cflags

    # get rid of gdkxft from the env -- it can cause problems.
    if os.environ.has_key('LD_PRELOAD'):
        valarr = string.split(os.environ['LD_PRELOAD'], ' ')
        for x in valarr[:]:
            if string.find(x, 'libgdkxft.so') >= 0:
                valarr.remove(x)
        os.environ['LD_PRELOAD'] = string.join(valarr, ' ')

def main(args):
    try:
        opts, args = getopt.getopt(args, 'f:',
                                   ['file=', 'no-interact', 'help'])
    except getopt.error, exc:
        sys.stderr.write('jhbuild: %s\n' % str(exc))
        sys.stderr.write(usage + '\n')
        sys.exit(1)


    interact = 1
    configfile=os.path.join(os.environ['HOME'], '.jhbuildrc')

    for opt, arg in opts:
        if opt == '--help':
            print usage
            print help
            sys.exit(0)
        elif opt in ('-f', '--file'):
            configfile = arg
        elif opt == '--no-interact':
            interact = 0

    config = read_config_file(configfile)

    setup_env(config)

    if not args or args[0][0] == '-':
        command = 'build' # default to cvs update + compile
    else:
        command = args[0]
        args = args[1:]

    try:
        cmd = commands[command]
    except KeyError:
        sys.stderr.write('jhbuild: unsupported command %s\n' % command)
        sys.stderr.write(usage + '\n')
        sys.exit(1)

    try:
        cmd(config, args, interact)
    except getopt.error, exc:
        sys.stderr.write('jhbuild %s: %s\n' % (command, exc))
        sys.stderr.write(usage + '\n')
        sys.exit(1)
    except KeyboardInterrupt:
        print "Interrupted"
        sys.exit(1)
    except EOFError:
        print "EOF"
        sys.exit(1)

if __name__ == '__main__':
    main(sys.argv[1:])
