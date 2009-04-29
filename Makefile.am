SUBDIRS = po

if DOC_INSTALLATION_ENABLED
SUBDIRS += doc
endif


PATCHES = $(wildcard $(top_srcdir)/patches/*.patch)
SOURCES = $(shell find $(top_srcdir)/jhbuild/ -name '*.py' -or -name '*.glade') jhbuild/defaults.jhbuildrc
MODULE_SETS = $(wildcard $(top_srcdir)/modulesets/*.modules) modulesets/moduleset.dtd

INTLTOOL = 			\
	intltool-extract.in 	\
	intltool-merge.in 	\
	intltool-update.in

EXTRA_DIST = gnome-doc-utils.make $(PATCHES) $(SOURCES) $(MODULE_SETS) \
	scripts/hg-update.py Makefile.plain install-check.c \
	po/Makefile.plain $(INTLTOOL)

DISTCLEANFILES = 		\
	intltool-extract 	\
	intltool-merge 		\
	intltool-update

# those won't be executed by make distcheck, it is necessary as they build
# in source tree and do install to ~/bin/
all-local:
	test z"$(srcdir)" = z"." && $(MAKE) -f Makefile.plain || true

install-exec-local:
	test z"$(srcdir)" = z"." && \
		$(MAKE) -f Makefile.plain install \
			bindir="$(bindir)" \
			datarootdir="$(datarootdir)"

