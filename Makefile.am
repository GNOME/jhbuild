SUBDIRS = po scripts jhbuild

if DOC_INSTALLATION_ENABLED
SUBDIRS += doc
endif

PATCHES = $(wildcard $(top_srcdir)/patches/*.patch)
MODULESETS = $(wildcard $(top_srcdir)/modulesets/*.modules) modulesets/moduleset.dtd


INTLTOOL = 			\
	intltool-extract.in 	\
	intltool-merge.in 	\
	intltool-update.in

EXTRA_DIST = gnome-doc-utils.make $(PATCHES) $(MODULESETS) \
	install-check.c \
	jhbuild.desktop $(INTLTOOL)

DISTCLEANFILES = 		\
	intltool-extract 	\
	intltool-merge 		\
	intltool-update

bin_PROGRAMS = install-check

install_check_SOURCES = install-check.c

