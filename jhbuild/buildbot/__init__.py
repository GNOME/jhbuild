import jhbuild.moduleset

def jhbuild_list():
    config = jhbuild.config.Config()
    module_set = jhbuild.moduleset.load(jhbuild_config)
    module_list = module_set.get_module_list(config.modules,
            include_optional_modules=True)
    return [x.name for x in module_list if not x.name.startswith('meta-')]
