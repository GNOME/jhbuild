




Configuration File Reference
============================

The ``~/.config/jhbuildrc`` file uses standard Python syntax. The file
is run, and the resulting variables defined in the namespace are used to
control how JHBuild acts. A set of default values are inserted into the
namespace before running the user's configuration file.

Boolean configuration variables are set using syntax as demonstrated in
the following example:

::

   use_local_modulesets = True

String configuration variables are set using syntax as demonstrated in
the following example:

::

   autogenargs = '--disable-static --disable-gtk-doc'

List configuration variables are set using syntax as demonstrated in the
following example:

::

   skip = ['mozilla', 'pulseaudio']

Dictionary configuration variables are set using syntax as demonstrated
in the following example:

::

   repos['git.gnome.org'] = 'ssh://username@git.gnome.org/git/'

Configuration Variables
-----------------------

.. _alwaysautogen:

``alwaysautogen``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value if set to ``True``, always run ``autogen.sh``. This
   is equivalent to passing ``--autogen`` option to JHBuild. Defaults to
   ``False``.

.. _autogenargs:

``autogenargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string containing arguments passed to the ``autogen.sh`` script of
   all modules. Can be overridden for particular modules using the
   :ref:`module_autogenargs` dictionary.

.. _branches:

``branches``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A dictionary specifying which branch to use for specific modules.
   This is useful if you are making some changes on a branch of a module
   and want JHBuild to build that branch instead of the one listed in
   the module set.

   The definition of branches depends on the module VCS:

   -  CVS: revision. E.g. ``'BRANCH-PROJECT-0_8'``

   -  Bazaar: URI of module branch. E.g.
      ``'http://bzr.example.net/project/gnome-2-28'``

   -  Git: tuple, with first part being an optional repository (or the
      None value) and the second part the name of the branch. E.g.
      ``('git://git.example.net/project', 'gnome-2-28')``

      ::

         branches['modulename'] = (None, 'branchname')

   -  Subversion: URI of module branch. E.g.
      ``'svn://svn.example.net/project/gnome-2-28'``

.. _builddir_pattern:

``builddir_pattern``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A ``printf`` style formatting pattern used to generate build
   directory names. This is only used when using separate source and
   build trees. The ``%s`` in the format string will be replaced with
   ``checkoutdir``. Defaults to ``'%s'``.

.. _buildroot:

``buildroot``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying the parent directory to place build trees.
   Defaults to ``~/.cache/jhbuild/build``. Setting the value to ``None``
   causes builds to be performed within the source trees.

.. _buildscript:

``buildscript``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying which buildscript to use. The recommended setting
   is the default, ``terminal``. In particular, do not set to ``gtk``.

.. _build_policy:

``build_policy``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying which modules to build. The three possible
   options are ``all``, to build all modules requested, ``updated`` to
   build only modules which have changed, or ``updated-deps`` to build
   modules which have changed or which have dependencies which have
   changed. Defaults to ``updated-deps``.

.. _checkoutroot:

``checkoutroot``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying the directory to unpack source trees to. Unless
   ``buildroot`` is set, builds will occur in this directory too.
   Defaults to ``~/checkout/gnome``.

.. _checkout_mode:

``checkout_mode``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying how the checkout is performed for directories in
   version control. Defaults to ``update``. This can be set per module
   using :ref:`module_checkout_mode`. Possible values are ``update``
   (update checkout directory), ``clobber`` (wipe out directory before
   checking out the sources), ``export`` (wipe out directory then create
   a tarball of the sources containing any patches) and ``copy``
   (checkout in a directory different from the one it will build).

.. _cmakeargs:

``cmakeargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string containing arguments passed to the ``cmake`` invocation of
   all modules. Can be overridden for particular modules using the
   :ref:`module_cmakeargs` dictionary. Defaults to ``''``.

.. _copy_dir:

``copy_dir``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying the directory to copy to, if the copy
   :ref:`checkout_mode` is in use. Defaults to the checkout directory.

