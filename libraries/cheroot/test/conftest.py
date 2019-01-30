"""Pytest configuration module.

Contains fixtures, which are tightly bound to the Cheroot framework
itself, useless for end-users' app testing.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ..testing import (  # noqa: F401
    native_server, wsgi_server,
)
from ..testing import get_server_client


@pytest.fixture  # noqa: F811
def wsgi_server_client(wsgi_server):
    """Create a test client out of given WSGI server."""
    return get_server_client(wsgi_server)


@pytest.fixture  # noqa: F811
def native_server_client(native_server):
    """Create a test client out of given HTTP server."""
    return get_server_client(native_server)
