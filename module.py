import os, string

_boldcode = os.popen('tput bold', 'r').read()
_normal = os.popen('tput rmso', 'r').read()

user_shell = os.environ.get('SHELL', '/bin/sh')

class Module:
    def __init__(self, name, checkoutdir=None, revision=None,
                 autogenargs='', dependencies=[]):
        self.name = name
        self.checkoutdir = checkoutdir
        self.revision = revision
        self.autogenargs = autogenargs
        self.dependencies = dependencies

    def __repr__(self):
        return '<cvs module %s>' % self.name

    def get_checkout_dir(self, checkoutroot):
        '''get the directory we will checkout to'''
        if self.checkoutdir:
            return os.path.join(checkoutroot, self.checkoutdir)
        else:
            return os.path.join(checkoutroot, self.name)

    def cvs_checkout_args(self):
        '''arguments to checkout the module'''
        ret = 'checkout '
        if self.checkoutdir:
            ret = ret + '-d ' + self.checkoutdir
        if self.revision:
            ret = ret + '-r ' + self.revision
        else:
            ret = ret + '-A '
        return ret + self.name

    def cvs_update_args(self):
        '''arguments to update the module (to be run from checkout dir)'''
        ret = 'update '
        if self.revision:
            ret = ret + '-r ' + self.revision
        else:
            ret = ret + '-A '
        return ret + '.'

    def autogen_args(self):
        '''return extra arguments to pass to autogen'''
        return self.autogenargs

class ModuleSet:
    def __init__(self):
        self.modules = {}
    def add(self, module):
        '''add a Module object to this set of modules'''
        self.modules[module.name] = module
    def get_module_list(self, seed):
        '''gets a list of module objects (in correct dependency order)
        needed to build the modules in the seed list'''
        module_list = map(lambda name, modules=self.modules:
                          modules[name], seed)
        i = 0
        while i < len(module_list):
            # make sure dependencies are built first
            depadd = []
            for dep in module_list[i].dependencies:
                depmod = self.modules[dep]
                if depmod not in module_list[:i+1]:
                    depadd.append(depmod)
            module_list[i:i] = depadd
            if not depadd:
                i = i + 1
        i = 0
        while i < len(module_list):
            if module_list[i] in module_list[:i]:
                del module_list[i]
            else:
                i = i + 1
        return module_list
    def get_full_module_list(self):
        return self.get_module_list(self.modules.keys())

