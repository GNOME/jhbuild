import sys, os, string, getopt

import module
import moduleinfo

usage = 'usage: jhbuild [ -f config ] options ...'
help = '''Build a set of CVS modules (such as GNOME).

  -f, --file=CONFIG            specify an alternative configuration file
  -c, --clean                  clean up modules before builds
  -n, --no-cvs                 skip the cvs update step
  -b, --no-build               only perform the cvs update step
  -u, --uptodate=MOD1,...      assume the named modules are up to date
      --no-interact            do not prompt for input
'''

try:
    opts, args = getopt.getopt(sys.argv[1:], 'ncbf:u:',
                               ['no-cvs', 'clean', 'no-build', 'file=',
                                'uptodate=', 'no-interact', 'help'])
except getopt.error, exc:
    sys.stderr.write('jhbuild: %s\n' % str(exc))
    sys.stderr.write(usage + '\n')
    sys.exit(1)

default_config = {
    'cvsroot': ':pserver:anonymous@anoncvs.gnome.org:/cvs/gnome',
    'moduleset': 'head',
    'modules': 'all',
    'checkoutroot': os.path.join(os.environ['HOME'], 'cvs', 'gnome2'),
    'prefix': '/opt/gtk2',
    'autogenargs': '',
    'installprog': None,
}

cvsupdate = 1
clean = 0
nobuild = 0
interact = 1
uptodate = ()
configfile=os.path.join(os.environ['HOME'], '.jhbuildrc')

for opt, arg in opts:
    if opt == '--help':
        print usage
        print help
        sys.exit(0)
    elif opt in ('-n', '--no-cvs'):
        cvsupdate = 0
    elif opt in ('-c', '--clean'):
        clean=1
    elif opt in ('-b', '--no-build'):
        nobuild=1
    elif opt in ('-f', '--file'):
        configfile = arg
    elif opt in ('-u', '--uptodate'):
        uptodate = string.split(arg, ',')
    elif opt == '--no-interact':
        interact = 0

config = default_config.copy()
execfile(configfile, config)

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

try:
    build.build(cvsupdate=cvsupdate, alwaysautogen=clean, makeclean=clean,
                nobuild=nobuild, skip=uptodate, interact=interact)
except KeyboardInterrupt:
    print "Interrupted"
except EOFError:
    print "EOF"

