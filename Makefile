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

.PHONY: all update install
