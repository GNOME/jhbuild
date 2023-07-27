project('jhbuild',
  meson_version: '>= 0.64.0',
)

py =  import('python').find_installation(pure: true)

pkgdatadir = get_option('datadir') / 'jhbuild'
pkgexecdir = get_option('libexecdir') / 'jhbuild'

install_subdir('jhbuild', install_dir: py.get_path('purelib'))
install_data('scripts/hg-update.py', install_dir: pkgexecdir, install_mode: 'rwxr-xr-x')
install_subdir('patches', install_dir: pkgdatadir)
install_subdir('modulesets', install_dir: pkgdatadir)
install_subdir('triggers', install_dir: pkgdatadir)

bash_completion = dependency('bash-completion', required: false)
if bash_completion.found()
  install_data('contrib/jhbuild_completion.bash',
    rename: ['jhbuild'],
    install_dir: bash_completion.get_variable(pkgconfig: 'completionsdir')
  )
endif

configure_file(
    input: 'scripts/jhbuild.in',
    output: 'jhbuild',
    configuration: {
        'pkgdatadir': get_option('prefix') / pkgdatadir,
    },
    install: true,
    install_dir: get_option('bindir'),
)

# TODO: Translations