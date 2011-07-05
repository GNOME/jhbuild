SUBDIRS = po scripts triggers jhbuild buildbot

if DOC_INSTALLATION_ENABLED
SUBDIRS += doc
endif

PATCHES = $(wildcard $(top_srcdir)/patches/*.patch)
MODULESETS = $(wildcard $(top_srcdir)/modulesets/*.modules) modulesets/moduleset.dtd

desktopdir = $(datadir)/applications
desktop_in_files = jhbuild.desktop.in
desktop_DATA = $(desktop_in_files:.desktop.in=.desktop)

@INTLTOOL_DESKTOP_RULE@

INTLTOOL = 			\
	intltool-extract.in 	\
	intltool-merge.in 	\
	intltool-update.in

EXTRA_DIST = gnome-doc-utils.make $(PATCHES) $(MODULESETS) \
	install-check.c \
	$(desktop_in_files) $(INTLTOOL)

DISTCLEANFILES = 		\
	intltool-extract 	\
	intltool-merge 		\
	intltool-update

CLEANFILES = \
	$(desktop_DATA)

bin_PROGRAMS = install-check

install_check_SOURCES = install-check.c

