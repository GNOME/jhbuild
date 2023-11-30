Getting Started
===============

JHBuild requires a few set up steps to be run before building software.
JHBuild requires some prerequisite software, and it is necessary to
install prerequisite tools needed to obtain and build the software
modules.

Installing JHBuild
------------------

JHBuild requires a Python runtime. Verify Python >= 3.7 is installed.

The recommended way to download JHBuild is via the version control
system, ``git``. This can be achieved with the following command. It is
recommended to run the command from a new directory where all source
code will be installed, for example, ``~/jhbuild/checkout``.

::

   $ git clone https://gitlab.gnome.org/GNOME/jhbuild.git
   ...
   $

This will download JHBuild into a new folder named ``jhbuild`` under the
current directory. Now to build and install JHBuild:

::

   $ cd jhbuild
   $ ./autogen.sh
   ...
   $ make
   ...
   $ make install
   ...
   $

If gnome-common, yelp-tools and autotools are available, ``autogen.sh``
will configure JHBuild to install via autotools. If gnome-common,
yelp-tools and autotools are not available, ``autogen.sh`` will
configure JHBuild to install via a plain Makefile. To always use the
plain Makefile method pass ``--simple-install`` to ``autogen.sh``.

If the above steps complete successfully, a small shell script will be
installed in ``~/.local/bin`` to start JHBuild. Add ``~/.local/bin`` to
the ``PATH``:

::

   $ PATH=$PATH:~/.local/bin
   $

To permanently add ``~/.local/bin`` to the :envvar:`PATH` variable, run the
following command:

::

   $ echo 'PATH=$PATH:~/.local/bin' >> ~/.bashrc
   $

Configuring JHBuild
-------------------

JHBuild can be configured via a configuration file. The default location
is ``~/.config/jhbuildrc``. If a configuration file does not exist, the
defaults are used. The configuration file uses Python syntax. An example
is provided, see ``examples/sample.jhbuildrc``. Copy
``examples/sample.jhbuildrc`` to ``~/.config/jhbuildrc`` and customize
as required.

It will also load any ``jhbuildrc`` files in :envvar:`XDG_CONFIG_DIRS` directories.
This is useful for system-wide configuration.

The sample configuration will make JHBuild build the meta-gnome-core and
meta-gnome-apps-tested modules and dependencies from the ``gnome-apps``
module set. JHBuild will unpack source trees to ``~/jhbuild/checkout/``
and install all files to subdirectories of ``~/jhbuild/install/``. The
two directories must be writable.

Configuration variables are documented in :doc:`config-reference`. The most commonly used variables are:

:ref:`repos`

   A dictionary that can be used to specify an alternative repository
   location for a particular repository. This configuration variable is
   useful to a module developer. By default, JHBuild will check out code
   from repositories using an anonymous repository location. The
   dictionary keys are short repository names and the values are
   alternative repository location strings. For example:

   ::

      repos['git.gnome.org'] = 'ssh://username@git.gnome.org/git/'

:ref:`moduleset`

   A string or list of strings specifying the name(s) of the module
   set(s) to use. This can either be the filename of a moduleset
   included with JHBuild (excluding the path and extension), or a full
   HTTP URL to an externally managed moduleset. HTTP URL modulesets are
   cached locally. If a module with the same name is present in more
   than one moduleset, the last set listed takes priority. Modulesets
   provided with JHBuild are updated to match the current GNOME
   development release.

:ref:`modules`

   A list of strings specifying the modules to build. The list of
   modules actually built will be recursively expanded to include all
   the dependencies unless the :ref:`buildone` command is used.
   Defaults to ``['meta-gnome-desktop']``.

:ref:`checkoutroot`

   A string specifying the directory to unpack source trees to. If
   :ref:`buildroot` is set to ``None``, builds will
   occur in this directory too. Defaults to ``~/jhbuild/checkout``.

:ref:`prefix`

   A string specifying the prefix to install modules to. ``prefix`` must
   be an absolute path. This directory must be writable. Defaults to
   ``'~/jhbuild/install/'``.

