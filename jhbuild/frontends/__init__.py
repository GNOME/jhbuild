import sys

def get_buildscript(config, module_list):
    modname = 'jhbuild.frontends.%s' % config.buildscript
    __import__(modname)
    BuildScript = sys.modules[modname].BUILD_SCRIPT
    return BuildScript(config, module_list)
