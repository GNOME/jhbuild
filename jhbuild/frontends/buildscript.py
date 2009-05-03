# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2003-2004  Seth Nickell
#
#   buildscript.py: base class of the various interface types
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

from jhbuild.utils import packagedb
from jhbuild.errors import FatalError, CommandError, SkipToPhase, SkipToEnd

class BuildScript:
    def __init__(self, config, module_list):
        if self.__class__ is BuildScript:
            raise NotImplementedError('BuildScript is an abstract base class')

        self.modulelist = module_list
        self.module_num = 0

        self.config = config

        if not os.path.exists(self.config.checkoutroot):
            try:
                os.makedirs(self.config.checkoutroot)
            except OSError:
                raise FatalError(
                        _('checkout root (%s) can not be created') % self.config.checkoutroot)
        if not os.access(self.config.checkoutroot, os.R_OK|os.W_OK|os.X_OK):
            raise FatalError(_('checkout root (%s) must be writable') % self.config.checkoutroot)

        if self.config.copy_dir and not os.path.exists(self.config.copy_dir):
            try:
                os.makedirs(self.config.copy_dir)
            except OSError:
                raise FatalError(
                        _('checkout copy dir (%s) can not be created') % self.config.copy_dir)
            if not os.access(self.config.copy_dir, os.R_OK|os.W_OK|os.X_OK):
                raise FatalError(_('checkout copy dir (%s) must be writable') % self.config.copy_dir)

        packagedbdir = os.path.join(self.config.prefix, 'share', 'jhbuild')
        try:
            if not os.path.isdir(packagedbdir):
                os.makedirs(packagedbdir)
        except OSError:
            raise FatalError(_('could not create directory %s') % packagedbdir)
        self.packagedb = packagedb.PackageDB(os.path.join(packagedbdir,
                                                          'packagedb.xml'))

    def execute(self, command, hint=None, cwd=None, extra_env=None):
        '''Executes the given command.

        If an error occurs, CommandError is raised.  The hint argument
        gives a hint about the type of output to expect.
        '''
        raise NotImplementedError

    def build(self):
        '''start the build of the current configuration'''
        self.start_build()
        
        failures = [] # list of modules that couldn't be built
        self.module_num = 0
        for module in self.modulelist:
            self.module_num = self.module_num + 1

            if self.config.min_time is not None:
                installdate = self.packagedb.installdate(module.name)
                if installdate > self.config.min_time:
                    self.message(_('Skipping %s (installed recently)') % module.name)
                    continue

            self.start_module(module.name)
            failed = False
            for dep in module.dependencies:
                if dep in failures:
                    if self.config.nopoison:
                        self.message(_('module %(mod)s will be build even though %(dep)s failed')
                                     % { 'mod':module.name, 'dep':dep })
                    else:
                        self.message(_('module %(mod)s not built due to non buildable %(dep)s')
                                     % { 'mod':module.name, 'dep':dep })
                        failed = True
            if failed:
                failures.append(module.name)
                self.end_module(module.name, failed)
                continue

            phases = self.get_build_phases(module)
            phase = None
            num_phase = 0
            while num_phase < len(phases):
                last_phase, phase = phase, phases[num_phase]
                try:
                    if module.skip_phase(self, phase, last_phase):
                        num_phase += 1
                        continue
                except SkipToEnd:
                    break

                self.start_phase(module.name, phase)
                error = None
                try:
                    error, altphases = module.run_phase(self, phase)
                except SkipToPhase, e:
                    try:
                        num_phase = phases.index(e.phase)
                    except ValueError:
                        break
                    continue
                except SkipToEnd:
                    break
                finally:
                    self.end_phase(module.name, phase, error)

                if error:
                    try:
                        nextphase = phases[num_phase+1]
                    except IndexError:
                        nextphase = None
                    newphase = self.handle_error(module, phase,
                                                 nextphase, error,
                                                 altphases)
                    if newphase == 'fail':
                        failures.append(module.name)
                        failed = True
                        break
                    if newphase is None:
                        break
                    if newphase in phases:
                        num_phase = phases.index(newphase)
                    else:
                        # requested phase is not part of the plan, we insert
                        # it, then fill with necessary phases to get back to
                        # the current one.
                        filling_phases = self.get_build_phases(module, targets=[phase])
                        canonical_new_phase = newphase
                        if canonical_new_phase.startswith('force_'):
                            # the force_ phases won't appear in normal build
                            # phases, so get the non-forced phase
                            canonical_new_phase = canonical_new_phase[6:]

                        if canonical_new_phase in filling_phases:
                            filling_phases = filling_phases[
                                    filling_phases.index(canonical_new_phase)+1:-1]
                        phases[num_phase:num_phase] = [newphase] + filling_phases

                        if phases[num_phase+1] == canonical_new_phase:
                            # remove next phase if it would just be a repeat of
                            # the inserted one
                            del phases[num_phase+1]
                else:
                    num_phase += 1

            self.end_module(module.name, failed)
        self.end_build(failures)
        if failures:
            return 1
        return 0

    def get_build_phases(self, module, targets=None):
        '''returns the list of required phases'''
        if targets:
            tmp_phases = targets[:]
        else:
            tmp_phases = self.config.build_targets[:]
        i = 0
        while i < len(tmp_phases):
            phase = tmp_phases[i]
            depadd = []
            try:
                phase_method = getattr(module, 'do_' + phase)
            except AttributeError:
                # unknown phase for this module type, simply skip
                del tmp_phases[i]
                continue
            if hasattr(phase_method, 'depends'):
                for subphase in phase_method.depends:
                    if subphase not in tmp_phases[:i+1]:
                        depadd.append(subphase)
            if depadd:
                tmp_phases[i:i] = depadd
            else:
                i += 1

        # remove duplicates
        phases = []
        for phase in tmp_phases:
            if not phase in phases:
                phases.append(phase)

        return phases

    def start_build(self):
        '''Hook to perform actions at start of build.'''
        pass
    def end_build(self, failures):
        '''Hook to perform actions at end of build.
        The argument is a list of modules that were not buildable.'''
        pass
    def start_module(self, module):
        '''Hook to perform actions before starting a build of a module.'''
        pass
    def end_module(self, module, failed):
        '''Hook to perform actions after finishing a build of a module.
        The argument is true if the module failed to build.'''
        pass
    def start_phase(self, module, phase):
        '''Hook to perform actions before starting a particular build phase.'''
        pass
    def end_phase(self, module, phase, error):
        '''Hook to perform actions after finishing a particular build phase.
        The argument is a string containing the error text if something
        went wrong.'''
        pass

    def message(self, msg, module_num=-1):
        '''Display a message to the user'''
        raise NotImplementedError

    def set_action(self, action, module, module_num=-1, action_target=None):
        '''inform the buildscript of a new stage of the build'''
        raise NotImplementedError

    def handle_error(self, module, phase, nextphase, error, altphases):
        '''handle error during build'''
        raise NotImplementedError