class BuildScript:
    def __init__(self, cvsroot, modulelist, autogenargs=None, cflags=None,
                 prefix=None, checkoutroot=None, installprog=None):
        self.cvsroot = cvsroot
        self.modulelist = modulelist
        self.autogenargs = autogenargs
        self.cflags = cflags
        self.prefix = prefix
        self.checkoutroot = checkoutroot
        self.installprog = installprog
        
        if not self.autogenargs:
            self.autogenargs = '--disable-static --disable-gtk-doc'
        if not self.prefix:
            self.prefix = '/opt/gtk2'
        if not self.checkoutroot:
            self.checkoutroot = os.path.join(os.environ['HOME'], 'cvs','gnome')

        assert os.access(self.prefix, os.R_OK|os.W_OK|os.X_OK), \
               'install prefix must be writable'

        self.login()
        self.setupenv()

    def login(self):
        '''make sure we are logged into the cvs server first'''
        loggedin = 0
        try:
            home = os.environ['HOME']
            fp = open(os.path.join(home, '.cvspass'), 'r')
            for line in fp.readlines():
                pos = string.find(line, ' ')
                if pos > 0:
                    line = line[:pos]
                if line == self.cvsroot:
                    loggedin = 1
                    break
        except IOError:
            pass
        if not loggedin:
            os.system('cvs -d %s login' % self.cvsroot)

    def __addpath(self, envvar, path):
        try:
            envval = os.environ[envvar]
            if string.find(envval, path) < 0:
                envval = envval + ':' + path
        except KeyError:
            envval = path
        os.environ[envvar] = envval
    def setupenv(self):
        '''set environment variables for using prefix'''
        includedir = os.path.join(self.prefix, 'include')
        self.__addpath('C_INCLUDE_PATH', includedir)
        libdir = os.path.join(self.prefix, 'lib')
        self.__addpath('LD_LIBRARY_PATH', libdir)
        bindir = os.path.join(self.prefix, 'bin')
        self.__addpath('PATH', bindir)
        pkgconfigdir = os.path.join(libdir, 'pkgconfig')
        self.__addpath('PKG_CONFIG_PATH', pkgconfigdir)
        aclocaldir = os.path.join(self.prefix, 'share', 'aclocal')
        try:
            val = os.environ['ACLOCAL_FLAGS']
            os.environ['ACLOCAL_FLAGS'] = '%s -I %s' % (val, aclocaldir)
        except KeyError:
            os.environ['ACLOCAL_FLAGS'] = '-I %s' % aclocaldir
        os.environ['CERTIFIED_GNOMIE'] = 'yes'

        if self.installprog:
            os.environ['INSTALL'] = self.installprog

        if self.cflags:
            os.environ['CFLAGS'] = self.cflags

    def _message(self, msg):
        print '%s*** %s ***%s' % (_boldcode, msg, _normal)

    def _execute(self, command):
        print command
        ret = os.system(command)
        print
        return ret

    def _cvscheckout(self, module):
        checkoutdir = module.get_checkout_dir(self.checkoutroot)
        if os.path.exists(checkoutdir):
            os.chdir(checkoutdir)
            self._message('updating module %s in %s' %
                          (module.name, checkoutdir))
            cmd = 'cvs -z3 -q %s' % module.cvs_update_args()
        else:
            os.chdir(self.checkoutroot)
            self._message('checking out module %s into %s' %
                          (module.name, checkoutdir))
            cmd = 'cvs -z3 -q -d %s %s' % \
                  (self.cvsroot, module.cvs_checkout_args())
        return self._execute(cmd)

    def _configure(self, module):
        self._message('running autogen.sh script for %s' % module.name)
        cmd = './autogen.sh --prefix %s %s %s' % \
              (self.prefix, self.autogenargs, module.autogen_args())
        return self._execute(cmd)

    def _makeclean(self, module):
        self._message('running make clean for %s' % module.name)
        return self._execute('make clean')

    def _make(self, module):
        self._message('running make for %s' % module.name)
        return self._execute('make')

    def _makeinstall(self, module):
        self._message('running make install for %s' % module.name)
        return self._execute('make install')

    ERR_RERUN = 0
    ERR_CONT = 1
    ERR_GIVEUP = 2
    def _handle_error(self, module, stage):
        '''Ask the user what to do about an error.

        Returns one of ERR_RERUN, ERR_CONT or ERR_GIVEUP.'''

        self._message('error during %s for module %s' % (stage, module.name))
        while 1:
            print
            print '  [1] rerun %s' % stage
            print '  [2] start shell'
            print '  [3] give up on module'
            print '  [4] continue (ignore error)'
            val = raw_input('choice: ')
            if val == '1':
                return self.ERR_RERUN
            elif val == '2':
                print 'exit shell to continue with build'
                os.system(user_shell)
            elif val == '3':
                return self.ERR_GIVEUP
            elif val == '4':
                return self.ERR_CONT
            else:
                print 'invalid option'

    def build(self, cvsupdate=1, alwaysautogen=0, makeclean=0, nobuild=0,
              skip=(), interact=1):
        poison = []  # list of modules that couldn't be built

        # build steps for each module ...
        STATE_CHECKOUT = 0
        STATE_CONFIGURE = 1
        STATE_CLEAN = 2
        STATE_BUILD = 3
        STATE_INSTALL = 4
        STATE_DONE = 5

        state_names = [
            'checkout', 'configure', 'clean', 'build', 'install', 'done'
        ]

        for module in self.modulelist:
            if module.name in skip: continue

            # check if any dependencies have been poisoned
            poisoned = 0
            for dep in module.dependencies:
                if dep in poison:
                    self._message('module %s not built due to non buildable %s'
                                  % (module.name, dep))
                    poisoned = 1
            if poisoned:
                poison.append(module.name)
                continue

            state = STATE_CHECKOUT
            while state != STATE_DONE:
                ret = 0
                next_state = STATE_DONE
                if state == STATE_CHECKOUT:
                    checkoutdir = module.get_checkout_dir(self.checkoutroot)
                    if cvsupdate:
                        ret = self._cvscheckout(module)

                    if nobuild:
                        next_state = STATE_DONE
                    else:
                        next_state = STATE_CONFIGURE
                    if ret == 0:
                        if not os.path.exists(checkoutdir):
                            self._message("checkout doesn't exist :(")
                            poison.append(module.name)
                            next_state = STATE_DONE
                        else:          # else, go on to configure check
                            os.chdir(checkoutdir)

                elif state == STATE_CONFIGURE:
                    if not os.path.exists('Makefile') or alwaysautogen:
                        ret = self._configure(module)
                    next_state = STATE_CLEAN

                elif state == STATE_CLEAN:
                    if makeclean:
                        ret = self._makeclean(module)
                    next_state = STATE_BUILD

                elif state == STATE_BUILD:
                    ret = self._make(module)
                    next_state = STATE_INSTALL

                elif state == STATE_INSTALL:
                    ret = self._makeinstall(module)
                    next_state = STATE_DONE

                if ret == 0:
                    state = next_state
                else:
                    if interact:
                        err = self._handle_error(module, state_names[state])
                    else:
                        self._message('giving up on %s' % module.name)
                        err = self.ERR_GIVEUP # non interactive
                    if err == self.ERR_CONT:
                        state = next_state
                    elif err == self.ERR_RERUN:
                        pass # redo stage
                    elif err == self.ERR_GIVEUP:
                        poison.append(module.name)
                        state = STATE_DONE

        if len(poison) == 0:
            self._message('success')
        else:
            self._message('the following modules were not built')
            for module in poison:
                print module,
            print
