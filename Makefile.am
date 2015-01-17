SUBDIRS = po examples scripts triggers jhbuild buildbot

if DOC_INSTALLATION_ENABLED
SUBDIRS += doc
endif

PATCHES = $(wildcard $(top_srcdir)/patches/*.patch)
MODULESETS = $(wildcard $(top_srcdir)/modulesets/*.modules)
DTDS = \
	modulesets/moduleset.dtd \
	modulesets/moduleset.rnc \
	$(NULL)

desktopdir = $(datadir)/applications
desktop_in_files = jhbuild.desktop.in
desktop_DATA = $(desktop_in_files:.desktop.in=.desktop)

@INTLTOOL_DESKTOP_RULE@

INTLTOOL = 			\
	intltool-extract.in 	\
	intltool-merge.in 	\
	intltool-update.in

EXTRA_DIST = $(PATCHES) $(MODULESETS) $(DTDS) \
	modulesets/moduleset.xsl \
	install-check.c \
	autogen.sh \
	$(desktop_in_files) $(INTLTOOL)

DISTCLEANFILES = 		\
	intltool-extract 	\
	intltool-merge 		\
	intltool-update

CLEANFILES = \
	$(desktop_DATA)

bin_PROGRAMS = install-check

install_check_SOURCES = install-check.c


install-exec-local:
	$(srcdir)/scripts/debian-python2-postinstall-hook.sh $(DESTDIR)$(bindir)

# Check the modulesets for validity.
# This is a lower-level check than `jhbuild checkmodulesets` (which analyses the
# module graph), and doesn't require jhbuild to be built and installed.
#
# This will fail if xmllint isn't installed.
check-modulesets:
	xmllint --noout --dtdvalid $(srcdir)/modulesets/moduleset.dtd $(MODULESETS)
.PHONY: check-modulesets

check: check-modulesets
.PHONY: check
