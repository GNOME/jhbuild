CC = gcc
CFLAGS = -Wall -O2

bindir=$(HOME)/bin

all: install-check
	@echo 'Run "make install" to install.'

install-check: install-check.c
	$(CC) $(CFLAGS) -o install-check install-check.c

update:
	cvs -z3 -q update -Pd .

install: install-check
	@echo "Creating $(bindir)/jhbuild"
	@mkdir -p $(bindir)
	@echo '#!/bin/sh' > $(bindir)/jhbuild
	@echo 'python '`pwd`'/jhbuild.py "$$@"' >> $(bindir)/jhbuild
	@chmod a+x $(bindir)/jhbuild
	@[ -f $(HOME)/.jhbuildrc ]||echo "Don't forget to create ~/.jhbuildrc"
	install -m755 install-check $(bindir)/install-check

dist:
	ln -sf . jhbuild
	tar czf jhbuild.tar.gz jhbuild/Makefile jhbuild/COPYING \
	  jhbuild/README jhbuild/ChangeLog jhbuild/*.py jhbuild/*.c \
	  jhbuild/*.patch jhbuild/*.jhbuildrc
	rm -f jhbuild

.PHONY: all update install
