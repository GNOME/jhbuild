# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2003-2004  Seth Nickell
#
#   gtkui.py: build logic for a GTK interface
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

import pygtk
pygtk.require('2.0')

import sys
import time
import os
import signal
import fcntl
import select
import subprocess

import gobject
import gtk
import gtk.glade

#FIXME: would be nice if we ran w/o GConf, do a try...except block around
#       the import and then set have_gconf to false
import gconf
have_gconf = True

import buildscript
import jhbuild.moduleset
from jhbuild.modtypes import MetaModule
from jhbuild.errors import CommandError

def get_glade_filename():
    return os.path.join(os.path.dirname(__file__), 'jhbuild.glade')

class Configuration:
    def __init__(self, config, args):
        self.config = config
        self.args = args

        glade_filename = get_glade_filename()

        # Fetch widgets out of the Glade
        self.glade = gtk.glade.XML(glade_filename)        
        self.window               = self.glade.get_widget("ConfigWindow")
        self.meta_modules_list    = self.glade.get_widget("ConfigMetaModules")
        self.start_module_menu    = self.glade.get_widget("ConfigStartModule")
        self.run_autogen_checkbox = self.glade.get_widget("ConfigRunAutogen")
        self.cvs_update_checkbox  = self.glade.get_widget("ConfigCVSUpdate")
        self.no_build_checkbox    = self.glade.get_widget("ConfigNoBuild")
        self.start_build_button   = self.glade.get_widget("ConfigBuildButton")
        self.cancel_button        = self.glade.get_widget("ConfigCancelButton")

        # Get settings for the checkboxes, etc
        self._get_default_settings()

        # Hook up the buttons / checkboxes
        self.start_build_button.connect('clicked', lambda button: gtk.main_quit())
        self.cancel_button.connect('clicked', lambda button: sys.exit(-1))
        self.run_autogen_checkbox.connect('toggled', self._autogen_checkbox_toggled)
        self.cvs_update_checkbox.connect('toggled', self._cvs_update_checkbox_toggled)
        self.no_build_checkbox.connect('toggled', self._no_build_checkbox_toggled)
        #self.start_module_menu.connect('clicked', self._start_module_menu_clicked)
        
        # Get the list of meta modules
        self.module_set = jhbuild.moduleset.load(config)
        full_module_list = self.module_set.get_full_module_list()
        self.meta_modules = []
        self.name_to_meta_module = {}
        for possible_meta_module in full_module_list:
            if isinstance(possible_meta_module, MetaModule):
                print "Found meta module %s" % possible_meta_module.name
                self.meta_modules.append(possible_meta_module)
                self.name_to_meta_module[possible_meta_module.name] = possible_meta_module

        self._create_meta_modules_list_view(self.meta_modules)
        
        self._build_start_module_menu()

    def run(self):
        self.window.show_all()
        gtk.main()
        self.window.hide()
        self._set_default_settings()
        return (self.module_list, self.start_at_module, self.run_autogen, self.cvs_update,
                self.no_build)

    def _get_default_settings(self):
        if have_gconf:
            client = gconf.client_get_default()
            self.run_autogen      = client.get_bool("/apps/jhbuild/always_run_autogen")
            self.cvs_update       = client.get_bool("/apps/jhbuild/update_from_cvs")
            self.no_build         = client.get_bool("/apps/jhbuild/no_build")
            self.selected_modules = client.get_list("/apps/jhbuild/modules_to_build", gconf.VALUE_STRING)
            self.start_at_module  = client.get_string("/apps/jhbuild/start_at_module")
        else:
            self.run_autogen = False
            self.cvs_update  = True
            self.no_build    = False

        self.run_autogen_checkbox.set_active(self.run_autogen)
        self.cvs_update_checkbox.set_active(self.cvs_update)
        self.no_build_checkbox.set_active(self.no_build)

    def _set_default_settings(self):
        if have_gconf:
            client = gconf.client_get_default()
            client.set_bool("/apps/jhbuild/always_run_autogen", self.run_autogen)
            client.set_bool("/apps/jhbuild/update_from_cvs", self.cvs_update)
            client.set_bool("/apps/jhbuild/no_build", self.no_build)
            client.set_list("/apps/jhbuild/modules_to_build", gconf.VALUE_STRING, self.selected_modules)
            if self.start_at_module:
                client.set_string("/apps/jhbuild/start_at_module", self.start_at_module)
            else:
                client.set_string("/apps/jhbuild/start_at_module", "")
                
            print ("Gconf setting for update from CVS is %d" % self.cvs_update)
            
        
    def _meta_module_toggled(self, cell, path, model):
        iter = model.get_iter((int(path),))
        build = model.get_value(iter, 0)
        build = not build
        model.set(iter, 0, build)
        self.selected_modules = self._get_selected_meta_modules()
        self._build_start_module_menu()
        
    def _create_meta_modules_list_view(self, meta_modules):
        self.model = gtk.ListStore(gobject.TYPE_BOOLEAN, gobject.TYPE_STRING)
        self.meta_modules_list.set_model(self.model)
        
        for module in meta_modules:
            iter = self.model.append()
            if self.selected_modules:
                selected = (module.name in self.selected_modules)
            else:
                selected = False
            self.model.set(iter, 0, selected, 1, module.name)

        renderer = gtk.CellRendererToggle()
        renderer.connect('toggled', self._meta_module_toggled, self.model)
        column = gtk.TreeViewColumn('Build', renderer, active=0)
        column.set_clickable(True)
        self.meta_modules_list.append_column(column)

        column = gtk.TreeViewColumn('Module Group', gtk.CellRendererText(), text=1)
        self.meta_modules_list.append_column(column)        

    def _get_selected_meta_modules(self):
        modules = []
        iter = self.model.get_iter_first()

        while iter:
            build = self.model.get_value(iter, 0)
            if build:
                name = self.model.get_value(iter, 1)
                module = self.name_to_meta_module[name]
                if module:
                    modules.append(module.name)
            iter = self.model.iter_next(iter)

        return modules

    
    def _build_start_module_menu(self):
        if not self.selected_modules:
            return
        
        self.module_list = self.module_set.get_module_list(self.selected_modules, self.config.skip)

        menu = gtk.Menu()
        menu.connect('selection-done', self._start_module_menu_clicked)
        
        selected_item_number = None
        i = 0
        for module in self.module_list:
            menu_item = gtk.MenuItem(module.name)
            menu.append(menu_item)
            if module.name == self.start_at_module:
                selected_item_number = i
            i = i + 1
            
        self.start_module_menu.set_menu (menu)

        if selected_item_number:
            self.start_module_menu.set_history(selected_item_number)
        else:
            if self.module_list:
                self.start_at_module = self.module_list[0].name
            else:
                self.start_at_module = None
            
        menu.show_all()

    def _start_module_menu_clicked(self, option_menu):
        number = self.start_module_menu.get_history()
        if self.module_list:
            item = self.module_list[number]
            self.start_at_module = item.name
        else:
            self.start_at_module = None

    def _autogen_checkbox_toggled(self, checkbox):
        self.run_autogen = not self.run_autogen

    def _cvs_update_checkbox_toggled(self, checkbox):
        self.cvs_update = not self.cvs_update

    def _no_build_checkbox_toggled(self, checkbox):
        self.no_build = not self.no_build

