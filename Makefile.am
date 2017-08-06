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

if GUI_ENABLED
desktopdir = $(datadir)/applications
desktop_DATA = jhbuild.desktop

jhbuild.desktop.in: jhbuild.desktop.in.in
	$(AM_V_GEN) $(MSGFMT) --desktop --template $< -d $(top_srcdir)/po -o $@

# Substitute variables in a Desktop Entry file.
jhbuild.desktop: jhbuild.desktop.in
	$(AM_V_GEN) sed -e 's|@bindir[@]|$(bindir)|g' $< > $@
endif

EXTRA_DIST = $(PATCHES) $(MODULESETS) $(DTDS) \
	modulesets/moduleset.xsl \
	autogen.sh \
	jhbuild.desktop.in.in jhbuild.desktop.in

CLEANFILES = \
	$(desktop_DATA)

MAINTAINERCLEANFILES = \
	jhbuild.desktop.in

install-exec-local:
	$(srcdir)/scripts/debian-python2-postinstall-hook.sh $(DESTDIR)$(bindir)

# Check the modulesets for validity.
# This is a lower-level check than `jhbuild checkmodulesets` (which analyses the
# module graph), and doesn't require jhbuild to be built and installed.
#
# This will fail if xmllint or trang isn't installed.
check-modulesets:
	xmllint --noout --dtdvalid $(srcdir)/modulesets/moduleset.dtd $(MODULESETS)
	trang $(srcdir)/modulesets/moduleset.rnc $(builddir)/moduleset.rng
	xmllint --noout --relaxng $(builddir)/moduleset.rng $(MODULESETS)
	rm -f $(builddir)/moduleset.rng
.PHONY: check-modulesets

check: check-modulesets
.PHONY: check
