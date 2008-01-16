SUBDIRS = doc

PATCHES = $(shell ls patches/*.patch)
SOURCES = $(shell find jhbuild/ -name *.py) jhbuild/defaults.jhbuildrc
MODULE_SETS = $(shell ls modulesets/*.modules) modulesets/moduleset.dtd

EXTRA_DIST = gnome-doc-utils.make $(PATCHES) $(SOURCES) $(MODULE_SETS) \
	scripts/hg-update.py Makefile.plain

all-local:
	$(MAKE) -f Makefile.plain

install-exec-local:
	$(MAKE) -f Makefile.plain install

