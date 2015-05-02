# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2007  Mariano Suarez-Alvarez
#
#   notify.py: using libnotify
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

try:
    import dbus
except ImportError:
    dbus = None

class Notify:

    def __init__(self, config = None):
        self.disabled = False
        self.notif_id = 0
        self.iface = self.get_iface()
        if (config and config.nonotify) or self.iface is None:
            self.disabled = True

    def get_iface(self):
        if dbus is None:
            return None

        try:
            bus = dbus.SessionBus()
            proxy = bus.get_object('org.freedesktop.Notifications',
                                   '/org/freedesktop/Notifications')
            return dbus.Interface(proxy, dbus_interface='org.freedesktop.Notifications')
        except dbus.exceptions.DBusException:
            return None

    def reset(self):
        self.notif_id = 0
        self.iface = self.get_iface()

    def notify(self, summary, body, icon = "", expire = 0):
        '''emit a notification'''
        if self.disabled:
            return

        try:
            self.notif_id = self.iface.Notify("jhbuild", self.notif_id, icon,
                                              summary, body, [], {}, 1000*expire)
        except dbus.exceptions.DBusException:
            self.reset()

    def clear(self):
        if self.notif_id != 0:
            try:
                self.iface.CloseNotification(self.notif_id)
                self.notif_id = 0
            except dbus.exceptions.DBusException:
                self.reset()

if __name__ == "__main__":
    n = Notify()
    n.notify("A summary", "A body text")
