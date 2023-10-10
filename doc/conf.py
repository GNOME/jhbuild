project = 'JHBuild'
copyright = '2023, JHBuild Contributors'
author = 'James Henstridge'

extensions = [
    'sphinx_rtd_theme',
]

html_theme = 'sphinx_rtd_theme'
html_baseurl = 'https://gnome.pages.gitlab.gnome.org/jhbuild/'
html_static_path = ['_static']
html_context = {
    'display_gitlab': True,
    'gitlab_host': 'gitlab.gnome.org',
    'gitlab_user': 'GNOME',
    'gitlab_repo': 'jhbuild',
    'gitlab_version': 'master',
    'conf_py_path': '/doc/',
    
}
html_theme_options = {
}

templates_path = ['_templates']
exclude_patterns = []
language = 'en'
locale_dirs = ['po']
gettext_compact = 'docs'
