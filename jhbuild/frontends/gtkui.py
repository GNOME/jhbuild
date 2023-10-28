# jhbuild - a tool to ease building collections of source packages
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Pango, GLib

try:
    gi.require_version('Vte', '2.91')
    from gi.repository import Vte
except (ImportError, ValueError):
    Vte = None

import sys
import time
import os
import signal
import fcntl
import select
import subprocess

from . import buildscript
import jhbuild.moduleset
from jhbuild.modtypes import MetaModule
from jhbuild.errors import CommandError
from jhbuild.utils import notify, _

from .terminal import t_bold, t_reset


class ExitRequestedException(Exception):
    pass


class AppWindow(Gtk.Window, buildscript.BuildScript):
    default_module_iter = None
    active_iter = None
    child_pid = None
    error_resolution = None
    preference_dialog = None

    def __init__(self, config, module_list=None, module_set=None):
        self.orig_modulelist = module_list
        self.module_set = jhbuild.moduleset.load(config)
        buildscript.BuildScript.__init__(self, config, module_list, module_set=self.module_set)
        self.config = config
        Gtk.Window.__init__(self)
        self.set_resizable(False)
        theme = Gtk.IconTheme.get_default()
        if theme.has_icon('applications-development'):
            self.set_default_icon_list([
                    theme.load_icon('applications-development', 16, 0),
                    theme.load_icon('applications-development', 24, 0),
                    theme.load_icon('applications-development', 32, 0),
                    theme.load_icon('applications-development', 48, 0),
                    theme.load_icon('applications-development', 64, 0),
                    theme.load_icon('applications-development', 128, 0)]
                    )
        self.set_title('JHBuild')

        self.create_modules_list_model()
        self.create_ui()
        self.notify = notify.Notify(config)

        if self.default_module_iter:
            self.module_combo.set_active_iter(self.default_module_iter)

        self.connect('delete-event', self.on_delete_event)

    def create_modules_list_model(self):
        # name, separator, startat
        self.modules_list_model = Gtk.ListStore(str, bool, str)
        full_module_list = self.module_set.get_full_module_list()
        for module in full_module_list:
            if isinstance(module, MetaModule):
                if module.name.endswith('-deprecations'):
                    # skip the deprecation meta modules, nobody want them
                    continue
                iter = self.modules_list_model.append((module.name, False, ''))
        self.modules_list_model.append(('', True, ''))
        self.modules_list_model.append((_('Others...'), False, ''))

        for module in self.config.modules:
            iter = self.add_extra_module_to_model(module)
            if not self.default_module_iter:
                self.default_module_iter = iter

    def add_extra_module_to_model(self, module, startat=''):
        # lookup selected module in current modules list
        for row in self.modules_list_model:
            row_value = self.modules_list_model.get(row.iter, 0)[0]
            if row_value == module:
                self.modules_list_model.set_value(row.iter, 2, startat)
                return row.iter

        # add selected module in the list
        if self.modules_list_model.get(self.modules_list_model[-3].iter, 1)[0] is False:
            # there is no user-added modules at the moment, add a separator row
            self.modules_list_model.insert_before(
                    self.modules_list_model[-2].iter, ('', True, ''))
        iter = self.modules_list_model.insert_before(
                self.modules_list_model[-2].iter, (module, False, startat))
        return iter

    quit = False
    def on_delete_event(self, *args):
        self.quit = True
        self.hide()
        if self.child_pid:
            os.kill(self.child_pid, signal.SIGKILL)
        if Gtk.main_level():
            Gtk.main_quit()

    def create_ui(self):
        self.set_border_width(5)
        app_vbox = Gtk.VBox(spacing=5)

        self.module_hbox = Gtk.HBox(spacing=5)
        app_vbox.pack_start(self.module_hbox, False, False, 9)

        label = Gtk.Label()
        label.set_markup('<b>%s</b>' % _('Choose Module:'))
        self.module_hbox.pack_start(label, False, False, 0)

        self.module_combo = Gtk.ComboBox.new_with_model(self.modules_list_model)
        cell = Gtk.CellRendererText()
        self.module_combo.pack_start(cell, True)
        self.module_combo.add_attribute(cell, 'text', 0)
        self.module_combo.changed_signal_id = self.module_combo.connect(
                'changed', self.on_module_selection_changed_cb)

        self.module_combo.set_row_separator_func(lambda x,y: x.get(y, 1)[0])
        self.module_hbox.pack_start(self.module_combo, False, True, 0)

        separator = Gtk.VSeparator()
        self.module_hbox.pack_start(separator, False, True, 0)
        preferences = Gtk.Button(stock=Gtk.STOCK_PREFERENCES)
        preferences.connect('clicked', self.on_preferences_cb)
        self.module_hbox.pack_start(preferences, False, True, 0)

        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_text(_('Build Progress'))
        app_vbox.pack_start(self.progressbar, False, True, 0)

        expander = Gtk.Expander.new(_('Terminal'))
        expander.set_expanded(False)
        app_vbox.pack_start(expander, False, False, 0)
        sclwin = Gtk.ScrolledWindow()
        sclwin.set_size_request(-1, 300)
        sclwin.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
        expander.add(sclwin)
        if Vte:
            self.terminal = Vte.Terminal()
            self.terminal.connect('child-exited', self.on_vte_child_exit_cb)
        else:
            os.environ['TERM'] = 'dumb' # avoid commands printing vt sequences
            self.terminal = Gtk.TextView()
            self.terminal.set_size_request(800, -1)
            textbuffer = self.terminal.get_buffer()
            terminal_bold_tag = textbuffer.create_tag('bold')
            terminal_bold_tag.set_property('weight', Pango.Weight.BOLD)
            terminal_mono_tag = textbuffer.create_tag('mono')
            terminal_mono_tag.set_property('family', 'Monospace')
            terminal_stdout_tag = textbuffer.create_tag('stdout')
            terminal_stdout_tag.set_property('family', 'Monospace')
            terminal_stderr_tag = textbuffer.create_tag('stderr')
            terminal_stderr_tag.set_property('family', 'Monospace')
            terminal_stderr_tag.set_property('foreground', 'red')
            terminal_stdin_tag = textbuffer.create_tag('stdin')
            terminal_stdin_tag.set_property('family', 'Monospace')
            terminal_stdin_tag.set_property('style', Pango.Style.ITALIC)
            self.terminal.set_editable(False)
            self.terminal.set_wrap_mode(Gtk.WrapMode.CHAR)
        sclwin.add(self.terminal)
        self.terminal_sclwin = sclwin

        self.error_hbox = self.create_error_hbox()
        app_vbox.pack_start(self.error_hbox, False, False, 0)

        buttonbox = Gtk.HButtonBox()
        buttonbox.set_layout(Gtk.ButtonBoxStyle.END)
        app_vbox.pack_start(buttonbox, False, False, 0)

        # Translators: This is a button label (to start build)
        self.build_button = Gtk.Button(_('Start'))
        self.build_button.connect('clicked', self.on_build_cb)
        buttonbox.add(self.build_button)

        button = Gtk.Button(stock=Gtk.STOCK_HELP)
        button.connect('clicked', self.on_help_cb)
        buttonbox.add(button)
        buttonbox.set_child_secondary(button, True)

        app_vbox.show_all()
        self.error_hbox.hide()
        self.add(app_vbox)


    def create_error_hbox(self):
        error_hbox = Gtk.HBox(False, 8)
        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_DIALOG_ERROR, Gtk.IconSize.BUTTON)
        error_hbox.pack_start(image, False, False, 0)
        image.set_alignment(0.5, 0.5)

        vbox = Gtk.VBox(False, 6)
        error_hbox.pack_start (vbox, True, True, 0)

        self.error_label = Gtk.Label()
        vbox.pack_start(self.error_label, True, True, 0)
        self.error_label.set_use_markup(True)
        self.error_label.set_line_wrap(True)
        self.error_label.set_alignment(0, 0.5)

        # label, code
        second_hbox = Gtk.HBox()
        vbox.pack_start(second_hbox, True, True, 0)

        self.error_resolution_model = Gtk.ListStore(str, str)
        self.error_combo = Gtk.ComboBox.new_with_model(self.error_resolution_model)
        self.error_combo.connect('changed', self.on_error_resolution_changed_cb)
        self.error_combo.set_row_separator_func(lambda x,y: (x.get(y, 0)[0] == ''))
        cell = Gtk.CellRendererText()
        self.error_combo.pack_start(cell, True)
        self.error_combo.add_attribute(cell, 'markup', 0)
        second_hbox.pack_start(self.error_combo, True, True, 0)

        self.error_apply_button = Gtk.Button(stock = Gtk.STOCK_APPLY)
        self.error_apply_button.set_sensitive(False)
        self.error_apply_button.connect('clicked', self.on_resolution_apply_clicked)
        second_hbox.pack_start(self.error_apply_button, False, False, 0)

        return error_hbox

    def on_error_resolution_changed_cb(self, *args):
        iter = self.error_combo.get_active_iter()
        if not iter:
            return
        if not self.error_resolution_model.get(iter, 1)[0]:
            return
        self.error_apply_button.set_sensitive(True)

    def on_resolution_apply_clicked(self, *args):
        self.error_apply_button.set_sensitive(False)
        iter = self.error_combo.get_active_iter()
        if not iter:
            return
        self.error_resolution = self.error_resolution_model.get(iter, 1)[0]

    def on_help_cb(self, *args):
        Gtk.show_uri(Gdk.Screen.get_default(),
                'https://gnome.pages.gitlab.gnome.org/jhbuild/', Gtk.get_current_event_time())

    def on_preferences_cb(self, *args):
        if not self.preference_dialog:
            self.preference_dialog = PreferencesDialog(self)
        self.preference_dialog.show()
        self.preference_dialog.present()

    def on_build_cb(self, *args):
        if self.preference_dialog:
            self.preference_dialog.hide()
        if not self.orig_modulelist:
            modules = [self.modules_list_model.get(
                    self.module_combo.get_active_iter(), 0)[0]]

            self.modulelist = self.module_set.get_module_list(
                                    modules, self.config.skip,
                                    tags = self.config.tags,
                                    include_suggests=not self.config.ignore_suggests)
        else:
            self.orig_modulelist = None

        startat = self.modules_list_model.get(self.module_combo.get_active_iter(), 2)[0]
        if startat:
            while self.modulelist and self.modulelist[0].name != startat:
                del self.modulelist[0]
        self.build()

    def on_module_selection_changed_cb(self, *args):
        old_selected_iter = self.active_iter
        last_iter = self.modules_list_model[-1].iter
        self.active_iter = self.module_combo.get_active_iter()
        if self.modules_list_model.get_path(
                self.active_iter) != self.modules_list_model.get_path(last_iter):
            return
        # "Others..." got clicked, modal dialog to let the user select a
        # specific module
        current_module = self.modules_list_model.get(old_selected_iter, 0)[0]
        dlg = SelectModulesDialog(self, current_module)
        response = dlg.run()
        if response != Gtk.ResponseType.OK:
            dlg.destroy()
            self.module_combo.set_active_iter(old_selected_iter)
            return
        selected_module = dlg.selected_module
        startat = dlg.startat
        dlg.destroy()

        iter = self.add_extra_module_to_model(selected_module, startat)
        self.module_combo.set_active_iter(iter)

    def is_build_paused(self):
        return False

    def build(self):
        if Gtk.main_level() == 0 and self.orig_modulelist:
            # gtkui called from a "normal" command, not from jhbuild gui
            self.modulelist = self.orig_modulelist
            self.show()
            self.build_button.emit('clicked')
            while Gtk.events_pending():
                Gtk.main_iteration()
            try:
                return self.rc
            except AttributeError:
                return 1
        try:
            self.rc = buildscript.BuildScript.build(self)
        except ExitRequestedException:
            self.rc = 1
        return self.rc

    def start_build(self):
        self.build_button.set_sensitive(False)
        self.module_hbox.set_sensitive(False)

    def end_build(self, failures):
        self.progressbar.set_fraction(1)
        self.progressbar.set_text(_('Build Completed'))
        self.build_button.set_sensitive(True)
        self.module_hbox.set_sensitive(True)

    def start_phase(self, module, phase):
        self.notify.clear()

    def start_module(self, module):
        idx = [x.name for x in self.modulelist].index(module)
        self.progressbar.set_fraction((1.0*idx) / len(self.modulelist))
        if Vte:
            self.terminal.feed(('%s*** %s ***%s\n\r' % (t_bold, module, t_reset)).encode("utf-8"))
        else:
            textbuffer = self.terminal.get_buffer()
            textbuffer.insert_with_tags_by_name(
                    textbuffer.get_end_iter(), '*** %s ***\n' % module, 'bold')
            mark = textbuffer.create_mark('end', textbuffer.get_end_iter(), False)
            self.terminal.scroll_to_mark(mark, 0.05, True, 0.0, 1.0)

    def end_module(self, module, failed):
        self.error_hbox.hide()

    def set_action(self, action, module, module_num=-1, action_target=None):
        self.progressbar.set_text('%s %s' % (action, action_target or module.name))

    def message(self, msg, module_num=-1):
        pass

    def handle_error(self, module, phase, nextphase, error, altphases):
        summary = _('Error during phase %(phase)s of %(module)s') % {
            'phase': phase, 'module':module.name}
        try:
            error_message = error.args[0]
            self.message('%s: %s' % (summary, error_message))
        except Exception:
            error_message = None
            self.message(summary)

        if not self.is_active():
            self.set_urgency_hint(True)
        self.notify.notify(summary=summary, body=error_message,
                icon=Gtk.STOCK_DIALOG_ERROR, expire=5)

        self.error_label.set_markup('<b>%s</b>' % _(summary))
        self.error_resolution_model.clear()
        iter = self.error_resolution_model.append(
                ('<i>%s</i>' % _('Pick an Action'), ''))
        self.error_resolution_model.append(('', ''))
        self.error_resolution_model.append(
                (_('Rerun phase %s') % phase, phase))
        if nextphase:
            self.error_resolution_model.append(
                    (_('Ignore error and continue to %s') % nextphase, nextphase))
        else:
            self.error_resolution_model.append(
                    (_('Ignore error and continue to next module'), '_done'))
        self.error_resolution_model.append(
                (_('Give up on module'), 'fail'))
        for altphase in altphases:
            try:
                altphase_label = _(getattr(getattr(module, 'do_' + altphase), 'label'))
            except AttributeError:
                altphase_label = altphase
            self.error_resolution_model.append(
                    (_('Go to phase "%s"') % altphase_label, altphase))
        self.error_resolution_model.append(('', ''))
        self.error_resolution_model.append(
                (_('Open Terminal'), 'shell'))

        self.error_combo.set_active_iter(iter)
        self.error_hbox.set_sensitive(True)
        self.error_hbox.show_all()
        self.error_resolution = None

        while True:
            self.error_resolution = None
            while Gtk.events_pending():
                Gtk.main_iteration()
                if self.quit:
                    return 'fail'
            if not self.error_resolution:
                continue
            self.set_urgency_hint(False)
            if self.error_resolution == 'shell':
                # set back combobox to "Pick an action"
                self.error_combo.set_active_iter(iter)
                if os.fork() == 0:
                    cmd = ['gnome-terminal', '--working-directory', module.get_builddir(self)]
                    os.execvp('gnome-terminal', cmd)
                    sys.exit(0)
                continue
            if self.error_resolution == '_done':
                self.error_resolution = None
            # keep the error hox visible during all of this module duration
            self.error_hbox.set_sensitive(False)
            return self.error_resolution

    def execute(self, command, hint=None, cwd=None, extra_env=None):
        if not command:
            raise CommandError(_('No command given'))

        if isinstance(command, str):
            short_command = command.split()[0]
        else:
            short_command = command[0]

        if Vte is None:
            textbuffer = self.terminal.get_buffer()

            if isinstance(command, str):
                self.terminal.get_buffer().insert_with_tags_by_name(
                        textbuffer.get_end_iter(),
                        ' $ ' + command + '\n', 'stdin')
            else:
                self.terminal.get_buffer().insert_with_tags_by_name(
                        textbuffer.get_end_iter(),
                        ' $ ' + ' '.join(command) + '\n', 'stdin')

            kws = {
                'close_fds': True,
                'shell': isinstance(command, str),
                'stdin': subprocess.PIPE,
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                }

            if cwd is not None:
                kws['cwd'] = cwd

            if extra_env is not None:
                kws['env'] = os.environ.copy()
                kws['env'].update(extra_env)

            command = self._prepare_execute(command)

            try:
                p = subprocess.Popen(command, **kws)
            except OSError as e:
                raise CommandError(str(e))
            self.child_pid = p.pid

            p.stdin.close()

            def make_non_blocking(fd):
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NDELAY)

            make_non_blocking(p.stdout)
            make_non_blocking(p.stderr)

            build_paused = False
            read_set = [p.stdout, p.stderr]

            while read_set:
                # Allow the frontend to get a little time
                while Gtk.events_pending():
                    Gtk.main_iteration()
                    if self.quit:
                        raise ExitRequestedException()

                rlist, wlist, xlist = select.select(read_set, [], [], 0)

                if p.stdout in rlist:
                    chunk = p.stdout.read()
                    if chunk == '':
                        p.stdout.close()
                        read_set.remove(p.stdout)
                    textbuffer.insert_with_tags_by_name(
                            textbuffer.get_end_iter(), chunk, 'stdout')

                if p.stderr in rlist:
                    chunk = p.stderr.read()
                    if chunk == '':
                        p.stderr.close()
                        read_set.remove(p.stderr)
                    textbuffer.insert_with_tags_by_name(
                            textbuffer.get_end_iter(), chunk, 'stderr')

                if textbuffer.get_line_count() > 200:
                    textbuffer.delete(textbuffer.get_start_iter(),
                            textbuffer.get_iter_at_line_offset(
                                textbuffer.get_line_count()-200, 0))

                mark = textbuffer.get_mark('end')
                if mark:
                    textbuffer.move_mark(mark, textbuffer.get_end_iter())
                else:
                    mark = textbuffer.create_mark('end', textbuffer.get_end_iter(), False)

                if self.terminal_sclwin.get_vadjustment().get_upper() == \
                        (self.terminal_sclwin.size_request().height + 
                         self.terminal_sclwin.get_vadjustment().get_value()):
                    # currently at the bottom of the textview, therefore scroll
                    # automatically
                    self.terminal.scroll_to_mark(mark, 0.05, True, 0.0, 1.0)

                # See if we should pause the current command
                if not build_paused and self.is_build_paused():
                    os.kill(p.pid, signal.SIGSTOP)
                    build_paused = True
                elif build_paused and not self.is_build_paused():
                    os.kill(p.pid, signal.SIGCONT)
                    build_paused = False

                time.sleep(0.05)

            rc = p.wait()
            self.child_pid = None
        else:
            # use the vte widget
            if isinstance(command, str):
                self.terminal.feed((' $ ' + command + '\n\r').encode("utf-8"))
                command = [os.environ.get('SHELL', '/bin/sh'), '-c', command]
            else:
                self.terminal.feed((' $ ' + ' '.join(command) + '\n\r').encode("utf-8"))

            kws = {}
            if extra_env is not None:
                env = os.environ.copy()
                env.update(extra_env)
                kws['envv'] = ['%s=%s' % x for x in env.items()]
            else:
                kws['envv'] = None

            if cwd:
                kws['working_directory'] = cwd
            else:
                kws['working_directory'] = None

            self.vte_fork_running = True
            self.vte_child_exit_status = None
            # In earlier python-vte versions,
            #  - the environment had to be passed as a sequence of strings
            #    ("FOO=1", "BAR=2") (GNOME bug 583078)
            #  - directory keyword could not be set to None (GNOME bug 583129)
            # The bugs have been fixed, but for compatibility reasons the old
            # compatibility code is still in place.
            self.child_pid = self.terminal.spawn_sync(
                    pty_flags=Vte.PtyFlags.DEFAULT,
                    spawn_flags=GLib.SpawnFlags.SEARCH_PATH_FROM_ENVP,
                    child_setup=None,
                    child_setup_data=None,
                    cancellable=None,
                    argv=command, **kws)[1]
            while self.vte_fork_running:
                Gtk.main_iteration()
                if self.quit:
                    raise ExitRequestedException()
            self.child_pid = None
            if os.WIFEXITED(self.vte_child_exit_status):
                rc = os.WEXITSTATUS(self.vte_child_exit_status)
            elif os.WIFSIGNALED(self.vte_child_exit_status):
                raise CommandError(_('%(command)s died with signal %(rc)s') % {
                        'command': short_command,
                        'rc': os.WTERMSIG(self.vte_child_exit_status)})

        if rc:
            raise CommandError(_('%(command)s returned with an error code (%(rc)s)') % {
                    'command': short_command, 'rc': rc})

    def on_vte_child_exit_cb(self, terminal, status):
        self.vte_fork_running = False
        self.vte_child_exit_status = status


