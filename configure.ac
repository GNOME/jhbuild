AC_INIT([jhbuild],
        [3.34.0],
        [http://bugzilla.gnome.org/enter_bug.cgi?product=jhbuild],
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
  AS_HELP_STRING([--with-python=PATH],[Path to Python interpreter; searches $PATH if only a program name is given; if not given, searches for a few standard names such as "python3" or "python2"]),
  [PYTHON="$withval"], [])
if test x"$PYTHON" = xyes; then
	AC_MSG_ERROR([--with-python option requires a path or program argument])
fi
if test -n "$PYTHON" && ! command -v "$PYTHON" > /dev/null; then
	AC_MSG_ERROR([Python interpreter $PYTHON does not exist])
fi

# All this is supposed to do is check the Python version against python_min_ver
# and python3_min_ver and prefer Python 3.x if nothing is set.
m4_define(python_min_ver, 2.7)
m4_define(python3_min_ver, 3.5)
if test -n "$PYTHON"; then
	AM_PATH_PYTHON([python_min_ver])
	AM_PYTHON_CHECK_VERSION([$PYTHON], [3.0],
				build_py3k=true,
				build_py3k=false)
	if test $build_py3k = true ; then
		AC_MSG_CHECKING([for $PYTHON >=] python3_min_ver)
		AM_PYTHON_CHECK_VERSION([$PYTHON], python3_min_ver,
					[AC_MSG_RESULT(yes)],
					[AC_MSG_ERROR(too old)])
	fi
else
	AM_PATH_PYTHON([python3_min_ver], [], [
		unset PYTHON;
		# XXX: AM_PATH_PYTHON caching is broken and always returns the result of the first use
		unset am_cv_pathless_PYTHON;
		AM_PATH_PYTHON([python_min_ver], [
			AS_CASE(["$PYTHON_VERSION"],
				[2.*], [],
				[AC_MSG_ERROR([JHBuild requires Python ] python_min_ver [or] python3_min_ver)])
		])
	])
fi

PKG_PROG_PKG_CONFIG

# i18n
AM_GNU_GETTEXT([external])
# FIXME: Remove AM_GNU_GETTEXT_VERSION once autoreconf supports REQUIRE_VERSION
AM_GNU_GETTEXT_VERSION([0.19.6])
AM_GNU_GETTEXT_REQUIRE_VERSION([0.19.6])

GETTEXT_PACKAGE=AC_PACKAGE_TARNAME
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE], "$GETTEXT_PACKAGE", [Gettext package])

# Documentation
AC_ARG_ENABLE(
	doc_installation,
	AS_HELP_STRING([--enable-doc-installation=@<:@no/yes@:>@], [install the documentation files]),
	[enable_doc_installation=$enableval],
	[enable_doc_installation=no])
AM_CONDITIONAL([DOC_INSTALLATION_ENABLED],[test "x$enable_doc_installation" = "xyes"])

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
