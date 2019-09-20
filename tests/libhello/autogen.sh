#!/bin/sh

srcdir=$(dirname "$0")
test -z "$srcdir" && srcdir=. 

libtoolize
aclocal
automake --add-missing
autoconf

exec "$srcdir/configure" "$@"