class SelectModulesDialog(Gtk.Dialog):
    def __init__(self, parent, default_module=None):
        Gtk.Dialog.__init__(self, '', parent)
        self.app = parent
        self.create_model()
        self.create_ui()

        if default_module:
            for module_row in self.modules_model:
                if self.modules_model.get(module_row.iter, 0)[0] == default_module:
                    self.treeview.get_selection().select_iter(module_row.iter)
                    self.treeview.scroll_to_cell(
                            self.modules_model.get_path(module_row.iter))
                    break
        self.connect('response', self.on_response_cb)

    def create_model(self):
        self.modules_model = Gtk.ListStore(str)
        modules = [x.name for x in self.app.module_set.get_full_module_list()]
        for module in sorted(modules, key=lambda x: x.lower()):
            self.modules_model.append((module,))

    def create_frame(self, label, child):
        frame = Gtk.Frame.new('')
        frame.set_border_width(3)
        frame.set_shadow_type(Gtk.ShadowType.NONE)
        frame.get_label_widget().set_markup('<b>%s</b>' % label)

        alignment = Gtk.Alignment()
        alignment.set_padding(0, 0, 12, 0)
        frame.add(alignment)
        alignment.add(child)

        return frame

    def create_ui(self):
        vbox = Gtk.VBox()
        self.vbox.add(vbox)

        sclwin = Gtk.ScrolledWindow()
        sclwin.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
        sclwin.set_size_request(-1, 200)
        vbox.pack_start(self.create_frame(_('Module'), sclwin), True, True, 0)

        self.treeview = Gtk.TreeView(self.modules_model)
        self.treeview.set_headers_visible(False)
        sclwin.add(self.treeview)
        selection = self.treeview.get_selection()
        selection.connect('changed', self.on_selection_changed_cb)

        renderer = Gtk.CellRendererText()
        tv_col = Gtk.TreeViewColumn('', renderer, text=0)
        tv_col.set_expand(True)
        tv_col.set_min_width(200)
        self.treeview.append_column(tv_col)

        self.startat_model = Gtk.ListStore(str)
        self.combo_startat = Gtk.ComboBox.new_with_model(self.startat_model)
        cell = Gtk.CellRendererText()
        self.combo_startat.pack_start(cell, True)
        self.combo_startat.add_attribute(cell, 'text', 0)
        vbox.pack_start(self.create_frame(_('Start At'), self.combo_startat), True, True, 0)

        self.vbox.show_all()

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

    def on_selection_changed_cb(self, selection, *args):
        iter = selection.get_selected()[1]
        if iter is None:
            self.startat_model.clear()
            return
        self.selected_module = self.modules_model.get(iter, 0)[0]

        old_start_at = None
        old_start_at_iter = self.combo_startat.get_active_iter()
        new_active_iter = None
        if old_start_at_iter:
            old_start_at = self.startat_model.get(old_start_at_iter, 0)[0]

        self.startat_model.clear()
        modulelist = self.app.module_set.get_module_list([self.selected_module],
                include_suggests=not self.app.config.ignore_suggests)
        for module in modulelist:
            iter = self.startat_model.append((module.name,))
            if module.name == old_start_at:
                new_active_iter = iter

        if new_active_iter:
            self.combo_startat.set_active_iter(new_active_iter)
        elif len(self.startat_model):
            self.combo_startat.set_active_iter(self.startat_model[0].iter)
        else:
            self.combo_startat.set_active_iter(None)

    def on_response_cb(self, dlg, response_id, *args):
        if response_id != Gtk.ResponseType.OK:
            return

        old_start_at_iter = self.combo_startat.get_active_iter()
        self.startat = None
        if old_start_at_iter:
            self.startat = self.startat_model.get(old_start_at_iter, 0)[0]

        return Gtk.ResponseType.OK

class PreferencesDialog(Gtk.Dialog):
    def __init__(self, parent, default_module=None):
        Gtk.Dialog.__init__(self, _('Preferences'), parent)
        self.app = parent
        self.create_ui()
        self.connect('response', self.on_response_cb)
        self.connect('delete-event', self.on_response_cb)

    def create_ui(self):
        vbox = Gtk.VBox(spacing=5)
        vbox.set_border_width(5)
        self.vbox.add(vbox)

        for key, label in (
                ('nonetwork', _('Disable network access')),
                ('alwaysautogen', _('Always run autogen.sh')),
                ('nopoison', _('Don\'t poison modules on failure'))):
            checkbutton = Gtk.CheckButton(label)
            checkbutton.set_active(getattr(self.app.config, key))
            checkbutton.connect('toggled', self.on_toggled_key, key)
            vbox.pack_start(checkbutton, False, False, 0)

        self.vbox.show_all()
        self.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)

    def on_toggled_key(self, checkbutton, key):
        setattr(self.app.config, key, checkbutton.get_active())

    def on_response_cb(self, *args):
        self.destroy()
        self.app.preference_dialog = None


BUILD_SCRIPT = AppWindow
