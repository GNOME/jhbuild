import os, string

def _execute(cmd):
    print cmd
    ret = os.system(cmd)
    print
    return ret

class CVSRoot:
    '''A class to wrap up various CVS opperations.'''
    
    def __init__(self, cvsroot, checkoutroot):
        self.cvsroot = cvsroot
        self.localroot = checkoutroot

        self._login()
        
    def _login(self):
        '''Maybe log in (if there are no entries in ~/.cvspass)'''
        loggedin = 0
        try:
            home = os.environ['HOME']
            fp = open(os.path.join(home, '.cvspass'), 'r')
            for line in fp.readlines():
                parts = string.split(line)
                if parts[0] == '/1':
                    root = parts[1]
                else:
                    root = parts[0]
                if string.replace(self.cvsroot, ':2401', ':') == \
                       string.replace(root, ':2401', ':'):
                    loggedin = 1
                    break
        except IOError:
            pass
        if not loggedin:
            return _execute('cvs -d %s login' % self.cvsroot)

    def getcheckoutdir(self, module, checkoutdir=None):
        if checkoutdir:
            return os.path.join(self.localroot, checkoutdir)
        else:
            return os.path.join(self.localroot, module)

    def checkout(self, module, revision=None, checkoutdir=None):
        os.chdir(self.localroot)
        cmd = 'cvs -z3 -q -d %s checkout ' % self.cvsroot

        if checkoutdir:
            cmd = cmd + '-d %s ' % checkoutdir

        if revision:
            cmd = cmd + '-r %s ' % revision
        else:
            cmd = cmd + '-A '

        cmd = cmd + module

        return _execute(cmd)

    def update(self, module, revision=None, checkoutdir=None):
        '''Perform a "cvs update" (or possibly a checkout)'''
        dir = self.getcheckoutdir(module, checkoutdir)
        if not os.path.exists(dir):
            return self.checkout(module, revision, checkoutdir)
        
        os.chdir(dir)
        cmd = 'cvs -z3 -q -d %s update ' % self.cvsroot

        if revision:
            cmd = cmd + '-r %s ' % revision
        else:
            cmd = cmd + '-A '

        cmd = cmd + '.'

        return _execute(cmd)
