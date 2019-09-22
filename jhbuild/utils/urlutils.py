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

from .compat import PY2, PY3

if PY2:
    from urlparse import urlparse, urljoin, urlsplit, urlunsplit, urlunparse
    from urllib2 import urlopen, Request, HTTPError, URLError
    from urllib import unquote
    import urlparse as urlparse_mod
elif PY3:
    from urllib.parse import urlparse, urljoin, urlsplit, urlunsplit, urlunparse, unquote
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
    from urllib import parse as urlparse_mod

    urlparse, urljoin, urlsplit, urlunsplit, urlunparse, urlopen, Request,
    urlparse_mod, HTTPError, URLError, unquote