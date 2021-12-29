JHBuild README
==============

JHBuild is a tool designed to ease building collections of source
packages, called “modules”.

JHBuild was originally written for building GNOME, but has since been
extended to be usable with other projects.

JHBuild requires Python >= 3.7

Installing JHBuild
------------------

Refer to the 'Getting Started' section of the JHBuild manual:

  https://gnome.pages.gitlab.gnome.org/jhbuild/getting-started.html

Or refer to the online JHBuild manual at:

  https://gnome.pages.gitlab.gnome.org/jhbuild/index.html
  
An introduction to JHBuild is also available on the GNOME Wiki:
  https://wiki.gnome.org/Projects/Jhbuild/Introduction

Using JHBuild
-------------

JHBuild uses a command line syntax similar to tools like CVS:

**jhbuild [global-options] command [command-arguments]**

The global JHBuild options are:

-f, --file config
  Use an alternative configuration file instead of the default
  ~/.config/jhbuildrc.

-m, --moduleset moduleset
  Use a module set other than the module set listed in the
  configuration file. This option can be a relative path if the module
  set is located in the JHBuild moduleset folder, or an absolute path
  if located elsewhere.

--no-interact
  Do not prompt the user for any input. This option is useful if
  leaving a build unattended, in order to ensure the build is not
  interrupted.

Refer to the JHBuild manual for a complete list of JHBuild commands
and options. The common ones are:

**jhbuild bootstrap**

The bootstrap command installs a set of build utilities. The build
utilities include autoconf , automake and similar utilities. The
recommended method to install the build utilities is via your
distribution's package management system. The bootstrap should only be
used if the build utilites are not provided by your distribution's package
management system, for example on Mac OS.

**jhbuild build [--autogen] [--clean] [--dist] [--distcheck] [--ignore-suggests] [--no-network] [--skip=module...] [--start-at=module] [--tags=tags] [-D date] [--no-xvfb] [--try-checkout] [--no-poison] [--force] [--build-optional-modules] [--min-age=time] [module...]**

The build command builds one or more packages, including their
dependencies.

If no module names are provided on the command line, the modules
list from the configuration file will be used.

-a, --autogen
  Always run autogen.sh before building modules. By default,
  autogen.sh will only be called if the top-level makefile is
  missing. Otherwise, JHBuild relies on the package's makefiles to
  detect if configure needs to be rebuilt or rerun.

-c, --clean
  Run make clean before building modules.

-d, --dist
  Run make dist after building modules.

--distcheck
  Run make distcheck after building modules.

--ignore-suggests
  Do not build soft dependencies.

-n, --no-network
  Do not access the network when building modules. This will skip
  download or update stages in a build. If a module can't be built
  without network access, the module build will fail.

-s, --skip=<module,...>
  Do not build the listed modules. Used to skip the building of
  specified dependencies.

--tags=<tag,...>
  Ignore modules that do not match tag. Modules are automatically
  attributed a tag matching the name of the module's module set.

-t, --start-at=module
  Start at the named module rather than at the beginning of the
  list. This option is useful if the build was interrupted.

-D date
  If supported by the underlying version control system, update the
  source tree to the specified date before building. An ISO date
  format is required, e.g. "2009-09-18 02:32Z".

-x, --no-xvfb
  Run graphical tests on the actual X server rather than in a
  simulated Xvfb.

-C, --try-checkout
  If the build fails, and if supported by the version control system,
  force a checkout and run autogen.sh before retrying the build.

-N, --no-poison
  If one or more of a module's dependencies failed, this option forces
  JHBuild to try to build the module anyway.

-f, --force
  Build the modules even if policy states it is not required.

--build-optional-modules
  Modules listed as optional dependencies, may not be required to
  build the module. This option forces JHBuild to build optional
  dependencies.

--min-age=time
  Skip modules installed more recently than the specified relative
  time. The time string format is a number followed by a unit. The
  following units are supported: seconds (s), minutes (m), hours (h)
  and days (d). For example, --min-age=2h will skip modules built
  less than two hours ago.

**jhbuild buildone [--autogen] [--clean] [--distcheck] [--no-network] [-D date] [--no-xvfb] [--force] [--min-age=time] module...**

The buildone command is similar to build, but it does not build the
dependent modules. It is useful for rebuilding one or more modules.

**jhbuild sanitycheck**

The sanitycheck command performs a number of checks to verify the
build environment is okay.

For details of all jbhuild's command line options:

  jhbuild --help

Reporting Bugs
--------------

If you find any bugs in JHBuild, or have feature requests (or
implementations :), please file them at:

  https://gitlab.gnome.org/GNOME/jhbuild/issues/new

This will ensure your request is not lost.
