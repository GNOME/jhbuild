import getopt
from jhbuild.commands.base import register_command
import jhbuild.frontends

def do_tinderbox(config, args):
    config.buildscript = 'tinderbox'

    opts, args = getopt.getopt(args, 'o:', ['output='])
    for opt, arg in opts:
        if opt in ('-o', '--output'):
            config.tinderbox_outputdir = arg

    module_set = jhbuild.moduleset.load(config)
    if args:
        module_list = module_set.get_module_list(args, config.skip)
    elif config.modules == 'all':
        module_list = module_set.get_full_module_list(config.skip)
    else:
        module_list = module_set.get_module_list(config.modules,
                                                 config.skip)

    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('tinderbox', do_tinderbox)
