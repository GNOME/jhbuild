
import os
import getopt
import jhbuild.moduleset
import jhbuild.frontends

__all__ = [ 'register_command', 'run' ]

# handle registration of new commands
_commands = {}
def register_command(name, function):
    _commands[name] = function
def run(command, config, args):
    # if the command hasn't been registered, load a module by the same name
    if not _commands.has_key(command):
        __import__('jhbuild.commands.%s' % command)
    if not _commands.has_key(command):
        raise RuntimeError('command not found')

    func = _commands[command]
    return func(config, args)

# standard commands:
def do_update(config, args):
    opts, args = getopt.getopt(args, 's:t:', ['skip=', 'start-at='])

    startat = None
    for opt, arg in opts:
        if opt in ('-s', '--skip'):
            config.skip = config.skip + string.split(arg, ',')
        elif opt in ('-t', '--start-at'):
            startat = arg

    module_set = jhbuild.moduleset.load(config)
    if args:
        module_list = module_set.get_module_list(args, config.skip)
    elif config.modules == 'all':
        module_list = module_set.get_full_module_list(config.skip)
    else:
        module_list = module_set.get_module_list(config.modules,
                                                 config.skip)

    # remove modules up to startat
    if startat:
        while module_list and module_list[0].name != startat:
            del module_list[0]

    # don't actually perform build ...
    config.nobuild = True
    config.nonetwork = False

    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('update', do_update)

def do_update_one(config, args):
    opts, args = getopt.getopt(args, '', [])

    module_set = jhbuild.moduleset.load(config)
    try:
        module_list = [ module_set.modules[modname] for modname in args ]
    except KeyError:
        raise SystemExit, "A module called '%s' could not be found." % modname
	
    # don't actually perform build ...
    config.nobuild = True
    config.nonetwork = False

    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('updateone', do_update_one)

def do_build(config, args):
    opts, args = getopt.getopt(args, 'acns:t:',
                               ['autogen', 'clean', 'no-network', 'skip=',
                                'start-at='])

    startat = None
    for opt, arg in opts:
        if opt in ('-a', '--autogen'):
            config.alwaysautogen = True
        elif opt in ('-c', '--clean'):
            config.makeclean = True
        elif opt in ('-n', '--no-network'):
            config.nonetwork = True
        elif opt in ('-s', '--skip'):
            config.skip = config.skip + string.split(arg, ',')
        elif opt in ('-t', '--start-at'):
            startat = arg
    module_set = jhbuild.moduleset.load(config)
    if args:
        module_list = module_set.get_module_list(args, config.skip)
    elif config.modules == 'all':
        module_list = module_set.get_full_module_list(config.skip)
    else:
        module_list = module_set.get_module_list(config.modules,
                                                 config.skip)

    # remove modules up to startat
    if startat:
        while module_list and module_list[0].name != startat:
            del module_list[0]

    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('build', do_build)

def do_build_one(config, args):
    opts, args = getopt.getopt(args, 'acn', ['autogen', 'clean', 'no-network'])

    for opt, arg in opts:
        if opt in ('-a', '--autogen'):
            config.alwaysautogen = True
        elif opt in ('-c', '--clean'):
            config.makeclean = True
        elif opt in ('-n', '--no-network'):
            config.nonetwork = True

    module_set = jhbuild.moduleset.load(config)
    try:
        module_list = [ module_set.modules[modname] for modname in args ]
    except KeyError:
        raise SystemExit, "A module called '%s' could not be found." % modname
	
    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('buildone', do_build_one)

def do_run(config, args):
    os.execlp(args[0], *args)
register_command('run', do_run)

def do_shell(config, args):
    os.execlp(module.user_shell, module.user_shell)
register_command('shell', do_shell)

def do_list(config, args):
    opts, args = getopt.getopt(args, 's:', ['skip='])
    for opt, arg in opts:
        if opt in ('-s', '--skip'):
            config.skip = config.skip + string.split(arg, ',')
    module_set = jhbuild.moduleset.load(config)
    if args:
        module_list = module_set.get_module_list(args, config.skip)
    elif config.modules == 'all':
        module_list = module_set.get_full_module_list(config.skip)
    else:
        module_list = module_set.get_module_list(config.modules,
                                                 config.skip)

    for mod in module_list:
        print mod.name
register_command('list', do_list)

def do_dot(config, args):
    module_set = jhbuild.moduleset.load(config)
    if args:
        modules = args
    elif config.modules == 'all':
        modules = None
    else:
        modules = config.modules
    module_set.write_dot(modules)
register_command('dot', do_dot)
