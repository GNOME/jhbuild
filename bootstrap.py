
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
            elif string.find(out, string.replace(self.version, 'x', '')) >= 0:
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
                except IOError, e:
                    print 'Could not download file. Exception was: '
                    print e
                val = raw_input('try downloading again? ')
                if val and string.lower(val)[0] == 'n':
                    return
        
        # untar the source package
        os.chdir(buildroot)
        localfile = os.path.basename(self.sourceurl)
        self._bold('untaring %s' % localfile)
        ret = self._execute('gunzip -dc %s | tar xf -' % localfile)
        if ret != 0:
            print 'failed to untar', self.package
            return

        # change to package directory
        if localfile[-7:] == '.tar.gz':
            os.chdir(localfile[:-7])
        elif localfile[-4:] == '.tgz':
            os.chdir(localfile[:-4])
        else:
            print 'unknown package extension: ', self.package
            return

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
    Bootstrap('gettext', '0.11.2',
              'ftp://ftp.gnu.org/pub/gnu/gettext/gettext-0.11.2.tar.gz',
              3170203,
              'gettext-changelog.patch',  # patch to unbreak gettext ...
              'gettextize --version | head -1'),
    Bootstrap('autoconf', '2.53',
              'ftp://ftp.gnu.org/pub/gnu/autoconf/autoconf-2.53.tar.gz',
              990527,
              None,
	      '((which autoconf2.50 &> /dev/null && autoconf2.50 --version) || autoconf --version) | head -1'),
    Bootstrap('libtool', '1.4.2',
              'ftp://ftp.gnu.org/pub/gnu/libtool/libtool-1.4.2.tar.gz',
              1184578,
              None,
              'libtoolize --version'),
    # some would argue that 1.4-p5 is a better choice, but ...
    Bootstrap('automake', '1.6.1',
              'ftp://ftp.gnu.org/pub/gnu/automake/automake-1.6.1.tar.gz',
              595788,
              None,
              'automake --version | head -1'),
    Bootstrap('pkg-config', '0.12.0',
              'http://www.freedesktop.org/software/pkgconfig/releases/pkgconfig-0.12.0.tar.gz',
              603456,
              None,
              'pkg-config --version'),
    Bootstrap('python', '2.x',
              'http://www.python.org/ftp/python/2.2/Python-2.2.tgz',
              6542443,
              None,
              'echo "import sys, string; print string.split(sys.version)[0]" | python -'),
    Bootstrap('audiofile', '0.2.3',
              'ftp://oss.sgi.com/projects/audiofile/download/audiofile-0.2.3.tar.gz',
              332223,
              None,
              'audiofile-config --version'),
    Bootstrap('scrollkeeper', '0.3.9',
              'http://unc.dl.sourceforge.net/sourceforge/scrollkeeper/scrollkeeper-0.3.9.tar.gz',
              418815,
              None,
              'scrollkeeper-config --version'),
]

def build_bootstraps(config):
    for bootstrap in bootstraps:
        bootstrap.build(config)
