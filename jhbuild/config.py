# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   config.py: configuration file parser
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

import os
import traceback
import sys

from jhbuild.errors import UsageError, FatalError

__all__ = [ 'Config' ]

_defaults_file = os.path.join(os.path.dirname(__file__), 'defaults.jhbuildrc')
_default_jhbuildrc = os.path.join(os.environ['HOME'], '.jhbuildrc')

_known_keys = [ 'moduleset', 'modules', 'skip', 'prefix',
                'checkoutroot', 'buildroot', 'autogenargs', 'makeargs',
                'repos', 'branches',
                'builddir_pattern', 'module_autogenargs', 'module_makeargs',
                'interact', 'buildscript', 'nonetwork',
                'alwaysautogen', 'nobuild', 'makeclean', 'makecheck',
                'use_lib64', 'tinderbox_outputdir', 'sticky_date',
                'tarballdir', 'pretty_print', 'svn_program', 'makedist',
                'makedistcheck', 'nonotify']

env_prepends = {}
def prependpath(envvar, path):
    env_prepends.setdefault(envvar, []).append(path)

def addpath(envvar, path):
    '''Adds a path to an environment variable.'''
    # special case ACLOCAL_FLAGS
    if envvar in [ 'ACLOCAL_FLAGS' ]:
        envval = os.environ.get(envvar, '-I %s' % path)
        parts = ['-I', path] + envval.split()
        i = 2
        while i < len(parts)-1:
            if parts[i] == '-I':
                # check if "-I parts[i]" comes earlier
                for j in range(0, i-1):
                    if parts[j] == '-I' and parts[j+1] == parts[i+1]:
                        del parts[i:i+2]
                        break
                else:
                    i += 2
            else:
                i += 1
        envval = ' '.join(parts)
    else:
        envval = os.environ.get(envvar, path)
        parts = envval.split(':')
        parts.insert(0, path)
        # remove duplicate entries:
        i = 1
        while i < len(parts):
            if parts[i] in parts[:i]:
                del parts[i]
            else:
                i += 1
        envval = ':'.join(parts)

    os.environ[envvar] = envval

class Config:
    def __init__(self, filename=_default_jhbuildrc):
        config = {
            '__file__': _defaults_file,
            'addpath':  addpath,
            'prependpath':  prependpath
            }
        env_prepends.clear()
        try:
            execfile(_defaults_file, config)
        except:
            traceback.print_exc()
            raise FatalError('could not load config defaults')
        config['__file__'] = filename
        try:
            execfile(filename, config)
        except:
            traceback.print_exc()
            raise FatalError('could not load config file')

        # backward compatibility, from the days when jhbuild only
        # supported Gnome.org CVS.
        if config.has_key('cvsroot'):
            config['cvsroots']['gnome.org'] = config['cvsroot']
        if config.has_key('cvsroots'):
            config['repos'].update(config['cvsroots'])
        if config.has_key('svnroots'):
            config['repos'].update(config['svnroots'])

        # environment variables
        if config.has_key('cflags') and config['cflags']:
            os.environ['CFLAGS'] = config['cflags']
        if config.has_key('installprog') and config['installprog']:
            os.environ['INSTALL'] = config['installprog']

        # copy known config keys to attributes on the instance
        for name in _known_keys:
            setattr(self, name, config[name])

        # default tarballdir to checkoutroot
        if not self.tarballdir: self.tarballdir = self.checkoutroot

        self.setup_env()

    def setup_env(self):
        '''set environment variables for using prefix'''

        if not os.path.exists(self.prefix):
            try:
                os.makedirs(self.prefix)
            except:
                raise FatalError("Can't create %s directory" % self.prefix)

        #includedir = os.path.join(prefix, 'include')
        #addpath('C_INCLUDE_PATH', includedir)

        # LD_LIBRARY_PATH
        if self.use_lib64:
            libdir = os.path.join(self.prefix, 'lib64')
        else:
            libdir = os.path.join(self.prefix, 'lib')
        addpath('LD_LIBRARY_PATH', libdir)

        # PATH
        bindir = os.path.join(self.prefix, 'bin')
        addpath('PATH', bindir)

        # PKG_CONFIG_PATH
        pkgconfigdatadir = os.path.join(self.prefix, 'share', 'pkgconfig')
        pkgconfigdir = os.path.join(libdir, 'pkgconfig')
        addpath('PKG_CONFIG_PATH', pkgconfigdatadir)
        addpath('PKG_CONFIG_PATH', pkgconfigdir)

        # XDG_DATA_DIRS
        xdgdatadir = os.path.join(self.prefix, 'share')
        addpath('XDG_DATA_DIRS', xdgdatadir)

        # XDG_CONFIG_DIRS
        xdgconfigdir = os.path.join(self.prefix, 'etc', 'xdg')
        addpath('XDG_CONFIG_DIRS', xdgconfigdir)

        # ACLOCAL_FLAGS
        aclocaldir = os.path.join(self.prefix, 'share', 'aclocal')
        if not os.path.exists(aclocaldir):
            try:
                os.makedirs(aclocaldir)
            except:
                raise FatalError("Can't create %s directory" % aclocaldir)
        addpath('ACLOCAL_FLAGS', aclocaldir)

        # PERL5LIB
        perl5lib = os.path.join(self.prefix, 'lib', 'perl5')
        addpath('PERL5LIB', perl5lib)

        os.environ['CERTIFIED_GNOMIE'] = 'yes'

	# PYTHONPATH
	pythonversion = 'python' + str(sys.version_info[0]) + '.' + str(sys.version_info[1])
	if self.use_lib64:
            pythonpath = os.path.join(self.prefix, 'lib64', pythonversion, 'site-packages')
        else:
            pythonpath = os.path.join(self.prefix, 'lib', pythonversion, 'site-packages')
	addpath('PYTHONPATH', pythonpath)

        # handle environment prepends ...
        for envvar in env_prepends.keys():
            for path in env_prepends[envvar]:
                addpath(envvar, path)
        

        # get rid of gdkxft from the env -- it will cause problems.
        if os.environ.has_key('LD_PRELOAD'):
            valarr = os.environ['LD_PRELOAD'].split(' ')
            for x in valarr[:]:
                if x.find('libgdkxft.so') >= 0:
                    valarr.remove(x)
            os.environ['LD_PRELOAD'] = ' '.join(valarr)
