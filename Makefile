
all:
	@echo 'Run "make install" to install.'

update:
	cvs -z3 -q update -Pd .

bindir=$(HOME)/bin

install:
	@echo "Creating $(bindir)/jhbuild"
	@mkdir -p $(bindir)
	@echo '#!/bin/sh' > $(bindir)/jhbuild
	@echo 'python '`pwd`'/jhbuild.py "$$@"' >> $(bindir)/jhbuild
	@chmod a+x $(bindir)/jhbuild
	@[ -f $(HOME)/.jhbuildrc ]||echo "Don't forget to create ~/.jhbuildrc"

.PHONY: all update install
