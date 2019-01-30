"""Tests for the HTTP server."""
# -*- coding: utf-8 -*-
# vim: set fileencoding=utf-8 :

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import os
import socket
import tempfile
import threading
import time

import pytest

from .._compat import bton
from ..server import Gateway, HTTPServer
from ..testing import (
    ANY_INTERFACE_IPV4,
    ANY_INTERFACE_IPV6,
    EPHEMERAL_PORT,
    get_server_client,
)


def make_http_server(bind_addr):
    """Create and start an HTTP server bound to bind_addr."""
    httpserver = HTTPServer(
        bind_addr=bind_addr,
        gateway=Gateway,
    )

    threading.Thread(target=httpserver.safe_start).start()

    while not httpserver.ready:
        time.sleep(0.1)

    return httpserver


non_windows_sock_test = pytest.mark.skipif(
    not hasattr(socket, 'AF_UNIX'),
    reason='UNIX domain sockets are only available under UNIX-based OS',
)


@pytest.fixture
def http_server():
    """Provision a server creator as a fixture."""
    def start_srv():
        bind_addr = yield
        httpserver = make_http_server(bind_addr)
        yield httpserver
        yield httpserver

    srv_creator = iter(start_srv())
    next(srv_creator)
    yield srv_creator
    try:
        while True:
            httpserver = next(srv_creator)
            if httpserver is not None:
                httpserver.stop()
    except StopIteration:
        pass


@pytest.fixture
def unix_sock_file():
    """Check that bound UNIX socket address is stored in server."""
    tmp_sock_fh, tmp_sock_fname = tempfile.mkstemp()

    yield tmp_sock_fname

    os.close(tmp_sock_fh)
    os.unlink(tmp_sock_fname)


def test_prepare_makes_server_ready():
    """Check that prepare() makes the server ready, and stop() clears it."""
    httpserver = HTTPServer(
        bind_addr=(ANY_INTERFACE_IPV4, EPHEMERAL_PORT),
        gateway=Gateway,
    )

    assert not httpserver.ready
    assert not httpserver.requests._threads

    httpserver.prepare()

    assert httpserver.ready
    assert httpserver.requests._threads
    for thr in httpserver.requests._threads:
        assert thr.ready

    httpserver.stop()

    assert not httpserver.requests._threads
    assert not httpserver.ready


def test_stop_interrupts_serve():
    """Check that stop() interrupts running of serve()."""
    httpserver = HTTPServer(
        bind_addr=(ANY_INTERFACE_IPV4, EPHEMERAL_PORT),
        gateway=Gateway,
    )

    httpserver.prepare()
    serve_thread = threading.Thread(target=httpserver.serve)
    serve_thread.start()

    serve_thread.join(0.5)
    assert serve_thread.is_alive()

    httpserver.stop()

    serve_thread.join(0.5)
    assert not serve_thread.is_alive()


@pytest.mark.parametrize(
    'ip_addr',
    (
        ANY_INTERFACE_IPV4,
        ANY_INTERFACE_IPV6,
    )
)
def test_bind_addr_inet(http_server, ip_addr):
    """Check that bound IP address is stored in server."""
    httpserver = http_server.send((ip_addr, EPHEMERAL_PORT))

    assert httpserver.bind_addr[0] == ip_addr
    assert httpserver.bind_addr[1] != EPHEMERAL_PORT


@non_windows_sock_test
def test_bind_addr_unix(http_server, unix_sock_file):
    """Check that bound UNIX socket address is stored in server."""
    httpserver = http_server.send(unix_sock_file)

    assert httpserver.bind_addr == unix_sock_file


@pytest.mark.skip(reason="Abstract sockets don't work currently")
@non_windows_sock_test
def test_bind_addr_unix_abstract(http_server):
    """Check that bound UNIX socket address is stored in server."""
    unix_abstract_sock = b'\x00cheroot/test/socket/here.sock'
    httpserver = http_server.send(unix_abstract_sock)

    assert httpserver.bind_addr == unix_abstract_sock


PEERCRED_IDS_URI = '/peer_creds/ids'
PEERCRED_TEXTS_URI = '/peer_creds/texts'


class _TestGateway(Gateway):
    def respond(self):
        req = self.req
        conn = req.conn
        req_uri = bton(req.uri)
        if req_uri == PEERCRED_IDS_URI:
            peer_creds = conn.peer_pid, conn.peer_uid, conn.peer_gid
            return ['|'.join(map(str, peer_creds))]
        elif req_uri == PEERCRED_TEXTS_URI:
            return ['!'.join((conn.peer_user, conn.peer_group))]
        return super(_TestGateway, self).respond()


@pytest.mark.skip(
    reason='Test HTTP client is not able to work through UNIX socket currently'
)
@non_windows_sock_test
def test_peercreds_unix_sock(http_server, unix_sock_file):
    """Check that peercred lookup and resolution work when enabled."""
    httpserver = http_server.send(unix_sock_file)
    httpserver.gateway = _TestGateway
    httpserver.peercreds_enabled = True

    testclient = get_server_client(httpserver)

    expected_peercreds = os.getpid(), os.getuid(), os.getgid()
    expected_peercreds = '|'.join(map(str, expected_peercreds))
    assert testclient.get(PEERCRED_IDS_URI) == expected_peercreds
    assert 'RuntimeError' in testclient.get(PEERCRED_TEXTS_URI)

    httpserver.peercreds_resolve_enabled = True
    import grp
    expected_textcreds = os.getlogin(), grp.getgrgid(os.getgid()).gr_name
    expected_textcreds = '!'.join(map(str, expected_textcreds))
    assert testclient.get(PEERCRED_TEXTS_URI) == expected_textcreds
