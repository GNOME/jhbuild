
import os, string
import urllib

_isxterm = os.environ.get('TERM', '') == 'xterm'
_boldcode = os.popen('tput bold', 'r').read()
_normal = os.popen('tput rmso', 'r').read()

class Bootstrap:
    def __init__(self, package, version, sourceurl, sourcesize, patch=None,
                 versioncheck=None):
        self.package = package
        self.version = version
        self.sourceurl = sourceurl
        self.sourcesize = sourcesize
        self.patch = patch
        self.versioncheck = versioncheck
    def _bold(self, msg):
        print '%s*** %s ***%s' % (_boldcode, msg, _normal)
        if _isxterm:
            print '\033]0;jhbuild: %s\007' % msg
    def _execute(self, command):
        print command
        ret = os.system(command)
        print
        return ret
    def wants_package(self):
        self._bold('checking for %s %s' % (self.package, self.version))
        if self.versioncheck:
            out = os.popen(self.versioncheck, 'r').read()
            if out == '':
                print 'package not found'
            elif string.find(out, self.version) >= 0:
                print 'package found'
                return 0
            else:
                if out[-1] == '\n': out = out[:-1]
                print 'might be okay:'
                print out
        val = raw_input('do you want to install %s %s [Y/n]? '
                        % (self.package, self.version))
        if val and string.lower(val)[0] == 'n':
            return 0
        return 1
    def build(self, config):
        if not self.wants_package():
            return

        # get the source package
        buildroot = config['checkoutroot']
        localfile = os.path.join(buildroot, os.path.basename(self.sourceurl))
        if not os.path.exists(localfile) or \
           os.stat(localfile)[6] != self.sourcesize:
            while 1:
                self._bold('downloading %s' % self.sourceurl)
                try:
                    urllib.urlretrieve(self.sourceurl, localfile)
                    if os.stat(localfile)[6] == self.sourcesize:
                        break # we got the file
                    print 'downloaded file does not match expected size'
                except IOError:
                    print 'could not download file'
                val = raw_input('try downloading again? ')
                if val and string.lower(val)[0] == 'n':
                    return
        
        # untar the source package
        os.chdir(buildroot)
        localfile = os.path.basename(self.sourceurl)
        self._bold('untaring %s' % localfile)
        ret = self._execute('zcat %s | tar xf -' % localfile)
        if ret != 0:
            print 'failed to untar', self.package
            return

        # change to package directory
        assert localfile[-7:] == '.tar.gz', 'package name should end in .tar.gz'
        os.chdir(localfile[:-7])

        # is there a patch to apply?
        if self.patch:
            patchfile = os.path.join(os.path.dirname(__file__), self.patch)
            self._bold('applying patch %s' % self.patch)
            ret = self._execute('patch -p1 < %s' % patchfile)
            if ret != 0:
                print 'failed to patch', self.package
                return

        # configure ...
        self._bold('configuring %s' % self.package)
        ret = self._execute('./configure --prefix %s' % config['prefix'])
        if ret != 0:
            print 'failed to configure', self.package
            return

        # make
        self._bold('building %s' % self.package)
        ret = self._execute('make')
        if ret != 0:
            print 'failed to build', self.package
            return
        
        # install
        self._bold('installing %s' % self.package)
        ret = self._execute('make install')
        if ret != 0:
            print 'failed to install', self.package
            return

bootstraps = [
    Bootstrap('gettext', '0.10.40',
              'ftp://ftp.gnu.org/pub/gnu/gettext/gettext-0.10.40.tar.gz',
              1352976,
              'gettext-changelog.patch',  # patch to unbreak gettext ...
              'gettextize --version | head -1'),
    Bootstrap('autoconf', '2.52',
              'ftp://ftp.gnu.org/pub/gnu/autoconf/autoconf-2.52.tar.gz',
              846656,
              None,
              'autoconf --version | head -1'),
    Bootstrap('libtool', '1.4.2',
              'ftp://ftp.gnu.org/pub/gnu/libtool/libtool-1.4.2.tar.gz',
              1184578,
              None,
              'libtoolize --version'),
    # some would argue that 1.4-p5 is a better choice, but ...
    Bootstrap('automake', '1.5',
              'ftp://ftp.gnu.org/pub/gnu/automake/automake-1.5.tar.gz',
              526934,
              None,
              'automake --version | head -1'),
    Bootstrap('pkg-config', '0.8.0',
              'http://www.freedesktop.org/software/pkgconfig/releases/pkgconfig-0.8.0.tar.gz',
              585852,
              None,
              'pkg-config --version')
]

def build_bootstraps(config):
    for bootstrap in bootstraps:
        bootstrap.build(config)