def optionmenu_get_history(self):
    menu = self.get_menu()
    children = menu.children()
    item = menu.get_active()

    for i in range(len(children)):
        if children[i] == item:
            break

    return i

class GtkBuildScript(buildscript.BuildScript):
    def __init__(self, config, module_list):
        buildscript.BuildScript.__init__(self, config, module_list)
        self.current_module = None
        self._createWindow()
        if have_gconf:
            self.terminal_command = self._getTerminalCommand()
        else:
            self.terminal_command = "gnome-terminal"

    def _getTerminalCommand(self):
        client = gconf.client_get_default()
        command = client.get_string("/desktop/gnome/applications/terminal/exec")
        return command
        
    def message(self, msg, module_num = -1):
        '''shows a message to the screen'''
        
        if module_num == -1:
            module_num = self.module_num
        dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK, message_format=msg)
        dialog.run()
        dialog.hide()        
        return

    def set_action(self, action, module, module_num=-1, action_target=None):
        if module_num == -1:
            module_num = self.module_num
        if not action_target:
            action_target = module.name
        if self.current_module != module and self.current_module != None:
            self.current_module._build_text_buffer = self.build_text
            self.build_text = gtk.TextBuffer(self.tag_table)
            self.build_text_view.set_buffer(self.build_text)
            self.iter = self.build_text.get_end_iter()            
        self.current_module = module

        num_modules = len(self.modulelist)
        if module_num > 0:
            self.build_progress.set_fraction(module_num / float(num_modules))
            self.build_progress.set_text('%d of %d modules'
                                         % (module_num, num_modules))

        self.window.set_title('[%d/%d] %s %s' % (module_num, num_modules, action, module.name))
        self.current_status_label.set_text('%s %s' % (action, module.name))

    def _runEventLoop(self):
        while gtk.events_pending():
            gtk.main_iteration()

    def _printToBuildOutput(self, output):
        self.iter = self.build_text.get_end_iter()
        self.build_text.insert(self.iter, output)
        self.build_text.move_mark (self.ins_mark, self.iter)
        self.build_text_view.scroll_to_mark (self.ins_mark, 0.0, True, 0.5, 0.5)
        
    def _printToWarningOutput(self, output):
        self.build_text.insert_with_tags_by_name(self.iter, output, "warning")

    def _pauseBuild(self):
        return self.pause_button.get_active()

    def _makeNonBlocking(self, fd):
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NDELAY)
        

    def execute(self, command, hint=None, cwd=None, extra_env=None):
        '''executes a command, and returns the error code'''
        return_code = -1

        kws = {
            'close_fds': True,
            'shell': isinstance(command, (str,unicode)),
            'stdin': subprocess.PIPE,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            }

        if cwd is not None:
            kws['cwd'] = cwd

        if extra_env is not None:
            kws['env'] = os.environ.copy()
            kws['env'].update(extra_env)

        try:
            p = subprocess.Popen(command, **kws)
        except OSError, e:
            raise CommandError(str(e))

        p.stdin.close()
        self._makeNonBlocking(p.stdout)
        self._makeNonBlocking(p.stderr)

        build_paused = False
        read_set = [p.stdout, p.stderr]

        while read_set:
            # Allow the frontend to get a little time
            self._runEventLoop()

            rlist, wlist, xlist = select.select(read_set, [], [], 0)

            if p.stdout in rlist:
                chunk = p.stdout.read()
                if chunk == '':
                    p.stdout.close()
                    read_set.remove(p.stdout)
                self._printToBuildOutput(chunk)

            if p.stderr in rlist:
                chunk = p.stderr.read()
                if chunk == '':
                    p.stderr.close()
                    read_set.remove(p.stderr)
                self._printToWarningOutput(chunk)

            # See if we should pause the current command
            if not build_paused and self._pauseBuild():
                print ("Pausing this guy, sending os.kill to %d", p.pid)
                os.kill(p.pid, signal.SIGSTOP)
                build_paused = True
            elif build_paused and not self._pauseBuild():
                print ("Continuing him")
                os.kill(p.pid, signal.SIGCONT)
                build_paused = False

            time.sleep(0.05)

        return p.wait()

    def start_build(self):
        self.window.show_all()
    def end_build(self, failures):
        if len(failures) == 0:
            self.message('success')
        else:
            self.message('the following modules were not built:\n%s'
                         % ', '.join(failures))
    def start_module(self, module):
        # Remember where we are in case something fails
        if have_gconf:
            client = gconf.client_get_default()
            client.set_string("/apps/jhbuild/start_at_module", module)

    def handle_error(self, module, state, nextstate, error, altstates):
        '''Ask the user what to do about an error.

        Returns one of ERR_RERUN, ERR_CONT or ERR_GIVEUP.''' #"

        if not self.config.interact:
            return 'fail'

        dialog = gtk.Dialog('Error during %s for module %s' % (state, module.name))
        dialog.add_button('_Try %s Again' % state, 1)
        dialog.add_button('_Ignore Error', 2)
        dialog.add_button('_Skip Module', 3)
        dialog.add_button('_Terminal', 4)

        for i, altstate in enumerate(altstates):
            dialog.add_button('Go to %s' % altstate, i + 5)

        text_view = gtk.TextView()
        text_view.set_buffer(self.build_text)
        text_view.set_wrap_mode(gtk.WRAP_WORD)

        scroller = gtk.ScrolledWindow()
        scroller.add(text_view)
        dialog.vbox.pack_start(scroller)

        scroller.set_size_request(-1, 250)
        scroller.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroller.set_shadow_type(gtk.SHADOW_IN)
        scroller.set_border_width(12)
        
        while True:

            #self.message('error during %s for module %s' % (state, module.name))

            text_view.scroll_to_iter(self.build_text.get_end_iter(), 0.0, True, 0.5, 0.5)
            dialog.show_all()

            val = dialog.run()

            if val != 4:
                dialog.hide()
            # If the dialog was destroyed, interpret that as try again.
            if val in (1, gtk.RESPONSE_NONE, gtk.RESPONSE_DELETE_EVENT):
                return state
            elif val == 2:
                return nextstate
            elif val == 3:
                return 'fail'
            elif val == 4:
                command = 'cd %s; %s' % (module.get_builddir(self),
                                         self.terminal_command)
                os.system(command)
            else:
                return altstates[val - 5]

    def _createWindow(self):
	glade_filename = get_glade_filename()
        self.glade = gtk.glade.XML(glade_filename)
        
        self.window               = self.glade.get_widget("BuildWindow")
        self.build_progress       = self.glade.get_widget("BuildProgressBar")
        self.build_text_view      = self.glade.get_widget("BuildText")
        self.current_status_label = self.glade.get_widget("CurrentStatusLabel")
        self.pause_button         = self.glade.get_widget("BuildPauseButton")
        self.cancel_button        = self.glade.get_widget("BuildCancelButton")
        #self.expander_button      = self.glade.get_widget("ExpanderButton")
        #self.expander_arrow       = self.glade.get_widget("ExpanderArrow")
        
	self.window.connect('destroy', lambda win: sys.exit())
        self.cancel_button.connect('clicked', lambda button: sys.exit())
        #self.expander_button.connect('activate', 
                                     
        self.tag_table = gtk.TextTagTable()
        self.build_text = gtk.TextBuffer(self.tag_table)
        self.warning_tag = self.build_text.create_tag("warning")
        self.warning_tag.set_property("foreground", "red")
        self.build_text_view.set_buffer(self.build_text)
        self.build_text_view.set_wrap_mode(gtk.WRAP_WORD)
        self.iter = self.build_text.get_end_iter()
	self.ins_mark = self.build_text.create_mark ("jhbuild-mark", self.iter, True);
        
BUILD_SCRIPT = GtkBuildScript
