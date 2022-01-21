"""
Tests the decorators that make up the core of hisock's receiving system
"""

import pytest

from hisock.server import HiSockServer
from hisock.client import HiSockClient

serv_on = HiSockServer._on
cli_on = HiSockClient._on


class DummyFuncClassServer:
    def __init__(self):
        self.funcs = {}
        self._reserved_functions = {
            "join": 1,
            "leave": 1,
            "message": 3,
            "name_change": 3,
            "group_change": 3,
        }


class DummyFuncClassClient(DummyFuncClassServer):
    def __init__(self):
        super().__init__()
        self._reserved_functions = {
            "client_connect": 1,
            "client_disconnect": 1,
            "force_disconnect": 0,
        }


_ServerDec = serv_on
_ClientDec = cli_on

server_dummy = DummyFuncClassServer()
client_dummy = DummyFuncClassClient()


def server_dec(cmd):
    return _ServerDec(server_dummy, cmd, False, False)


def client_dec(cmd):
    return _ClientDec(client_dummy, cmd, False, False)


#################################################
#                                               #
#                                               #
#################################################


@server_dec("e")
def func_server_no_typecast(clt, msg):
    pass


@server_dec("f")
def func_server_two_typecast(clt: str, msg: int):
    pass


@server_dec("g")
def func_server_one_typecast(clt, msg: float):
    pass


@server_dec("h")
def func_server_clt_typecast(clt: list, msg):
    pass


@client_dec("i")
def func_client_no_typecast(msg):
    pass


@client_dec("j")
def func_client_typecast(msg: int):
    pass


class TestServerDecs:
    def test_server_no_typehint(self):
        assert server_dummy.funcs["e"] == {
            "func": func_server_no_typecast,
            "name": func_server_no_typecast.__name__,
            "type_hint": {"client_data": None, "message": None},
            "threaded": False
        }

    def test_server_two_typecast(self):
        assert server_dummy.funcs["f"] == {
            "func": func_server_two_typecast,
            "name": func_server_two_typecast.__name__,
            "type_hint": {"client_data": str, "message": int},
            "threaded": False
        }

    def test_server_one_typecast(self):
        assert server_dummy.funcs["g"] == {
            "func": func_server_one_typecast,
            "name": func_server_one_typecast.__name__,
            "type_hint": {"client_data": None, "message": float},
            "threaded": False
        }

    def test_server_clt_typecast(self):
        assert server_dummy.funcs["h"] == {
            "func": func_server_clt_typecast,
            "name": func_server_clt_typecast.__name__,
            "type_hint": {"client_data": list, "message": None},
            "threaded": False
        }


class TestClientDecs:
    def test_client_no_typecast(self):
        assert client_dummy.funcs["i"] == {
            "func": func_client_no_typecast,
            "name": func_client_no_typecast.__name__,
            "type_hint": {},
            "threaded": False
        }

    def test_client_typecast(self):
        assert client_dummy.funcs["j"] == {
            "func": func_client_typecast,
            "name": func_client_typecast.__name__,
            "type_hint": {"message": int},
            "threaded": False
        }

    def test_client_exception(self):
        with pytest.raises(ValueError):

            @client_dec("$RESERVED$")
            def func_client_exception(msg):
                pass
