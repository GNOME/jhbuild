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

# Build _static/languageLoader.js from template adding language codes
def setup_languageloader(l: list):
    from string import Template
    from pathlib import Path

    HERE = Path(__file__).resolve().parent
    with open(
        HERE / '_templates' / 'languageLoader.js'
    ) as languageloader_template_file:
        template = Template(languageloader_template_file.read())
    languageloader_path = HERE / '_static' / 'languageLoader.js'
    languageloader_path.write_text(
        template.safe_substitute({"LANGUAGES": languages})
    )
setup_languageloader(languages)