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
  compile [ options ... ]      compile checked out modules
  build [ options ... ]        update and compile (the default)
  run program [ args ... ]     run a command in the build environment

Options for the compile/build commands:
  -a, --autogen                Always run autogen.sh
  -c, --clean                  run make clean before make
  -s, --skip=MODULES           treat the given modules as up to date
'''

default_config = {
    'cvsroot': ':pserver:anonymous@anoncvs.gnome.org:/cvs/gnome',
    'moduleset': 'head',
    'modules': 'all',
    'checkoutroot': os.path.join(os.environ['HOME'], 'cvs', 'gnome2'),
    'prefix': '/opt/gtk2',
    'autogenargs': '',
    'installprog': None,
}

def read_config_file(file=os.path.join(os.environ['HOME'], '.jhbuildrc')):
    config = default_config.copy()
    execfile(file, config)
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
                               checkoutroot=config['checkoutroot'],
                               installprog=config['installprog'])
    build.build(cvsupdate=1, nobuild=1, interact=interact)

def do_compile(config, args, interact=1, cvsupdate=0):
    opts, args = getopt.getopt(args, 'acs:', ['autogen', 'clean', 'skip='])

    autogen = 0
    clean = 0
    skip = ()
    for opt, arg in opts:
        if opt in ('-a', '--autogen'):
            autogen = 1
        if opt in ('-c', '--clean'):
            clean = 1
        elif opt in ('-s', '--skip'):
            skip = string.split(arg, ',')
    if args:
        raise getopt.error, 'no non option arguments expected'

    module_set = getattr(moduleinfo, config['moduleset'])
    if config['modules'] == 'all':
        module_list = module_set.get_full_module_list()
    else:
        module_list = module_set.get_module_list(config['modules'])

    build = module.BuildScript(cvsroot=config['cvsroot'],
                               modulelist=module_list,
                               autogenargs=config['autogenargs'],
                               prefix=config['prefix'],
                               checkoutroot=config['checkoutroot'],
                               installprog=config['installprog'])
    build.build(cvsupdate=cvsupdate, alwaysautogen=autogen, makeclean=clean,
                skip=skip, interact=interact)

def do_build(config, args, interact=1):
    do_compile(config, args, interact, cvsupdate=1)

def do_run(config, args, interact=1):
    # do this to set up environment
    build = module.BuildScript(cvsroot=config['cvsroot'],
                               modulelist=[],
                               autogenargs=config['autogenargs'],
                               prefix=config['prefix'],
                               checkoutroot=config['checkoutroot'],
                               installprog=config['installprog'])

    # os.execlp(args[0], *args) # not python 1.5 compatible :(
    apply(os.execlp, [args[0]] + args)

commands = {
    'update':  do_update,
    'compile': do_compile,
    'build':   do_build,
    'run':     do_run,
}

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

    if not args or args[0][0] == '-':
        command = 'build' # default to cvs update + compile
    else:
        command = args[0]
        args = args[1:]

    try:
        commands[command](config, args, interact)
    except KeyError:
        sys.stderr.write('jhbuild: unsupported command %s\n' % command)
        sys.stderr.write(usage + '\n')
        sys.exit(1)
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
