# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2011  Colin Walters <walters@verbum.org>
#
#   symlinklock.py - A lock file
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
import sys 
import time
import errno
import stat
import logging
import re

class LockFile(object):
    def __init__(self, path):
        self.path = path

    def lock(self, timeout_seconds=0):
        raise NotImplementedError()

    def unlock(self):
        raise NotImplementedError()
    
    @classmethod
    def get(self, path):
        if sys.platform == 'win32':
            return DummyLockFile(path)
        else:
            return SymlinkLockFile(path)

class DummyLockFile(LockFile):
    def lock(self, timeout_seconds=0):
        pass

    def unlock(self):
        pass

class SymlinkLockFile(LockFile):
    """This class provides a multi-process locking approach similar to
    what Emacs does when editing a buffer for a file.  The basic idea
    is that Unix locking approaches are often buggy, and worse don't
    provide data like *who* is locking a file (useful for
    debugging).  Only available on Unix."""
    def __init__(self, path):
        LockFile.__init__(self, path)
        self._locked = False
        self._lock_data = 'lock-pid-%d-uid-%d' % (os.getpid(), os.getuid())
        self._lock_data_re = re.compile(r'^lock-pid-([0-9]+)-uid-([0-9]+)$')

    def _existing_process_matches(self, pid, uid):
        if os.uname()[0] != 'Linux':
            return os.path.exists('/proc/%d' % (pid, ))
        try:
            f = open('/proc/%d/status' % (pid, ))
        except IOError, e:
            return False
        for line in f:
            if line.startswith('Uid:'):
                (real, rest) = line[4:].split(None, 1)
                if int(real) == uid:
                    return True
                return False
        return False

    def _get_current_locker(self):
        try:
            linkdata = os.readlink(self.path)
        except OSError, e:
            if e.errno == errno.NOENT:
                return (None, None)
            else:
                raise
        match = self._lock_data_re.match(linkdata)
        if match is None:
            raise ValueError('Invalid lock data %r, expected lock-pid-XXX-uid-XXX')
        return (int(match.group(1)), int(match.group(2)))

    def lock(self, timeout_seconds=0):
        """Sleep until we acquire the lock file.  Timeout of 0 means wait forever; -1 means do not wait."""
        assert not self._locked
        waited = 0
        printed_sleeping_log = False
        while True:
            try:
                os.symlink(self._lock_data, self.path)
                self._locked = True
                return
            except OSError, e:
                if e.errno == errno.EEXIST:
                    (pid, uid) = self._get_current_locker()
                    if pid is None:
                        continue
                    if not self._existing_process_matches(pid, uid):
                        logging.info(_('Removing stale lock left by no longer extant pid %(pid)d, uid %(uid)d') % {'pid': pid,
                                                                                                                   'uid': uid})
                        try:
                            os.unlink(self.path)
                            continue
                        except OSError, e:
                            if e.errno == errno.ENOENT:
                                continue
                            else:
                                raise
                    if timeout_seconds != -1:
                        if not printed_sleeping_log:
                            logging.info(_('Lock %(path)r taken by pid %(pid)d; waiting for it to exit.  Press Control-C to interrupt.') 
                                         % {'path': self.path, 'pid': pid})
                            printed_sleeping_log = True
                        time.sleep(1)
                        waited += 1
                    if timeout_seconds != 0 and (timeout_seconds == -1 or waited >= timeout_seconds):
                        raise Exception("Timed out waiting for lock file %r" % (self.path, ))
                else:
                    raise

    def unlock(self):
        assert self._locked
        os.unlink(self.path)
        self._locked = False
            
if __name__ == '__main__':
    import __builtin__
    __builtin__.__dict__['_'] = lambda x: x
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    lock = LockFile('/tmp/jhbuild-lock')
    lock.lock()
    logging.info('locked')
    time.sleep(5)
    lock.unlock()
    logging.info('unlocked')
