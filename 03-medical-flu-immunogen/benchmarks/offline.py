"""Block public network I/O during evaluation (Windows asyncio needs loopback)."""
import socket
from contextlib import contextmanager
from unittest.mock import patch


def _disabled(*args, **kwargs):
    raise AssertionError("external network I/O in offline evaluation")


def _loopback_only(connect):
    def checked(sock, address):
        if not isinstance(address, tuple) or address[0] not in ("127.0.0.1", "::1"):
            _disabled()
        return connect(sock, address)
    return checked


@contextmanager
def offline_runtime():
    with (patch.object(socket.socket, "connect", _loopback_only(socket.socket.connect)),
          patch.object(socket.socket, "connect_ex", _loopback_only(socket.socket.connect_ex)),
          patch.object(socket, "getaddrinfo", _disabled)):
        yield
