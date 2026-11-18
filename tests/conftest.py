import os
import socket
import sys
from pathlib import Path
import pytest

os.environ["MPLBACKEND"] = "Agg"
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    # Windows asyncio uses loopback sockets internally for Streamlit AppTest.
    def guarded(original):
        def connect(sock,address,*args,**kwargs):
            if isinstance(address,tuple) and address[0] in ("127.0.0.1","::1"):
                return original(sock,address,*args,**kwargs)
            raise AssertionError("External network forbidden during offline tests")
        return connect
    monkeypatch.setattr(socket.socket,"connect",guarded(socket.socket.connect))
    monkeypatch.setattr(socket.socket,"connect_ex",guarded(socket.socket.connect_ex))
