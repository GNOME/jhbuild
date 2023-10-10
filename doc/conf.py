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

    # FIXME: Must keep in sync with languageLoader.js
    'languages': [
        'en',
        'cs',
        'de',
        'el',
        'es',
        'fr',
        'ja',
        'ko',
        'pt_BR',
        'ru',
        'sl',
        'sv',
        'zh_CN',
    ],
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
