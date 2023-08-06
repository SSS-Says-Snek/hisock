"""
This module contains shared code for both HiSockServer and HiSockClient.

====================================
Copyright SSS_Says_Snek, 2022-present
====================================
"""

from __future__ import annotations

import inspect
import threading
from typing import Any, Callable, Optional, Union

try:
    from . import _typecast
    from .utils import (ClientInfo, FunctionNotFoundException,
                        MessageCacheMember, Sendable, make_header,
                        validate_command_not_reserved)
except ImportError:
    import _typecast
    from utils import (ClientInfo, FunctionNotFoundException,
                       MessageCacheMember, Sendable, make_header,
                       validate_command_not_reserved)


class _HiSockBase:
    RECV_BUFFERSIZE = 8192

    """
    Base class for both :class:`HiSockClient` and :class:`HiSockServer`.
    See their documentation for more info.
    """

    def __init__(self, addr: tuple[str, int], header_len: int = 16, cache_size: int = -1):
        self.addr = addr
        self.header_len = header_len

        # Function related storage
        # {"command": {"func": Callable, "name": str, "type_hint": {"arg": Any}, "threaded": bool, "override": bool}}
        self.funcs = {}
        # {event_name: {"thread_event": threading.Event, "data": Union[None, bytes]}}
        # If catching all, then event_name will be a number sandwiched by dollar signs
        # Then `update` will handle the event with the lowest number
        self._recv_on_events: dict[str, Any] = {}

        # Cache
        self.cache_size = cache_size
        # cache_size <= 0: No cache
        if cache_size > 0:
            self.cache = []

        # Flags
        self.closed = False
        self._receiving_data = False

    # Internal methods

    def _cache(
        self,
        has_listener: bool,
        command: str,
        content: bytes,
        full_data: bytes,
        content_header: bytes,
    ):
        if self.cache_size <= 0:
            return

        cache_content = content if has_listener else full_data
        self.cache.append(
            MessageCacheMember(
                {
                    "header": content_header,
                    "content": cache_content,
                    "called": has_listener,
                    "command": command,
                }
            )
        )

        # Pop oldest from stack
        if 0 < self.cache_size < len(self.cache):
            self.cache.pop(0)

    # On decorator

    def _call_wildcard_function(
        self,
        command: str,
        content: Sendable,
        client_info: Optional[ClientInfo] = None,
    ):
        """
        Call the wildcard command.

        :param command: The command that was sent. If None, then it is just
            random data.
        :type command: str, optional
        :param content: The data to pass to the wildcard command. Will NOT be
            type-casted.
        :type content: bytes
        :param client_info: The client info. If None, then there is no client info.
        :type client_info: ClientInfo, optional

        :raises FunctionNotFoundException: If there is no wildcard listener.
        """

        try:
            self.funcs["*"]
        except KeyError:
            raise FunctionNotFoundException("A wildcard function doesn't exist.") from None

        arguments = []
        if client_info is not None:
            arguments.append(client_info)
        arguments.extend([command, content])

        self._call_function(
            "*",
            *arguments,
        )

    def _call_function_reserved(self, reserved_func_name: str, *args, **kwargs):
        """
        Call a reserved function. If the function is overridden or not found,
        then the function will not be called.

        :param reserved_func_name: The name of the reserved function to call.
        :type reserved_func_name: str
        :param args: The arguments to pass to the function.
        :param kwargs: The keyword arguments to pass to the function.
        """

        if (
            reserved_func_name not in self._reserved_funcs
            or reserved_func_name not in self.funcs
            # This shouldn't happen, because if it is overridden then it should already
            # be deleted from the reserved functions dictionary. But just in case the user
            # manually changed the dictionary or something...
            or self.funcs[reserved_func_name]["override"]
        ):
            return

        # Not going to verify if the amount of args and kwargs are correct, because
        # that should've already been done

        # Normal
        if not self.funcs[reserved_func_name]["threaded"]:
            self.funcs[reserved_func_name]["func"](*args, **kwargs)
            return

        # Threaded
        function_thread = threading.Thread(
            target=self.funcs[reserved_func_name]["func"],
            args=args,
            kwargs=kwargs,
            daemon=True,
        )
        function_thread.start()

    def _call_function(self, func_name: str, *args, **kwargs):
        """
        Calls a function with the given arguments.

        :param func_name: The name of the function to call.
        :type func_name: str
        :param args: The arguments to pass to the function.
        :param kwargs: The keyword arguments to pass to the function.

        :raises FunctionNotFoundException: If the function is not found.
        """

        if func_name not in self.funcs:
            raise FunctionNotFoundException(f"Function with command {func_name} not found")

        # Normal
        if not self.funcs[func_name]["threaded"]:
            self.funcs[func_name]["func"](*args, **kwargs)
            return

        # Threaded
        function_thread = threading.Thread(
            target=self.funcs[func_name]["func"],
            args=args,
            kwargs=kwargs,
            daemon=True,
        )
        function_thread.start()

    def _prepare_send(self, command: str, content: Optional[Sendable] = None) -> bytes:
        fmt, encoded_content = _typecast.write_fmt(content) if content is not None else ("", b"")

        data_to_send = b"$CMD$" + command.encode() + b"$MSG$" + make_header(fmt, 8) + fmt.encode() + encoded_content
        data_header = make_header(data_to_send, self.header_len)

        return data_header + data_to_send

    class _on:  # NOSONAR (it's used in child classes)
        """Decorator for handling a command"""

        def __init__(
            self,
            outer,
            command: str,
            threaded: bool,
            override: bool,
        ):
            self.outer = outer
            self.command = command
            self.threaded = threaded
            self.override = override

            validate_command_not_reserved(self.command)

        def __call__(self, func: Callable) -> Callable:
            """
            Adds a function that gets called when the server receives a matching command.

            :raises ValueError: If the number of function arguments is invalid.
            """

            func_args = inspect.getfullargspec(func).args

            # Overriding a reserved command, remove it from reserved functions
            if self.override and self.command in self.outer._reserved_funcs:
                self.outer.funcs.pop(self.command, None)
                del self.outer._reserved_funcs[self.command]

            self._assert_num_func_args_valid(len(func_args))

            # Add function
            self.outer.funcs[self.command] = {
                "func": func,
                "name": func.__name__,
                "threaded": self.threaded,
                "num_args": len(func_args),
                "override": self.override,
            }

            # Decorator stuff
            return func

        def _assert_num_func_args_valid(self, number_of_func_args: int):
            """
            Asserts the number of function arguments is valid.
            Unreserved commands can have either 0 or 1 arguments.
            For reserved commands, refer to
            :ivar:`outer._reserved_funcs`.

            :raises TypeError: If the number of function arguments is invalid.
            """

            needed_number_of_args = f"0-{len(self.outer._unreserved_func_arguments)}"

            # Reserved commands
            if self.command in self.outer._reserved_funcs:
                needed_number_of_args = self.outer._reserved_funcs[self.command]
                valid = number_of_func_args == needed_number_of_args

            # Unreserved commands
            else:
                valid = number_of_func_args <= len(self.outer._unreserved_func_arguments)

            if not valid:
                raise TypeError(
                    f"{self.command} command must have {needed_number_of_args} "
                    f"arguments, not {number_of_func_args}"
                )

    # Transmitting data

    def _handle_recv_commands(self, command: str, content: bytes):
        """
        Handle data needed for :meth:`recv`
        Should be called from update or run.

        :param command: The command to handle.
        :type command: str
        :param content: The content / data / message.
        :type content: bytes

        :return: If there was a response.
        :rtype: bool
        """

        for listener in self._recv_on_events:
            # Catch-all listeners
            # `listener` transverses in-order, so the first will be the minimum
            should_continue = True
            if listener.startswith("$") and listener.endswith("$"):
                should_continue = False
            # Specific listeners
            if listener == command:
                should_continue = False
            if should_continue:
                continue

            self._recv_on_events[listener]["data"] = content
            self._recv_on_events[listener]["thread_event"].set()
            return True

        return False

    def recv(self, recv_on: str = None) -> Sendable:
        """
        Receive data from the server while blocking.
        Can receive on a command, which is used as like one-time on decorator.

        .. note::
           Reserved functions will be ignored and not caught by this method.

        :param recv_on: A string for the command to receive on.
        :type recv_on: str, optional
        :param recv_as: The type to receive the data as.
        :type recv_as: Sendable, optional

        :return: The data received type casted as ``recv_as``.
        :rtype: Sendable
        """

        # `update` will be the one actually receiving the data (in its own thread).
        # Tell update to listen for a command and send it to us instead.
        if recv_on is not None:
            listen_on = recv_on
        else:
            # Get the highest number of catch-all listeners
            catch_all_listener_max = 0
            for listener in self._recv_on_events:
                if not listener.startswith("$") and listener.endswith("$"):
                    continue
                catch_all_listener_max = int(listener.replace("$", ""))

            listen_on = f"${catch_all_listener_max + 1}$"

        # {event_name: {"thread_event": threading.Event, "data": Union[None, bytes]}}
        self._recv_on_events[listen_on] = {
            "thread_event": threading.Event(),
            "data": None,
        }

        # Wait for `update` to retrieve the data
        self._recv_on_events[listen_on]["thread_event"].wait()

        # Clean up
        data = self._recv_on_events[listen_on]["data"]
        del self._recv_on_events[listen_on]

        fmt_len = int(data[:8])
        fmt = data[8 : 8 + fmt_len].decode()
        data = data[8 + fmt_len :]

        fmt_ast = _typecast.read_fmt(fmt)
        typecasted_data = _typecast.typecast_data(fmt_ast, data)

        # Return
        return typecasted_data
