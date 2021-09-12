import builtins
import inspect
import re
from functools import wraps
from typing import Callable, Any

import pytest


class _ServerDec:
    """Decorator used to handle something when receiving command"""

    def __init__(self, outer, cmd_activation):
        # `outer` arg is for the HiSockServer instance
        # `cmd_activation` is the command... on activation (WOW)
        self.outer = outer
        self.cmd_activation = cmd_activation

    def __call__(self, func: Callable):
        """Adds a function that gets called when the server receives a matching command"""

        func_args = inspect.getfullargspec(func).args

        if len(func_args) != 2 and (
                self.cmd_activation not in self.outer.reserved_functions or
                self.cmd_activation == "message"):
            raise ValueError(
                f"Incorrect number of arguments: {len(func_args)} != 2"
            )

        annots = inspect.getfullargspec(func).annotations

        if self.cmd_activation not in self.outer.reserved_functions or \
                self.cmd_activation == "message":
            # Processes nonreserved commands and reserved `message `

            # `func_args` looks like ['clt_data', 'msg']
            # `annots` look like {'msg': str}
            try:
                # Try to map first arg (client data)
                # Into type hint compliant one
                clt_annotation = annots[func_args[0]]
                if isinstance(clt_annotation, str):
                    clt_annotation = builtins.__dict__[annots[func_args[0]]]
            except KeyError:
                # KeyError means there is no type hint
                clt_annotation = None
            try:
                # Try to map second arg (content)
                # Into type hint compliant one
                msg_annotation = annots[func_args[1]]
                if isinstance(msg_annotation, str):
                    msg_annotation = builtins.__dict__[annots[func_args[1]]]
            except KeyError:
                # KeyError means there is no type hint
                msg_annotation = None
        else:
            # None for now, will add support for reserved functions
            # soon tm
            clt_annotation = None
            msg_annotation = None

        # Creates function dictionary to add to `outer.funcs`
        func_dict = {
            "func": func,
            "name": func.__name__,
            "type_hint": {
                "clt": clt_annotation,
                "msg": msg_annotation
            }
        }

        self.outer.funcs[self.cmd_activation] = func_dict

        # Returns inner function, like a decorator would do
        return func


class _ClientDec:
    """Decorator used to handle something when receiving command"""

    def __init__(self, outer: Any, command: str):
        # `outer` arg is for the HiSockClient instance
        # `cmd_activation` is the command... on activation (WOW)
        self.outer = outer
        self.command = command

    def __call__(self, func: Callable):
        """Adds a function that gets called when the client receives a matching command"""

        # Checks for illegal $cmd$ notation (used for reserved functions)
        if re.search(r"\$.+\$", self.command):
            raise ValueError(
                "The format \"$command$\" is used for reserved functions - "
                "Consider using a different format"
            )
        # Gets annotations of function
        annots = inspect.getfullargspec(func).annotations
        func_args = inspect.getfullargspec(func).args

        try:
            # Try to map first arg (client data)
            # Into type hint compliant one
            msg_annotation = annots[func_args[0]]
            if isinstance(msg_annotation, str):
                msg_annotation = builtins.__dict__[annots[func_args[0]]]
        except KeyError:
            msg_annotation = None

        # Creates function dictionary to add to `outer.funcs`
        func_dict = {
            "func": func,
            "name": func.__name__,
            "type_hint": msg_annotation
        }
        self.outer.funcs[self.command] = func_dict

        # Returns the inner function, like a decorator
        return func


class DummyFuncClassServer:
    def __init__(self):
        self.funcs = {}
        self.reserved_functions = [
            'join', 'leave',
            'message'
        ]


class DummyFuncClassClient(DummyFuncClassServer):
    def __init__(self):
        super().__init__()
        self.reserved_functions = [
            'client_connect',
            'client_disconnect'
        ]


server_dummy = DummyFuncClassServer()
client_dummy = DummyFuncClassClient()


def server_dec(cmd):
    return _ServerDec(server_dummy, cmd)


def client_dec(cmd):
    return _ClientDec(client_dummy, cmd)


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
        assert server_dummy.funcs['e'] == {
            "func": func_server_no_typecast,
            "name": func_server_no_typecast.__name__,
            "type_hint": {
                "clt": None,
                "msg": None
            }
        }

    def test_server_two_typecast(self):
        assert server_dummy.funcs['f'] == {
            "func": func_server_two_typecast,
            "name": func_server_two_typecast.__name__,
            "type_hint": {
                "clt": str,
                "msg": int
            }
        }

    def test_server_one_typecast(self):
        assert server_dummy.funcs['g'] == {
            "func": func_server_one_typecast,
            "name": func_server_one_typecast.__name__,
            "type_hint": {
                "clt": None,
                "msg": float
            }
        }

    def test_server_clt_typecast(self):
        assert server_dummy.funcs['h'] == {
            "func": func_server_clt_typecast,
            "name": func_server_clt_typecast.__name__,
            "type_hint": {
                "clt": list,
                "msg": None
            }
        }


class TestClientDecs:
    def test_client_no_typecast(self):
        assert client_dummy.funcs['i'] == {
            "func": func_client_no_typecast,
            "name": func_client_no_typecast.__name__,
            "type_hint": None
        }

    def test_client_typecast(self):
        assert client_dummy.funcs['j'] == {
            "func": func_client_typecast,
            "name": func_client_typecast.__name__,
            "type_hint": int
        }

    def test_client_exception(self):
        with pytest.raises(ValueError):
            @client_dec("$RESERVED$")
            def func_client_exception(msg):
                pass
