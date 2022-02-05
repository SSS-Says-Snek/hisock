"""
This module contains shared code for both HiSockServer and HiSockClient.

====================================
Copyright SSS_Says_Snek, 2022-present
====================================
"""

import inspect
import threading
import warnings
from typing import Callable, Union

try:
    from .utils import (
        FunctionNotFoundException,
        ClientInfo,
        MessageCacheMember,
        Sendable,
        validate_command_not_reserved,
        _type_cast,
        _str_type_to_type_annotations_dict,
    )
except ImportError:
    from utils import (
        FunctionNotFoundException,
        ClientInfo,
        MessageCacheMember,
        Sendable,
        validate_command_not_reserved,
        _type_cast,
        _str_type_to_type_annotations_dict,
    )


class _HiSockBase:
    """
    Base class for both :class:`HiSockClient` and :class:`HiSockServer`.
    See their documentation for more info.
    """

    def __init__(
        self, addr: tuple[str, int], header_len: int = 16, cache_size: int = -1
    ):
        self.addr = addr
        self.header_len = header_len

        # Function related storage
        # {"command": {"func": Callable, "name": str, "type_hint": {"arg": Any}, "threaded": bool, "override": bool}}
        self.funcs = {}
        # {event_name: {"thread_event": threading.Event, "data": Union[None, bytes]}}
        # If catching all, then event_name will be a number sandwiched by dollar signs
        # Then `update` will handle the event with the lowest number
        self._recv_on_events = {}

        # Cache
        self.cache_size = cache_size
        # cache_size <= 0: No cache
        if cache_size > 0:
            self.cache = []

        # Flags
        self.closed = False
        self._receiving_data = False

    # Internal methods

    def _type_cast_client_data(
        self, command: str, client_data: dict
    ) -> Union[ClientInfo, dict]:
        """
        Type cast client info accordingly.
        If the type hint is None, then the client info is returned as is (a dict).

        :param command: The name of the function that called this method.
        :type command: str
        :param client_data: The client data to type cast.
        :type client_data: dict

        :return: The type casted client data from the type hint.
        :rtype: Union[ClientInfo, dict]
        """

        type_cast_to = self.funcs[command]["type_hint"]["client_data"]
        if type_cast_to is None:
            type_cast_to = ClientInfo

        if type_cast_to is ClientInfo:
            return ClientInfo(**client_data)
        return client_data

    @staticmethod
    def _send_type_cast(content: Sendable) -> bytes:
        """
        Type casting content for the send methods.
        This method exists so type casting can easily be changed without changing
        all the send methods.

        :param content: The content to type cast
        :type content: Sendable

        :return: The type casted content
        :rtype: bytes

        :raises InvalidTypeCast: If the content cannot be type casted
        """

        return _type_cast(
            type_cast=bytes,
            content_to_type_cast=content,
            func_name="<sending function>",
        )

    def _cache(
        self,
        has_listener: bool,
        command: str,
        content: bytes,
        decoded_data: str,
        content_header: bytes,
    ):
        if self.cache_size <= 0:
            return

        cache_content = content if has_listener else decoded_data
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
            or
            # This shouldn't happen, because if it is overridden then it should already
            # be deleted from the reserved functions dictionary. But just in case the user
            # manually changed the dictionary or something...
            self.funcs[reserved_func_name]["override"]
            or reserved_func_name not in self.funcs
        ):
            return

        # Not going to verify if the amount of args and kwargs are correct, because
        # that should've already been done
        self.funcs[reserved_func_name]["func"](*args, **kwargs)

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
            raise FunctionNotFoundException(
                f"Function with command {func_name} not found"
            )

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

            # Store annotations of function
            annotations = _str_type_to_type_annotations_dict(
                inspect.getfullargspec(func).annotations
            )  # {"param": type}
            parameter_annotations = {}

            # Map function arguments into type hint compliant ones
            type_cast_arguments: tuple
            if self.command in self.outer._reserved_funcs:
                type_cast_arguments = (
                    self.outer._reserved_funcs[self.command]["type_cast_arguments"],
                )[0]
            else:
                type_cast_arguments = self.outer._unreserved_func_arguments

            for func_argument, argument_name in zip(func_args, type_cast_arguments):
                parameter_annotations[argument_name] = annotations.get(
                    func_argument, None
                )

            # Add function
            self.outer.funcs[self.command] = {
                "func": func,
                "name": func.__name__,
                "type_hint": parameter_annotations,
                "threaded": self.threaded,
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
                needed_number_of_args = (
                    self.outer._reserved_funcs[self.command]["number_arguments"],
                )[0]
                valid = number_of_func_args == needed_number_of_args

            # Unreserved commands
            else:
                valid = number_of_func_args <= len(
                    self.outer._unreserved_func_arguments
                )

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

    def recv(self, recv_on: str = None, recv_as: Sendable = bytes) -> Sendable:
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

        # Wait for `update` to retreive the data
        self._recv_on_events[listen_on]["thread_event"].wait()

        # Clean up
        data = self._recv_on_events[listen_on]["data"]
        del self._recv_on_events[listen_on]

        # Return
        return _type_cast(
            type_cast=recv_as, content_to_type_cast=data, func_name="<recv function>"
        )
