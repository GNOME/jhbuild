import sys, os, string, getopt

import module
import moduleinfo

usage = 'usage: jhbuild [ -f config ] command [ options ... ]'
help = '''Build a set of CVS modules (such as GNOME).

Global options:
  -f, --file=CONFIG            specify an alternative configuration file
      --no-interact            do not prompt for input

Commands:
  update                       update from cvs
  build [ options ... ]        update and compile (the default)
  buildone module              build a single module
  run program [ args ... ]     run a command in the build environment
  shell                        start a shell in the build environment
  bootstrap                    build required support tools.

Options for the build/buildone commands:
  -a, --autogen                Always run autogen.sh
  -c, --clean                  run make clean before make
  -n, --no-cvs                 skip cvs update
  -s, --skip=MODULES           treat the given modules (and deps) as up to date
''' # for xemacs/jed "

default_config = {
    'cvsroot': ':pserver:anonymous@anoncvs.gnome.org:/cvs/gnome',
    'moduleset': 'head',
    'modules': 'all',
    'checkoutroot': os.path.join(os.environ['HOME'], 'cvs', 'gnome2'),
    'prefix': '/opt/gtk2',
    'autogenargs': '',
    'cflags': None,
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
        module_list = module_set.get_full_module_list()
    else:
        module_list = module_set.get_module_list(config['modules'])
	
    build = module.BuildScript(cvsroot=config['cvsroot'],
                               modulelist=module_list,
                               autogenargs=config['autogenargs'],
                               prefix=config['prefix'],
                               checkoutroot=config['checkoutroot'])
    build.build(cvsupdate=1, nobuild=1, interact=interact)

def do_build(config, args, interact=1, cvsupdate=1):
    opts, args = getopt.getopt(args, 'acns:',
                               ['autogen', 'clean', 'no-cvs', 'skip='])

    autogen = 0
    clean = 0
    skip = config['skip']
    for opt, arg in opts:
        if opt in ('-a', '--autogen'):
            autogen = 1
        elif opt in ('-c', '--clean'):
            clean = 1
        elif opt in ('-n', '--no-cvs'):
            cvsupdate = 0
        elif opt in ('-s', '--skip'):
            skip = skip + string.split(arg, ',')

    module_set = getattr(moduleinfo, config['moduleset'])
    if args:
        module_list = module_set.get_module_list(args)
    elif config['modules'] == 'all':
        module_list = module_set.get_full_module_list()
    else:
        module_list = module_set.get_module_list(config['modules'])

    # expand the skip list to include the dependencies
    skip = map(lambda mod: mod.name, module_set.get_module_list(skip))

    build = module.BuildScript(cvsroot=config['cvsroot'],
                               modulelist=module_list,
                               autogenargs=config['autogenargs'],
                               prefix=config['prefix'],
                               checkoutroot=config['checkoutroot'])
    build.build(cvsupdate=cvsupdate, alwaysautogen=autogen, makeclean=clean,
                skip=skip, interact=interact)

def do_build_one(config, args, interact=1):
    opts, args = getopt.getopt(args, 'acn', ['autogen', 'clean', 'no-cvs'])

    autogen = 0
    clean = 0
    cvsupdate = 1
    for opt, arg in opts:
        if opt in ('-a', '--autogen'):
            autogen = 1
        elif opt in ('-c', '--clean'):
            clean = 1
        elif opt in ('-n', '--no-cvs'):
            cvsupdate = 0
    if len(args) != 1:
        raise getopt.error, 'only expecting one non option arg'

    mod = args[0]

    module_set = getattr(moduleinfo, config['moduleset'])
    module_list = [module_set.modules[mod]]
	
    build = module.BuildScript(cvsroot=config['cvsroot'],
                               modulelist=module_list,
                               autogenargs=config['autogenargs'],
                               prefix=config['prefix'],
                               checkoutroot=config['checkoutroot'])
    build.build(cvsupdate=cvsupdate, alwaysautogen=autogen, makeclean=clean,
                interact=interact)

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

commands = {
    'update':    do_update,
    'build':     do_build,
    'buildone':  do_build_one,
    'run':       do_run,
    'shell':     do_shell,
    'bootstrap': do_bootstrap,
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
	        
    includedir = os.path.join(prefix, 'include')
    addpath('C_INCLUDE_PATH', includedir)
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