.. _export_dir:

``export_dir``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying the directory to export to, if the export
   :ref:`checkout_mode` is in use. Defaults to the checkout directory.

.. _cvs_program:

``cvs_program``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying which program to use for CVS support. This can be
   ``git-cvsimport``, or ``cvs``. Defaults to ``cvs``.

.. _disable_Werror:

``disable_Werror``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value (default ``True``) which controls if
   ``--disable-Werror`` will be passed to automake builds. Many packages
   use this flag as a way to disable fatal compiler warnings. The value
   of ``True`` is selected as a reasonable default for those using
   jhbuild as a means to get an up-to-date version of software packages
   without being side-tracked by build failures in other people's
   modules. Setting this value to ``False`` may make sense for those
   using jhbuild as part of a continuous integration or testing system.

.. _dvcs_mirror_dir:

``dvcs_mirror_dir``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying a local mirror directory. JHBuild will create
   local mirrors of repositories at the specified directory. The mirrors
   can be shared by multiple repository groups, saving space and time
   because hard-links will be used for local clones. The commands
   ``update`` and ``updateone`` will create the mirrors and fetch new
   commits from the online repositories. This option is only supported
   by Git and Bazaar repositories.

.. _exit_on_error:

``exit_on_error``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to exit immediately when a module
   fails to build. This is primarily useful in noninteractive mode, in
   order to prevent additional modules from building after one fails.
   Setting this value to ``True`` is equivalent to passing the
   ``--exit-on-error`` option. Defaults to ``False``.

.. _extra_prefixes:

``extra_prefixes``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A list of strings specifying, in precedence order, the list of extra
   prefixes. JHBuild sets many environment variables (such as
   ``LD_LIBRARY_PATH``, ``PKG_CONFIG_PATH`` and ``XDG_DATA_DIRS``) based
   on the ``prefix`` variable. Adding directories to ``extra_prefixes``
   will cause these prefixes to be included as well, at a lower
   precedence than the JHBuild ``prefix``, but at a higher precedence
   than system directories. This variable is empty by default except on
   systems that install software in ``/usr/local``, in which case it
   contains this directory.

.. _help_website:

``help_website``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A tuple specifying a help website name and URL. The website is
   displayed in the tinderbox html for failed modules. ``%(module)s`` in
   the URL will be replaced with the module name. To disable, set
   ``help_website`` to ``None``. Defaults to
   ``('Gnome Live!', 'http://live.gnome.org/JhbuildIssues/%(module)s')``.

.. _installprog:

``installprog``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying a program to use as replacement for
   ``/usr/bin/install``.

.. _ignore_suggests:

``ignore_suggests``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to ignore soft dependencies when
   calculating the dependency tree. Defaults to ``False``.

.. _interact:

``interact``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to interact with the user. Setting
   this value to ``False`` is equivalent to passing the
   ``--no-interact`` option. Defaults to ``True``.

.. _makeargs:

``makeargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string listing additional arguments to be passed to :command:`make`.
   JHBuild will automatically append the parallel execution option
   (``-j``) based upon available CPU cores. Defaults to ``''``.

.. _makecheck:

``makecheck``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to run :command:`make check` after
   :command:`make`. Defaults to ``False``.

.. _makecheck_advisory:

``makecheck_advisory``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether failures when running
   :command:`make check` should be advisory only and not cause a build failure.
   Defaults to ``False``.

.. _makeclean:

``makeclean``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to run :command:`make clean` before
   :command:`make`. Defaults to ``False``.

.. _makedist:

``makedist``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to run :command:`make dist` after
   :command:`make`. Defaults to ``False``. This setting is equivalent to
   passing the ``--dist`` option.

.. _makedistcheck:

``makedistcheck``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to run ``make distcheck`` after
   :command:`make`. Defaults to ``False``. This setting is equivalent to
   passing the ``--distcheck`` option.

.. _mesonargs:

``mesonargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string containing arguments passed to the :command:`meson` invocation of
   all modules. Can be overridden for particular modules using the
   ``module_mesonargs`` dictionary. Defaults to ``''``.

.. _module_autogenargs:

``module_autogenargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A dictionary mapping module names to strings specifying the arguments
   to be passed to ``autogen.sh``. The setting in :ref:`module_autogenargs`
   is used instead of the global :ref:`autogenargs` setting. If a
   particular module isn't listed in the dictionary, the global
   :ref:`autogenargs` will be used.

.. _module_checkout_mode:

``module_checkout_mode``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   A dictionary specifying which checkout mode to use for modules. This
   overrides the global :ref:`checkout_mode` setting.

.. _module_cmakeargs:

``module_cmakeargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A dictionary mapping module names to strings specifying the arguments
   to be passed to :command:`cmake`. The setting in :ref:`module_cmakeargs` is
   used instead of the global :ref:`cmakeargs` setting. If a particular
   module isn’t listed in the dictionary, the global :ref:`cmakeargs` will
   be used.

.. _module_makeargs:

``module_makeargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A dictionary mapping module names to strings specifying the arguments
   to pass to :command:`make`. The setting in :ref:`module_makeargs` replaces the
   value of :ref:`makeargs`. If a particular module isn't listed in the
   dictionary, the global :ref:`makeargs` will be used.

.. _module_makecheck:

``module_makecheck``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A dictionary mapping module names to boolean values specifying
   whether to run ``make check`` after ``make``. The setting in
   :ref:`module_makecheck` replaces the value of :ref:`makecheck`. If a
   particular module isn't listed in the dictionary, the global
   :ref:`makecheck` will be used.

.. _module_mesonargs:

``module_mesonargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A dictionary mapping module names to strings specifying the arguments
   to be passed to ``meson``. The setting in :ref:`module_mesonargs` is
   used instead of the global :ref:`mesonargs` setting. If a particular
   module isn’t listed in the dictionary, the global :ref:`mesonargs` will
   be used.

.. _module_ninjaargs:

``module_ninjaargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A dictionary mapping module names to strings specifying the arguments
   to pass to ``ninja``. The setting in :ref:`module_ninjaargs` replaces
   the value of :ref:`ninjaargs`. If a particular module isn't listed in
   the dictionary, the global :ref:`ninjaargs` will be used.

.. _module_nopoison:

``module_nopoison``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A dictionary mapping module names to boolean values. If a module is
   set to ``True``, JHBuild will attempt to build dependent modules even
   if the specified module failed. The setting in :ref:`module_nopoison`
   replaces the value of :ref:`nopoison`. If a particular module isn't
   listed in the dictionary, the global :ref:`nopoison` will be used.

.. _module_extra_env:

``module_extra_env``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   A dictionary mapping module names to dictionaries with extra
   environment variables to pass when executing commands for the module.

.. _module_static_analyzer:

``module_static_analyzer``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   Dictionary mapping module names to boolean values indicating whether
   static analysis should be performed while building that module. This
   allows the global :ref:`static_analyzer` configuration option to be
   overridden.

.. _modules:

``modules``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A list of strings specifying the modules to build. The list of
   modules actually built will be recursively expanded to include all
   the dependencies unless the :ref:`buildone` command is used.
   Defaults to ``['meta-gnome-desktop']``.

.. _moduleset:

``moduleset``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string or list of strings specifying the name(s) of the module
   set(s) to use. This can either be the filename of a moduleset
   included with JHBuild (excluding the path and extension), or a full
   HTTP URL to an externally managed moduleset. HTTP URL modulesets are
   cached locally. If a module with the same name is present in more
   than one moduleset, the last set listed takes priority. Modulesets
   provided with JHBuild are updated to match the current GNOME
   development release.

.. _modulesets_dir:

``modulesets_dir``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying the directory containing the modulesets to use.
   Defaults to the ``modulesets/`` directory in JHBuild sources.

.. _nice_build:

