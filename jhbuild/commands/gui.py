import getopt
from jhbuild.commands.base import register_command
import jhbuild.frontends
from jhbuild.frontends.gtkui import Configuration

def do_gui(config, args):
    # request GTK build script.
    config.buildscript = 'gtkui'
    
    configuration = Configuration(config, args)
    (module_list, start_at,
     run_autogen, cvs_update, no_build) = configuration.run()

    if start_at:
        while module_list and module_list[0].name != start_at:
            del module_list[0]
 
    if run_autogen:
        config.alwaysautogen = True
    elif not cvs_update:
        config.nonetwork = True

    if no_build:
        config.nobuild = True
        
    if module_list != None:
        build = jhbuild.frontends.get_buildscript(config, module_list)
        build.build()

register_command('gui', do_gui)
