#!/bin/sh
# This awful bit of code is intended to ensure that
# modules we build with jhbuild can always use "python2"
# to find Python 2, even if the host system (e.g. Debian)
# doesn't have such a symbolic link.
#
# See: https://mail.gnome.org/archives/desktop-devel-list/2012-November/msg00011.html

set -e

bindir=$1
test -n "$bindir" || (echo "usage: $0 bindir"; exit 1)

py2=$(which python2 2>/dev/null || true)
if test -z "$py2"; then
    py=$(which python 2>/dev/null);
    ln -s "$(which python)" ${bindir}/python2;
fi