``nice_build``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   Run builds under the ``SCHED_IDLE`` priority on Linux, ``nice`` on
   other Unix. This can dramatically improve desktop interactivity for
   parallel builds while having only a negligible impact on build
   throughput.

.. _ninjaargs:

``ninjaargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string listing additional arguments to be passed to ``ninja``.
   Defaults to ``''``.

.. _nobuild:

``nobuild``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value, if set to ``True`` JHBuild will not build modules,
   but just download and unpack the sources. The default value is
   ``False``.

.. _nonetwork:

``nonetwork``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to access the network. This
   affects checking out or updating CVS modules, downloading tarballs
   and updating module sets. Setting this to ``True`` is equivalent to
   passing the ``--no-network`` option. Defaults to ``False``.

.. _nonotify:

``nonotify``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to emit notifications using the
   notification daemon. If set to ``False``, notifications are emitted.
   Defaults to ``True``.

.. _nopoison:

``nopoison``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value, if set to ``True`` JHBuild attempts to build modules
   even if one or more of the module's dependencies failed to build.
   This option is equivalent to the ``--no-poison`` argument. The
   default value is ``False``.

.. _notrayicon:

``notrayicon``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to show an icon in the system tray
   using Zenity. If set to ``False``, an icon is shown. Defaults to
   ``True``.

.. _noxvfb:

``noxvfb``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value, if set to ``True`` JHBuild will run any graphical
   tests on the real X server, rather than using ``Xvfb``. This option
   is equivalent to passing ``--no-xvfb``. The default value is
   ``False``.

.. _partial_build:

``partial_build``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value, if set to ``True`` JHBuild will not build dependency
   modules if corresponding system packages are installed and sufficient
   version. Defaults to ``True``.

.. _prefix:

``prefix``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying the prefix to install modules to. ``prefix`` must
   be an absolute path. This directory must be writable. Defaults to
   ``'~/jhbuild/install/'``.

.. _pretty_print:

``pretty_print``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to pretty format the subprocess
   output. Only CVS output supports pretty printing. Disable if the
   pretty printing causes problems. Defaults to ``True``.

.. _print_command_pattern:

``print_command_pattern``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string displayed before JHBuild executes a command. ``%(command)s``
   in the string will be replaced with the command about to be executed.
   ``%(cwd)s`` in the string will be replaced with the current working
   directory. Defaults to ``'%(command)s'``.

.. _progress_bar:

``progress_bar``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying whether to display a progress bar during
   :ref:`quiet_mode`. Defaults to ``True``.

.. _quiet_mode:

``quiet_mode``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value, if set to ``True`` disables the output of running
   commands. Defaults to ``False``.

.. _repos:

``repos``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A dictionary specifying an alternative repository location for a
   particular repository. This configuration variable is useful to a
   module developer. By default, JHBuild will check out code from
   repositories using an anonymous repository location. The dictionary
   keys are short repository names and the values are the alternative
   repository location strings. For example:

   ::

      repos['git.gnome.org'] = 'ssh://username@git.gnome.org/git/'

.. _shallow_clone:

``shallow_clone``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value specifying if JHBuild should prefer smaller version
   control downloads. Equivalent to ``git clone --depth 1`` or
   ``bzr co --light``. Defaults to ``False``.

.. _skip:

``skip``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A list of modules to skip. This ``--skip`` command line option
   extends the list. This list is empty by default. If the list contains
   the special value ``'*'``, JHBuild will skip all modules not
   explicitly listed in the ``modules`` variable. This may be useful if
   you want to build modules without their implicit dependencies.
   The list supports ``fnmatch()``-style globs, e.g. ``py*`` to
   skip all modules starting with ``py``.

.. _static_analyzer:

``static_analyzer``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value: if set to ``True``, run a static analysis tool on
   each module as it’s being built. Defaults to ``False``.

.. _static_analyzer_outputdir:

``static_analyzer_outputdir``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   Root directory below which static analysis reports will be saved (if
   :ref:`static_analyzer` is ``True``). Defaults to
   ``/tmp/jhbuild_static_analyzer``.

