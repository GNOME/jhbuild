SUBDIRS = commands frontends modtypes utils versioncontrol

appdir = $(pythondir)/jhbuild/

app_PYTHON = \
	__init__.py  \
	config.py \
	defaults.jhbuildrc \
	environment.py \
	errors.py \
	main.py  \
	moduleset.py \
	monkeypatch.py

sitecustomizedir = $(pkgdatadir)/sitecustomize
sitecustomize_DATA = sitecustomize/sitecustomize.py

EXTRA_DIST = $(sitecustomize_DATA)