:ref:`autogenargs`

   A string containing arguments passed to the ``autogen.sh`` script of
   all modules. Can be overridden for particular modules using the
   :ref:`autogenargs` dictionary.

:ref:`cmakeargs`

   A string containing arguments passed to the ``cmake`` invocation of
   all modules. Can be overridden for particular modules using the
   :ref:`cmakeargs` dictionary.

:ref:`makeargs`

   A string listing additional arguments to be passed to ``make``.
   JHBuild will automatically append the parallel execution option
   (``-j``) based upon available CPU cores. Defaults to ``''``.

:ref:`mesonargs`

   A string containing arguments passed to the :command:`meson` invocation of
   all modules. Can be overridden for particular modules using the :ref:`mesonargs`
   dictionary.

:ref:`ninjaargs`

   A string listing additional arguments to be passed to :command:`ninja`.
   Defaults to ``''``.

Build Prerequisites
-------------------

Before any modules can be built, it is necessary to have certain build
tools installed. Common build tools include the GNU Autotools (autoconf,
automake, libtool and gettext), The GNU Toolchain (binutils, gcc, g++),
make, pkg-config and Python, depending on which modules will be built.

JHBuild can check the tools are installed using the :ref:`sanitycheck`
command:

::

   $ jhbuild sanitycheck

If this command displays any messages, please install the required
package from your distribution's repository. A list of `package
names <http://live.gnome.org/JhbuildDependencies>`__ for different
distributions is maintained on the GNOME wiki. Run the ``sanitycheck``
command again after installing the distribution's packages to ensure the
required tools are present.

Using JHBuild
-------------

After set up is complete, JHBuild can be used to build software. To
build all the modules selected in the ``~/.config/jhbuildrc`` file, run
the following command:

::

   $ jhbuild build

JHBuild will download, configure, compile and install each of the
modules. If an error occurs at any stage, JHBuild will present a menu
asking what to do. The choices include dropping to a shell to fix the
error, rerunning the build from various stages, giving up on the module,
or ignore the error and continue.

.. note::

   Giving up on a module will cause any modules depending on the module
   to fail.

Below is an example of the menu displayed:

::

     [1] Rerun phase build
     [2] Ignore error and continue to install
     [3] Give up on module
     [4] Start shell
     [5] Reload configuration
     [6] Go to phase "wipe directory and start over"
     [7] Go to phase "configure"
     [8] Go to phase "clean"
     [9] Go to phase "distclean"
   choice:

It is also possible to build a different set of modules and their
dependencies by passing the module names as arguments to the ``build``
command. For example, to build gtk+:

::

   $ jhbuild build gtk+

If JHBuild is cancelled part way through a build, it is possible to
resume the build at a particular module using the ``--start-at`` option:

::

   $ jhbuild build --start-at=pango

To build one or more modules, ignoring their dependencies, JHBuild
provides the ``buildone`` command. For the ``buildone`` command to
complete successfully, all dependencies must be previously built and
installed or provided by distribution packages.

::

   $ jhbuild buildone gtk+

When actively developing a module, you are likely in a source working
directory. The ``make`` will invoke the build system and install the
module. This will be a key part of your edit-compile-install-test cycle.

::

   $ jhbuild make

To get a list of the modules and dependencies JHBuild will build, and
the order they will be built, use the ``list`` command:

::

   $ jhbuild list

To get information about a particular module, use the ``info`` command:

::

   $ jhbuild info gtk+

To download or update all the software sources without building, use the
``update`` command. The ``update`` command provides an opportunity to
modify the sources before building and can be useful if internet
bandwidth varies.

::

   $ jhbuild update

Later, JHBuild can build everything without downloading or updating the
sources:

::

   $ jhbuild build --no-network

To run a particular command with the same environment used by JHBuild,
use the ``run`` command:

::

   $ jhbuild run program

To start a shell with the same environment used by JHBuild, use the
``shell`` command:

::

   $ jhbuild shell