.. _static_analyzer_template:

``static_analyzer_template``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   Command template for the static analyzer. This has the parameters
   ``outputdir`` (the value of the :ref:`static_analyzer_outputdir`
   configuration variable) and ``module`` (the name of the module
   currently being built) substituted into it ``printf``-style. The
   resulting command is used as a prefix to ``make`` when building a
   module. Defaults to ``scan-build``.

.. _sticky_date:

``sticky_date``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string if set, and if supported by the underlying version control
   system, JHBuild will update the source tree to the specified date
   before building. An ISO date format is required, e.g.
   ``'yyyy-mm-dd'``. Defaults to ``None``.

.. _svn_program:

``svn_program``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying which program to use for subversion support. This
   can be ``svn``, ``git-svn`` or ``bzr``. Defaults to ``svn``.

.. _system_libdirs:

``system_libdirs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A list of strings specifying the system library paths. This is used
   when setting the default values of some environment variables, such
   as ``PKG_CONFIG_PATH``.

.. _tarballdir:

``tarballdir``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string if set, tarballs will be downloaded to the specified
   directory instead of :ref:`checkoutroot`. This is useful if you have
   multiple JHBuild environments or regularly clear out :ref:`checkoutroot`
   and want to reduce bandwidth usage. Defaults to
   ``'~/.cache/jhbuild/downloads'``.

.. _tinderbox_outputdir:

``tinderbox_outputdir``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string specifying the directory to store ``jhbuild tinderbox``
   output. This string can be overridden by the ``--output`` option.
   Defaults to ``None``, so either the command line option must be used
   or this variable must be set in the configuration file.

.. _trycheckout:

``trycheckout``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value, if set to ``True`` JHBuild will automatically try to
   solve failures by 1) running ``autogen.sh`` again, and 2) checking
   out a newer version of a module from version control. This setting is
   equivalent to passing the ``--try-checkout`` option.

.. _use_local_modulesets:

``use_local_modulesets``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A boolean value that specifies to use modulesets that were checked
   out along the JHBuild source code; instead of downloading them
   on-the-fly from GNOME version control system. Defaults to ``False``.

.. _xvfbargs:

``xvfbargs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A string listing arguments to pass to ``Xvfb`` if running graphical
   tests.

.. _conditions:

``conditions``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   A set of condition (strings) that can influence the modules that are
   built and the options that are used for building them. You should use
   ``conditions.add()`` and ``conditions.discard()`` to modify the list
   if you want to make changes.

   The original set of conditions is determined on a per-OS basis and
   can be modified using the ``--conditions=`` commandline argument. The
   changes made by ``--conditions`` are visible at the time that
   jhbuildrc is sourced, so you can set other variables based on the
   current value of the set, but ``--conditions`` will be applied again
   after any changes made by jhbuildrc.

Other Configuration File Structures
-----------------------------------

In addition to the above variables, there are other settings that can be
set in the configuration file:

.. py:data:: os.environ

   A dictionary representing the environment. This environment is passed
   to processes that JHBuild spawns.

   Some influential environment variables include ``CPPFLAGS``,
   ``CFLAGS``, ``INSTALL`` and ``LDFLAGS``. For example:

   ::

      os.environ['CFLAGS'] = '-O0 -g'

.. py:function:: addpath(envvar, pathname)

   This will add a directory to the ``PATH`` environment variable.
   ``addpath`` will correctly handle the case when the environment
   variable is initially empty (having a stray colon at the beginning or
   end of an environment variable can have unexpected consequences).

.. py:function:: prependpath(envvar, pathname)

   After processing the configuration file, JHBuild will alter some
   paths based on variables such as ``prefix`` (e.g. adding
   ``$prefix/bin`` to the start of ``PATH``).

   The ``prependpath`` function works like ``addpath``, except that the
   environment variable is modified after JHBuild has made its changes
   to the environment.
