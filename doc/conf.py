project = 'JHBuild'
copyright = '2023, JHBuild Contributors'
author = 'James Henstridge'

extensions = [
    'sphinx_rtd_theme',
]

with open('po/LINGUAS') as f:
    languages = ([s.strip('\n') for s in f.readlines()])
languages.append('en')
languages.sort()

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

    # FIXME: Must keep in sync with languageLoader.js
    'languages': languages,
}
html_theme_options = {
}
html_js_files = [
    'languageLoader.js',
]

templates_path = ['_templates']
exclude_patterns = []
language = 'en'
locale_dirs = ['po']
gettext_compact = 'docs'
