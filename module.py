# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2002  James Henstridge
#
#   module.py: logic for running the build.
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

import os, string
import cvs
import interface

class Module:
    def __init__(self, name, checkoutdir=None, revision=None,
                 autogenargs='', dependencies=[], cvsroot=None):
        self.name = name
        self.checkoutdir = checkoutdir
        self.revision = revision
        self.autogenargs = autogenargs
        self.dependencies = dependencies
        self.cvsroot = cvsroot

    def __repr__(self):
        return '<cvs module %s>' % self.name

    def autogen_args(self):
        '''return extra arguments to pass to autogen'''
        return self.autogenargs

class MetaModule:
    '''MetaModules are like Modules, except that nothing needs to be
    done to build them (they only have dependencies).'''
    def __init__(self, name, modules):
        self.name = name
        self.modules = modules

class ModuleSet:
    def __init__(self, baseset=None):
        self.modules = {}
        if baseset:
            self.modules.update(baseset.modules)
    def add(self, module):
        '''add a Module object to this set of modules'''
        self.modules[module.name] = module
    def addmod(self, *args, **kwargs):
        mod = apply(Module, args, kwargs)
        self.add(mod)

    # functions for handling dep expansion
    def __expand_mod_list(self, modlist):
        '''expands a list of names to a list of Module objects.  Expands
        MetaModule objects as expected.  Does not handle loops in task
        deps''' #"
        ret = []
        for modname in modlist:
            mod = self.modules[modname]
            if isinstance(mod, MetaModule):
                ret = ret + self.__expand_mod_list(mod.modules)
            else:
                ret.append(mod)
        return ret
        
    def get_module_list(self, seed):
        '''gets a list of module objects (in correct dependency order)
        needed to build the modules in the seed list''' #"
        module_list = self.__expand_mod_list(seed)
        i = 0
        while i < len(module_list):
            # make sure dependencies are built first
            depadd = []
            for depmod in self.__expand_mod_list(module_list[i].dependencies):
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
    def __init__(self, cvsroot, modulelist, autogenargs=None,
                 prefix=None, checkoutroot=None, makeargs=None):
        self.modulelist = modulelist
        self.autogenargs = autogenargs
        self.makeargs = makeargs
        self.makeargs = ''
        self.prefix = prefix
        self.module_num = 0

        interface.frontend.setModuleList(modulelist)
        
        if not self.autogenargs:
            self.autogenargs = '--disable-static --disable-gtk-doc'
        if not self.makeargs:
            self.makeargs = ''
        if not self.prefix:
            self.prefix = '/opt/gtk2'

        if not checkoutroot:
            checkoutroot = os.path.join(os.environ['HOME'], 'cvs','gnome')
        self.checkoutroot = checkoutroot
        self.cvsroot = cvs.CVSRoot(cvsroot, checkoutroot)

        assert os.access(self.prefix, os.R_OK|os.W_OK|os.X_OK), \
               'install prefix must be writable'

    def _setAction(self, action, module):
        interface.frontend.setAction(action, module, self.module_num)

    def _message(self, msg, module):
        interface.frontend.message(msg, module)

    def _execute(self, command):
        interface.frontend.printToBuildOutput(command)
        return interface.execute(command)

    def _cvscheckout(self, module, force_checkout=0):
        self._setAction('Checking out', module)

        if module.cvsroot:
            cvsroot = cvs.CVSRoot(module.cvsroot, self.checkoutroot)
        else:
            cvsroot = self.cvsroot

        if force_checkout:
            return cvsroot.checkout(module.name, module.revision,
                                    module.checkoutdir)
        else:
            return cvsroot.update(module.name, module.revision,
                                  module.checkoutdir)

    def _configure(self, module):
        checkoutdir = self.cvsroot.getcheckoutdir(module.name,
                                                  module.checkoutdir)
        os.chdir(checkoutdir)
        self._setAction('Configuring', module)
        cmd = './autogen.sh --prefix %s %s %s' % \
              (self.prefix, self.autogenargs, module.autogen_args())
        return self._execute(cmd)

    def _makeclean(self, module):
        checkoutdir = self.cvsroot.getcheckoutdir(module.name,
                                                  module.checkoutdir)
        os.chdir(checkoutdir)
        self._setAction('Cleaning', module)
        return self._execute('make %s clean' % self.makeargs)

    def _make(self, module):
        checkoutdir = self.cvsroot.getcheckoutdir(module.name,
                                                  module.checkoutdir)
        os.chdir(checkoutdir)
        self._setAction('Making', module)
        return self._execute('make %s' % self.makeargs)

    def _makeinstall(self, module):
        checkoutdir = self.cvsroot.getcheckoutdir(module.name,
                                                  module.checkoutdir)
        os.chdir(checkoutdir)
        self._setAction('Installing', module)
        return self._execute('make %s install' % self.makeargs)

    ERR_RERUN = 0
    ERR_CONT = 1
    ERR_GIVEUP = 2
    ERR_CONFIGURE = 3
    def _handle_error(self, module, stage):
        checkoutdir = self.cvsroot.getcheckoutdir(module.name, module.checkoutdir);
        return interface.frontend.handle_error(module,stage,checkoutdir,self.module_num,len(self.modulelist))

    def build(self, cvsupdate=1, alwaysautogen=0, makeclean=0, nobuild=0,
              skip=(), interact=1, startat=None):
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

        self.module_num = 0
        for module in self.modulelist:
            self.module_num = self.module_num + 1
            if module.name in skip: continue
            force_configure = 0

            if startat:
                if module.name == startat:
                    startat = None
                else:
                    continue
            # check if any dependencies have been poisoned
            poisoned = 0
            for dep in module.dependencies:
                if dep in poison:
                    self._message('module %s not built due to non buildable %s'
                                  % (module.name, dep), module)
                    poisoned = 1
            if poisoned:
                poison.append(module.name)
                continue

            state = STATE_CHECKOUT
            while state != STATE_DONE:
                ret = 0
                next_state = STATE_DONE
                if state == STATE_CHECKOUT:
                    if cvsupdate:
                        ret = self._cvscheckout(module, force_checkout=force_configure)

                    if nobuild:
                        next_state = STATE_DONE
                    else:
                        next_state = STATE_CONFIGURE
                    checkoutdir = self.cvsroot.getcheckoutdir(module.name,
                                                            module.checkoutdir)
                    if ret == 0:
                        if not os.path.exists(checkoutdir):
                            self._message("checkout doesn't exist :(", module)
                            poison.append(module.name)
                            next_state = STATE_DONE

                elif state == STATE_CONFIGURE:
                    if not os.path.exists('Makefile') or force_configure or alwaysautogen:
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
                        self._message('giving up on %s' % module.name, module)
                        err = self.ERR_GIVEUP # non interactive
                    if err == self.ERR_CONT:
                        state = next_state
                    elif err == self.ERR_CONFIGURE:
                        state = STATE_CHECKOUT
                        force_configure = 1
                        pass
                    elif err == self.ERR_RERUN:
                        pass # redo stage
                    elif err == self.ERR_GIVEUP:
                        poison.append(module.name)
                        state = STATE_DONE

        if len(poison) == 0:
            self._message('success', module)
        else:
            self._message('the following modules were not built', module)
            interface.frontend.print_unbuilt_modules(poison)
