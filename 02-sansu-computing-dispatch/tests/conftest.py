import ipaddress
import socket
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
torch.set_num_threads(1)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Windows asyncio uses a loopback socketpair even with in-process TestClient."""
    connect = socket.socket.connect
    def local_only(sock,address):
        if isinstance(address,tuple) and not ipaddress.ip_address(address[0]).is_loopback:
            raise AssertionError("external connection during offline test")
        return connect(sock,address)
    monkeypatch.setattr(socket.socket,"connect",local_only)
