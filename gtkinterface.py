# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2002 Seth Nickell
#
#   gtkinterface.py: GTK frontend for jhbuild
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
import gtk
import gtk.glade

user_shell = os.environ.get('SHELL', '/bin/sh')

class Interface:

    current_module = None
    
    def setModuleList(self, list):
        self.module_list = list

    def runEventLoop(self):
        while (gtk.events_pending()):
            gtk.main_iteration()

    def pauseBuild(self):
        return self.pause_button.get_active()

    def _createWindow(self):
        self.glade = gtk.glade.XML("/gnome-source/jhbuild/jhbuild.glade")
        
        self.window               = self.glade.get_widget("BuildWindow")
        self.build_progress       = self.glade.get_widget("BuildProgressBar")
        self.build_text_view      = self.glade.get_widget("BuildText")
        self.current_action_label = self.glade.get_widget("CurrentActionLabel")
        self.current_module_label = self.glade.get_widget("CurrentModuleLabel")
        self.pause_button         = self.glade.get_widget("PauseButton")
        self.expander_button      = self.glade.get_widget("ExpanderButton")
        self.expander_arrow       = self.glade.get_widget("ExpanderArrow")
        
	self.window.connect('destroy', lambda win: gtk.main_quit())        
        #self.expander_button.connect('activate', 
                                     
        self.tag_table = gtk.TextTagTable()
        self.build_text = gtk.TextBuffer(self.tag_table)
        self.warning_tag = self.build_text.create_tag("warning")
        self.warning_tag.set_property("foreground", "red")
        self.build_text_view.set_buffer(self.build_text)
        self.build_text_view.set_wrap_mode(gtk.WRAP_WORD)
        self.iter = self.build_text.get_end_iter()
        
        self.window.show_all()
        
    def __init__(self):
        self._createWindow()

    def setAction(self, action, module, module_num):
        if ((self.current_module != module) and (self.current_module != None)):
            self.current_module._build_text_buffer = self.build_text
            self.build_text = gtk.TextBuffer(self.tag_table)
            self.build_text_view.set_buffer(self.build_text)
            self.iter = self.build_text.get_end_iter()            
        self.current_module = module
        
        num_modules = len(self.module_list)
        if module_num > 0:
            self.build_progress.set_fraction(module_num / float(num_modules))
            self.build_progress.set_text('%d of %d modules' % (module_num, num_modules))
        else:
            percent = ''

        self.window.set_title('[%d/%d] %s %s' % (module_num, num_modules, action, module.name))
        self.current_action_label.set_text ('%s:' %action)
        self.current_module_label.set_text (module.name)
                              
    def message(self, msg, modulenum):
        return
        #dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK, message_format=msg)
        #dialog.run()
        #dialog.hide()
        
    def printToBuildOutput(self, output):
        self.build_text.insert(self.iter, output, -1)
        self.iter = self.build_text.get_end_iter()
        self.build_text_view.scroll_to_iter(self.iter, 0, True, 0, 1)

    def printToWarningOutput(self, output):
        self.build_text.insert_with_tags_by_name(self.iter, output, "warning")

    def print_unbuilt_modules(self, unbuilt_modules):
        for module in unbuilt_modules:
            print module
        print

    ERR_RERUN = 0
    ERR_CONT = 1
    ERR_GIVEUP = 2
    ERR_CONFIGURE = 3
    RUN_SHELL = 10
    def handle_error(self, module, stage, checkoutdir, modulenum, nummodules):
        '''Ask the user what to do about an error.

        Returns one of ERR_RERUN, ERR_CONT or ERR_GIVEUP.''' #"

        self.message('error during %s for module %s' % (stage, module.name),
                     modulenum, nummodules)

        dialog = gtk.Dialog('error during %s for module %s' % (stage, module.name))
        dialog.add_button('_Try %s Again' % stage, self.ERR_RERUN)
        dialog.add_button('_Rebuild Module', self.ERR_CONFIGURE)
        dialog.add_button('_Skip Module', self.ERR_GIVEUP)
        dialog.add_button('_Ignore Error', self.ERR_CONT)
        
        text_view = gtk.TextView()
        text_view.set_buffer(self.build_text)
        text_view.set_wrap_mode(gtk.WRAP_WORD)

        scroller = gtk.ScrolledWindow()
        scroller.add(text_view)
        dialog.vbox.pack_start(scroller)
        
        scroller.set_size_request(-1, 250)
        scroller.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroller.set_shadow_type(gtk.SHADOW_IN)
        scroller.set_border_width(12)

        dialog.show_all()

        text_view.scroll_to_iter(self.build_text.get_end_iter(), 0, True, 0, 1)
        
        value = dialog.run()
        dialog.hide()
        
        return value
