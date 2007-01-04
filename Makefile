PACKAGE = jhbuild
VERSION = 0.1

CC = gcc
CFLAGS = -Wall -O2

bindir=$(HOME)/bin
desktopdir=$(HOME)/.local/share/applications

all: install-check
	@echo 'Run "make install" to install.'

install-check: install-check.c
	$(CC) $(CFLAGS) -o install-check install-check.c

update:
	svn update --quiet

install: install-check
	@echo "Creating $(bindir)/jhbuild"
	@mkdir -p $(bindir)
	@sed "s,@jhbuilddir@,`pwd`,g" < jhbuild.in > $(bindir)/jhbuild
	@chmod a+x $(bindir)/jhbuild

	@echo "Creating $(desktopdir)/jhbuild.desktop"
	@mkdir -p $(desktopdir)
	@cp jhbuild.desktop $(desktopdir)
	@echo "Exec=$(bindir)/jhbuild gui" >> $(desktopdir)/jhbuild.desktop

	@[ -f $(HOME)/.jhbuildrc ]||echo "Don't forget to create ~/.jhbuildrc"
	install -m755 install-check $(bindir)/install-check

distdir = $(PACKAGE)-$(VERSION)
dist:
	-rm -rf $(distdir)
	mkdir $(distdir)
	cp -p README COPYING ChangeLog Makefile jhbuild.in jhbuild.desktop $(distdir)/
	cp -p *.c *.jhbuildrc $(distdir)/
	mkdir $(distdir)/modulesets
	cp -p modulesets/*.modules $(distdir)/modulesets/
	cp -p modulesets/moduleset.dtd modulesets/moduleset.xsl $(distdir)/modulesets/
	mkdir $(distdir)/patches
	cp -p patches/*.patch $(distdir)/patches/
	mkdir $(distdir)/jhbuild
	cp -p jhbuild/*.py jhbuild/defaults.jhbuildrc $(distdir)/jhbuild/
	mkdir $(distdir)/jhbuild/commands
	cp -p jhbuild/commands/*.py $(distdir)/jhbuild/commands/
	mkdir $(distdir)/jhbuild/frontends
	cp -p jhbuild/frontends/*.py $(distdir)/jhbuild/frontends/
	cp -p jhbuild/frontends/jhbuild.glade $(distdir)/jhbuild/frontends/
	mkdir $(distdir)/jhbuild/modtypes
	cp -p jhbuild/modtypes/*.py $(distdir)/jhbuild/modtypes/
	mkdir $(distdir)/jhbuild/utils
	cp -p jhbuild/utils/*.py $(distdir)/jhbuild/utils/
	mkdir $(distdir)/scripts
	cp -p scripts/*.py scripts/*.xsl scripts/*.deps scripts/*.exceptions $(distdir)/scripts/
	mkdir $(distdir)/scripts/branch-violations
	cp -p scripts/branch-violations/README scripts/branch-violations/find-branch-* \
		$(distdir)/scripts/branch-violations/
	chmod -R a+r $(distdir)
	tar czf $(distdir).tar.gz $(distdir)
	rm -rf $(distdir)

.PHONY: all update install
