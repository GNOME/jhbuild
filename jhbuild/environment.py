# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007-2008  Frederic Peters
# Copyright (C) 2014 Canonical Limited
#
#   environment.py: environment variable setup
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import sys
import os
from distutils.sysconfig import get_python_lib

from jhbuild.utils.cmds import get_output

if sys.platform.startswith('win'):
    from jhbuild.utils import subprocess_win32

def addpath(envvar, path, prepend=True):
    '''Adds a path to an environment variable.'''
    if envvar in [ 'LDFLAGS', 'CFLAGS', 'CXXFLAGS' ]:
        if sys.platform.startswith('win'):
            path = subprocess_win32.fix_path_for_msys(path)

        envval = os.environ.get(envvar)
        if envval:
            envval = path + ' ' + envval
        else:
            envval = path
    else:
        if envvar == 'PATH':
            # PATH is special cased on Windows to allow execution without
            # sh.exe. The other env vars (like LD_LIBRARY_PATH) don't mean
            # anything to native Windows so they stay in UNIX format, but
            # PATH is kept in Windows format (; separated, c:/ or c:\ format
            # paths) so native Popen works.
            pathsep = os.pathsep
        else:
            pathsep = ':'
            if sys.platform.startswith('win'):
                path = subprocess_win32.fix_path_for_msys(path)

            if sys.platform.startswith('win') and len(path) > 1 and \
               path[1] == ':':
                # Windows: Don't allow c:/ style paths in :-separated env vars
                # for obvious reasons. /c/ style paths are valid - if a var is
                # separated by : it will only be of interest to programs inside
                # MSYS anyway.
                path='/'+path[0]+path[2:]

        envval = os.environ.get(envvar, path)
        parts = envval.split(pathsep)
        if prepend:
            parts.insert(0, path)
        else:
            parts.append(path)
        # remove duplicate entries:
        i = 1
        while i < len(parts):
            if parts[i] in parts[:i]:
                del parts[i]
            elif envvar == 'PYTHONPATH' and parts[i] == "":
                del parts[i]
            else:
                i += 1
        envval = pathsep.join(parts)

    os.environ[envvar] = envval

def setup_env_defaults(system_libdirs):
    '''default "system values" for environment variables that are not already set'''

    # PKG_CONFIG_PATH
    if os.environ.get('PKG_CONFIG_PATH') is None:
        for dirname in reversed(system_libdirs + ['/usr/share']):
            full_name = os.path.join(dirname, 'pkgconfig')
            if os.path.exists(full_name):
                addpath('PKG_CONFIG_PATH', full_name)

    # GI_TYPELIB_PATH
    if 'GI_TYPELIB_PATH' not in os.environ:
        for dirname in reversed(system_libdirs):
            full_name = os.path.join(dirname, 'girepository-1.0')
            if os.path.exists(full_name):
                addpath('GI_TYPELIB_PATH', full_name)

    # XDG_DATA_DIRS
    if 'XDG_DATA_DIRS' not in os.environ:
        os.environ['XDG_DATA_DIRS'] = '/usr/local/share:/usr/share'

    # XDG_CONFIG_DIRS
    if 'XDG_CONFIG_DIRS' not in os.environ:
        os.environ['XDG_CONFIG_DIRS']='/etc/xdg'

    # ACLOCAL_PATH
    if 'ACLOCAL_PATH' not in os.environ:
        os.environ['ACLOCAL_PATH']='/usr/share/aclocal'

    # get rid of gdkxft from the env -- it will cause problems.
    if 'LD_PRELOAD' in os.environ:
        valarr = os.environ['LD_PRELOAD'].split(' ')
        for x in valarr[:]:
            if x.find('libgdkxft.so') >= 0:
                valarr.remove(x)
        os.environ['LD_PRELOAD'] = ' '.join(valarr)

    if 'CONFIG_SITE' in os.environ:
        del os.environ['CONFIG_SITE']

