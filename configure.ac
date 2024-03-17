AC_INIT([jhbuild],
        [3.38.1],
        [https://gitlab.gnome.org/GNOME/jhbuild/-/issues/],
        [jhbuild])

AC_CONFIG_SRCDIR(jhbuild/main.py)
AC_PREFIX_DEFAULT([~/.local/])
AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_AUX_DIR([build-aux])

AM_INIT_AUTOMAKE([1.11 -Wno-portability foreign no-define tar-ustar no-dist-gzip dist-xz])
AM_MAINTAINER_MODE([enable])

# Check for programs
AC_PROG_CC

# Option to specify python interpreter to use; this just sets $PYTHON, so that
# we will fall back to reading $PYTHON if --with-python is not given
AC_ARG_WITH(python,
  AS_HELP_STRING([--with-python=PATH],[Path to Python interpreter; searches $PATH if only a program name is given; if not given, searches for a few standard names such as "python3"]),
  [PYTHON="$withval"], [])
if test x"$PYTHON" = xyes; then
	AC_MSG_ERROR([--with-python option requires a path or program argument])
fi
if test -n "$PYTHON" && ! command -v "$PYTHON" > /dev/null; then
	AC_MSG_ERROR([Python interpreter $PYTHON does not exist])
fi

m4_define(python3_min_ver, 3.7)
AM_PATH_PYTHON([python3_min_ver])

AC_SUBST([PYTHON_BASENAME], [$(basename "$PYTHON")])

PKG_PROG_PKG_CONFIG

# i18n
AM_GNU_GETTEXT([external])
# FIXME: Remove AM_GNU_GETTEXT_VERSION once autoreconf supports REQUIRE_VERSION
AM_GNU_GETTEXT_VERSION([0.19.6])
AM_GNU_GETTEXT_REQUIRE_VERSION([0.19.6])

GETTEXT_PACKAGE=AC_PACKAGE_TARNAME
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE], "$GETTEXT_PACKAGE", [Gettext package])

# GUI
AC_ARG_ENABLE(
	gui,
	AS_HELP_STRING([--enable-gui=@<:@no/yes@:>@], [install the graphical user interface (default: no)]),
	[enable_gui=$enableval],
	[enable_gui=no])
AM_CONDITIONAL([GUI_ENABLED],[test "x$enable_gui" == "xyes"])

YELP_HELP_INIT

AC_CONFIG_FILES([
	Makefile
	doc/Makefile
	po/Makefile.in
	examples/Makefile
	scripts/Makefile
	triggers/Makefile
	jhbuild.desktop.in
	jhbuild/Makefile
	jhbuild/commands/Makefile
	jhbuild/frontends/Makefile
	jhbuild/modtypes/Makefile
	jhbuild/utils/Makefile
	jhbuild/versioncontrol/Makefile
])
AC_OUTPUT
