SUBDIRS = po examples scripts triggers jhbuild doc

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
	README.rst \
	modulesets/moduleset.xsl \
	autogen.sh \
	jhbuild.desktop.in.in jhbuild.desktop.in \
	tests/test_main.py \
	tests/mock.py \
	tests/__init__.py \
	tests/autotools/autogen.sh \
	tests/autotools/configure.in \
	tests/autotools/hello.c \
	tests/autotools/Makefile.am \
	tests/distutils/hello \
	tests/distutils/setup.py \
	tests/hello/autogen.sh \
	tests/hello/configure.in \
	tests/hello/hello-frontend.c \
	tests/hello/Makefile.am \
	tests/libhello/autogen.sh \
	tests/libhello/configure.in \
	tests/libhello/libhello.c \
	tests/libhello/libhello.h \
	tests/libhello/libhello.pc.in \
	tests/libhello/Makefile.am

CLEANFILES = \
	$(desktop_DATA)

MAINTAINERCLEANFILES = \
	jhbuild.desktop.in

DISTCHECK_CONFIGURE_FLAGS = \
	--with-python=$(PYTHON)

check:
	$(PYTHON) -bb -m unittest discover -v -t $(top_srcdir) -s $(top_srcdir)/tests

.PHONY: check