def setup_env(prefix):
    '''set environment variables for using prefix'''

    os.environ['JHBUILD_PREFIX'] = prefix
    addpath('JHBUILD_PREFIXES', prefix)

    # LD_LIBRARY_PATH
    libdir = os.path.join(prefix, 'lib')
    addpath('LD_LIBRARY_PATH', libdir)
    os.environ['JHBUILD_LIBDIR'] = libdir

    # LDFLAGS and C_INCLUDE_PATH are required for autoconf configure
    # scripts to find modules that do not use pkg-config (such as guile
    # looking for gmp, or wireless-tools for NetworkManager)
    # (see bug #377724 and bug #545018)

    # This path doesn't always get passed to addpath so we fix it here
    if sys.platform.startswith('win'):
        libdir = subprocess_win32.fix_path_for_msys(libdir)
    os.environ['LDFLAGS'] = ('-L%s ' % libdir) + os.environ.get('LDFLAGS', '')

    includedir = os.path.join(prefix, 'include')
    addpath('C_INCLUDE_PATH', includedir)
    addpath('OBJC_INCLUDE_PATH', includedir)
    addpath('CPLUS_INCLUDE_PATH', includedir)

    # On Mac OS X, we use DYLD_FALLBACK_LIBRARY_PATH
    if sys.platform == 'darwin':
        addpath('DYLD_FALLBACK_LIBRARY_PATH', libdir)

    # PATH
    bindir = os.path.join(prefix, 'bin')
    addpath('PATH', bindir)

    # MANPATH
    manpathdir = os.path.join(prefix, 'share', 'man')
    addpath('MANPATH', '')
    addpath('MANPATH', manpathdir)
    # Setting MANPATH on *BSD causes man to ignore its default search path,
    # so we need to add the default search path to MANPATH.
    if sys.platform.startswith('freebsd') or sys.platform.startswith('dragonfly'):
        systemmanpath = get_output('manpath -q', extra_env={'MANPATH': ''})
        systemmanpath = systemmanpath.strip().split(':')
    elif sys.platform.startswith('netbsd'):
        # Running 'man -p' without specifying a manual page name causes it to
        # exit with status 1.
        systemmanpath = get_output('man -p || true', extra_env={'MANPATH': ''})
        systemmanpath = list(map(os.path.dirname, systemmanpath.strip().split('\n')))
    elif sys.platform.startswith('openbsd'):
        # I cannot find a command that prints the default search path on
        # OpenBSD, so I add paths found in the default /etc/man.conf here.
        systemmanpath = [ '/usr/share/man', '/usr/X11R6/man', '/usr/local/man' ]
    else:
        systemmanpath = []
    for systemmanpathdir in systemmanpath:
        addpath('MANPATH', systemmanpathdir, prepend=False)

    # INFOPATH
    infopathdir = os.path.join(prefix, 'share', 'info')
    infopathports = os.path.join(prefix, 'info')
    if not os.path.exists(infopathdir) and os.path.exists(infopathports):
        addpath('INFOPATH', infopathports)
    else:
        addpath('INFOPATH', infopathdir)

    # PKG_CONFIG_PATH
    pkgconfigdatadir = os.path.join(prefix, 'share', 'pkgconfig')
    pkgconfigdir = os.path.join(libdir, 'pkgconfig')
    addpath('PKG_CONFIG_PATH', pkgconfigdatadir)
    addpath('PKG_CONFIG_PATH', pkgconfigdir)
    # XXX: The host Python on Fedora uses lib64 while jhbuild defaults
    # to lib, so any distutils based build will install .pc files
    # into lib64. To make at least pkg-config happy add the host
    # libdir layout as well.
    host_libdir = os.path.dirname(get_python_lib(True, True, prefix))
    host_pkgconfigdir = os.path.join(host_libdir, 'pkgconfig')
    addpath('PKG_CONFIG_PATH', host_pkgconfigdir)

    # GI_TYPELIB_PATH
    typelibpath = os.path.join(libdir, 'girepository-1.0')
    addpath('GI_TYPELIB_PATH', typelibpath)

    # XDG_DATA_DIRS
    xdgdatadir = os.path.join(prefix, 'share')
    addpath('XDG_DATA_DIRS', xdgdatadir)

    # XDG_CONFIG_DIRS
    xdgconfigdir = os.path.join(prefix, 'etc', 'xdg')
    addpath('XDG_CONFIG_DIRS', xdgconfigdir)

    # XCURSOR_PATH
    if not os.environ.get('XCURSOR_PATH'):
        # The XCURSOR_PATH envvar overrides the default paths,
        # so include them here.
        xcursorpath = [ os.path.join(os.environ['HOME'], '.local', 'share', 'icons'),
                        os.path.join(os.environ['HOME'], '.icons'),
                        '/usr/share/icons',
                        '/usr/share/pixmaps',
                        '/usr/X11R6/lib/X11/icons' ]
        for xcursorpathdir in xcursorpath:
            addpath('XCURSOR_PATH', xcursorpathdir, prepend=False)

    xcursordir = os.path.join(prefix, 'share', 'icons')
    addpath('XCURSOR_PATH', xcursordir)

    # GST_PLUGIN_PATH
    gstplugindir = os.path.join(libdir , 'gstreamer-0.10')
    if os.path.exists(gstplugindir):
        addpath('GST_PLUGIN_PATH', gstplugindir)

    # GST_PLUGIN_PATH_1_0
    gstplugindir = os.path.join(libdir , 'gstreamer-1.0')
    if os.path.exists(gstplugindir):
        addpath('GST_PLUGIN_PATH_1_0', gstplugindir)

    # GST_REGISTRY
    gstregistry = os.path.join(prefix, '_jhbuild', 'gstreamer-0.10.registry')
    os.environ['GST_REGISTRY'] = gstregistry

    # GST_REGISTRY_1_0
    gstregistry = os.path.join(prefix, '_jhbuild', 'gstreamer-1.0.registry')
    os.environ['GST_REGISTRY_1_0'] = gstregistry

    # ACLOCAL_PATH
    aclocalpath = os.path.join(prefix, 'share', 'aclocal')
    addpath('ACLOCAL_PATH', aclocalpath)

    # PERL5LIB
    perl5lib = os.path.join(prefix, 'lib', 'perl5')
    addpath('PERL5LIB', perl5lib)

    # CMAKE_PREFIX_PATH
    addpath('CMAKE_PREFIX_PATH', prefix)

    # These two variables are so that people who use "jhbuild shell"
    # can tweak their shell prompts and such to show "I'm under jhbuild".
    # The first variable is the obvious one to look for; the second
    # one is for historical reasons.
    os.environ['UNDER_JHBUILD'] = 'true'
    os.environ['CERTIFIED_GNOMIE'] = 'yes'

    # PYTHONPATH
    # We use a sitecustomize script to make sure we get the correct path
    # with the various versions of python that the user may run.
    if PKGDATADIR:
        addpath('PYTHONPATH', os.path.join(PKGDATADIR, 'sitecustomize'))
    else:
        addpath('PYTHONPATH', os.path.join(SRCDIR, 'jhbuild', 'sitecustomize'))
