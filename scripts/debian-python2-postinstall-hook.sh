#!/bin/sh
# This awful bit of code is intended to ensure that
# modules we build with jhbuild can always use "python2"
# to find Python 2, even if the host system (e.g. Debian)
# doesn't have such a symbolic link.
#
# See: https://mail.gnome.org/archives/desktop-devel-list/2012-November/msg00011.html

set -e

BINDIR=$1
DEST="$BINDIR/python2"
PYTHON=$(which python 2>/dev/null || true);

die() { echo "$1" >&2 ; exit 2; }

test -n "$BINDIR" || die "Usage: $0 BINDIR"
test -d "$BINDIR" || die "$0: '$BINDIR' is not a directory"

which python2 2>/dev/null && exit 0 # 'python2' is already on PATH

test -x "$PYTHON" || die "$0: Unable to find 'python' in the PATH"

ln -sf "$PYTHON" "$DEST"
