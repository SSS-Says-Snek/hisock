"""
This module contains the HiSockClient, used to power the client
of HiSock, but also contains a `connect` function, to pass in
things automatically. It is strongly advised to use `connect`
over `HiSockClient`, as `connect` passes in some key arguments
that `HiSockClient` does not provide

====================================
Copyright SSS_Says_Snek, 2021-present
====================================
"""

# Imports
from __future__ import annotations  # Remove when 3.10 is used by majority

import socket
import inspect  # Type-hinting detection for type casting
import json  # Handle sending dictionaries
import errno  # Handle fatal errors with the server
import warnings  # Non-severe errors
import sys  # Utilize stderr
import threading  # Threaded client and decorators
import traceback  # Error handling
from typing import Callable, Union  # Type hints
from ipaddress import IPv4Address  # Comparisons
from time import time  # Unix timestamp support

try:
    # Pip builds require relative import
    from .utils import (
        ClientException,
        ClientNotFound,
        ServerException,
        FunctionNotFoundException,
        FunctionNotFoundWarning,
        ServerNotRunning,
        MessageCacheMember,
        Sendable,
        Client,
        _removeprefix,
        _type_cast,
        _str_type_to_type_annotations_dict,
        make_header,
        iptup_to_str,
        validate_ipv4,
        validate_command_not_reserved,
    )
except ImportError:
    # Relative import doesn't work for non-pip builds
    from utils import (
        ClientException,
        ClientNotFound,
        ServerException,
        FunctionNotFoundException,
        FunctionNotFoundWarning,
        ServerNotRunning,
        MessageCacheMember,
        Sendable,
        Client,
        _removeprefix,
        _type_cast,
        _str_type_to_type_annotations_dict,
        make_header,
        iptup_to_str,
        validate_ipv4,
        validate_command_not_reserved,
    )


# ░█████╗░░█████╗░██╗░░░██╗████████╗██╗░█████╗░███╗░░██╗██╗
# ██╔══██╗██╔══██╗██║░░░██║╚══██╔══╝██║██╔══██╗████╗░██║██║
# ██║░░╚═╝███████║██║░░░██║░░░██║░░░██║██║░░██║██╔██╗██║██║
# ██║░░██╗██╔══██║██║░░░██║░░░██║░░░██║██║░░██║██║╚████║╚═╝
# ╚█████╔╝██║░░██║╚██████╔╝░░░██║░░░██║╚█████╔╝██║░╚███║██╗
# ░╚════╝░╚═╝░░╚═╝░╚═════╝░░░░╚═╝░░░╚═╝░╚════╝░╚═╝░░╚══╝╚═╝
#   Change this code only if you know what you are doing!
# If this code is changed, the client may not work properly


class HiSockClient:
    """
    The client class for :mod:`HiSock`.

    :param addr: A two-element tuple, containing the IP address and the
        port number of where the server is hosted.
        **Only IPv4 is currently supported.**
    :type addr: tuple
    :param name: Either a string or NoneType, representing the name the client
        goes by. Having a name provides an easy interface of sending.
        data to a specific client and identifying clients. It is therefore
        highly recommended to pass in a name.

        Pass in NoneType for no name (:meth:`connect` should handle that)
    :type name: str, optional
    :param group: Either a string or NoneType representing the group the client
        is in. Being in a group provides an easy interface of sending
        data to multiple specific clients, and identifying multiple clients.
        It is highly recommended to provide a group for complex servers.
        Pass in NoneType for no group (:meth:`connect` should handle that).
    :type group: str, optional
    :param blocking: A boolean set to whether the client should block the loop
        while waiting for message or not.
        Default is True.
    :type blocking: bool, optional
    :param header_len: An integer defining the header length of every message.
        A larger header length would mean a larger maximum message length
        (about 10**header_len).
        **MUST** be the same header length as the server, or else it will crash
        (hard to debug too!).
        Default sets to 16 (maximum length of content: 10 quadrillion bytes).
    :type header_len: int, optional

    :ivar tuple addr: A two-element tuple containing the IP address and the
        port number of the server.
    :ivar int header_len: An integer storing the header length of each "message".
    :ivar str name: A string representing the name of the client to identify by.
        Default is None.
    :ivar str group: A string representing the group of the client to identify by.
        Default is None.
    :ivar dict funcs: A list of functions registered with decorator :meth:`on`.
        **This is mainly used for under-the-hood-code.**
    :ivar int connect_time: An integer sotring the Unix timestamp of when the
        client connected to the server.
    """

    def __init__(
        self,
        addr: tuple[str, int],
        name: Union[str, None],
        group: Union[str, None],
        blocking: bool = True,
        header_len: int = 16,
        cache_size: int = -1,
    ):
        self.addr = addr
        self.name = name
        self.group = group
        self.header_len = header_len

        # Socket initialization
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect(self.addr)
        except ConnectionRefusedError:
            raise ServerNotRunning(
                "Server is not running! Aborting..."
            ) from ConnectionRefusedError
        self.sock.setblocking(blocking)

        # Function related storage
        # {"command": {"func": Callable, "name": str, "type_hint": Any, "threaded": bool}}
        self.funcs = {}

        # Stores the names of the reserved functions, as well as the
        # number of arguments each reserved function accepts
        # Used for the `on` decorator
        self._reserved_functions = {
            "client_connect": 1,
            "client_disconnect": 1,
            "force_disconnect": 0,
        }
        # {event_name: {"thread_event": threading.Event, "data": Union[None, bytes]}}
        # If catching all, then event_name will be a number sandwiched by dollar signs
        # Then `update` will handle the event with the lowest number
        self._recv_on_events = {}

        # Cache
        self.cache_size = cache_size
        if cache_size > 0:
            # cache_size <= 0: No cache
            self.cache = []

        # TLS arguments
        self.tls_arguments = {"tls": False}  # If TLS is false, then no TLS

        # Flags
        self.closed = False
        self.connected = False
        self.connect_time = 0  # Unix timestamp
        self._receiving_data = False

        # Send client hello
        self._send_client_hello()

    # Dunders

    def __str__(self) -> str:
        """Example: <HiSockClient connected to 192.168.1.133:5000>"""

        return f"<HiSockClient connected to {iptup_to_str(self.addr)}>"

    def __repr__(self):
        return self.__str__()

    # Comparisons

    def __gt__(self, other: Union[HiSockClient, str]) -> bool:
        """Example: HiSockClient(...) > "192.168.1.133:5000" """

        if type(other) not in (HiSockClient, str):
            raise TypeError("Type not supported for > comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) > IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    def __ge__(self, other: Union[HiSockClient, str]) -> bool:
        """Example: HiSockClient(...) >= "192.168.1.133:5000" """

        if type(other) not in (HiSockClient, str):
            raise TypeError("Type not supported for >= comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) >= IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) >= IPv4Address(ip[0])

    def __lt__(self, other: Union[HiSockClient, str]) -> bool:
        """Example: HiSockClient(...) < "192.168.1.133:5000" """

        if type(other) not in (HiSockClient, str):
            raise TypeError("Type not supported for < comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) < IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) < IPv4Address(ip[0])

    def __le__(self, other: Union[HiSockClient, str]) -> bool:
        """Example: HiSockClient(...) <= "192.168.1.133:5000" """

        if type(other) not in (HiSockClient, str):
            raise TypeError("Type not supported for <= comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) <= IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) <= IPv4Address(ip[0])

    def __eq__(self, other: Union[HiSockClient, str]) -> bool:
        """Example: HiSockClient(...) == "192.168.1.133:5000" """

        if type(other) not in (HiSockClient, str):
            raise TypeError("Type not supported for == comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) == IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) == IPv4Address(ip[0])

    # Internal methods

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
            func_name="<client sending function>",
        )

    def _send_client_hello(self):
        """
        Sends a hello to the server for the first connection.

        :raises ClientException: If the client is already connected.
        """

        if self.connected:
            raise ClientException(
                f"Client is already connected! (connected {time() - self.connect_time} seconds ago)"
            )

        hello_dict = {"name": self.name, "group": self.group}
        self._send_raw(f"$CLTHELLO${json.dumps(hello_dict)}")

        self.connected = True
        self.connect_time = time()

    def _handle_keepalive(self):
        """Handle a keepalive sent from the server."""

        self._send_raw("$KEEPACK$")

    # On decorator

    def _call_function(self, func_name: str, sort_by_name: bool, *args, **kwargs):
        """
        Calls a function with the given arguments and returns the result.

        :param func_name: The name of the function to call.
        :type func_name: str
        :param sort_by_name: Whether to sort the arguments by name or not.
        :type sort_by_name: bool
        :param args: The arguments to pass to the function.
        :param kwargs: The keyword arguments to pass to the function.

        :raises FunctionNotFoundException: If the function is not found.
        """

        func: str

        # Find the function by the function name
        if sort_by_name:
            for func_command, func_data in self.funcs.items():
                if func_data["name"] == func_name:
                    func = func_command
                    break
            else:
                raise FunctionNotFoundException(
                    f"Function with name {func_name} not found"
                )
        # Find the function by the function command
        else:
            if func_name not in self.funcs:
                raise FunctionNotFoundException(
                    f"Function with command {func_name} not found"
                )
            func = func_name

        # Normal
        if not self.funcs[func]["threaded"]:
            self.funcs[func]["func"](*args, **kwargs)
            return

        # Threaded
        function_thread = threading.Thread(
            target=self.funcs[func]["func"],
            args=args,
            kwargs=kwargs,
            daemon=True,
        )
        function_thread.start()

    class _on:
        """Decorator used to handle something when receiving command."""

        def __init__(
            self, outer: HiSockClient, command: str, threaded: bool, override: bool
        ):
            self.outer = outer
            self.command = command
            self.threaded = threaded
            self.override = override

            validate_command_not_reserved(self.command)

        def __call__(self, func: Callable) -> Callable:
            """
            Adds a function that gets called when the client receives a
            matching command.
            """

            func_args = inspect.getfullargspec(func).args

            # Overriding a reserved command, remove it from reserved functions
            if self.override:
                if self.command in self.outer._reserved_functions:
                    self.outer.funcs.pop(self.command)

                    del self.outer._reserved_functions[
                        self.command
                    ]
                else:
                    warnings.warn(
                        f"Unnecessary override for {self.command}.", UserWarning
                    )

            self._assert_num_func_args_valid(len(func_args))

            annotations = _str_type_to_type_annotations_dict(
                inspect.getfullargspec(func).annotations
            )  # {"param": type}
            parameter_annotations = {}

            # Process unreserved commands
            if self.command not in self.outer._reserved_functions:
                # Map function arguments into type hint compliant ones
                # Note: this is the same code as in `HiSockServer` which is why
                # this could support multiple arguments. However, for now, the
                # only argument is `message`.
                for func_argument, argument_name in zip(func_args, ("message",)):
                    if func_argument not in annotations:
                        continue
                    parameter_annotations[argument_name] = annotations[func_argument]

            # Add function
            self.outer.funcs[self.command] = {
                "func": func,
                "name": func.__name__,
                "type_hint": parameter_annotations,
                "threaded": self.threaded,
            }

            # Decorator stuff
            return func

        def _assert_num_func_args_valid(self, number_of_func_args: int):
            """
            Asserts the number of function arguments is valid.
            Unreserved commands can have either 0 or 1 arguments.
            For reserved commands, refer to
            :ivar:`HiSockClient._reserved_functions_parameters_num`.

            :raises TypeError: If the number of function arguments is invalid.
            """

            valid = False
            needed_number_of_args = "0-1"

            # Reserved commands
            try:
                needed_number_of_args = self.outer._reserved_functions[
                    self.command
                ]
                valid = number_of_func_args == needed_number_of_args
            # Unreserved commands
            except KeyError:
                valid = not number_of_func_args > 1

            if not valid:
                raise TypeError(
                    f"{self.command} command must have {needed_number_of_args} "
                    f"arguments, not {number_of_func_args}"
                )

    def on(
        self, command: str, threaded: bool = False, override: bool = False
    ) -> Callable:
        """
        A decorator that adds a function that gets called when the client
        receives a matching command.

        Reserved functions are functions that get activated on
        specific events, and they are:

        1. ``client_connect`` - Activated when a client connects to the server
        2. ``client_disconnect`` - Activated when a client disconnects from the server

        The parameters of the function depend on the command to listen.
        For example, reserved functions ``client_connect`` and
        ``client_disconnect`` gets the client's data passed in as an argument.
        All other unreserved functions get the message passed in.

        In addition, certain type casting is available to unreserved functions.
        That means, that, using type hints, you can automatically convert
        between needed instances. The type casting currently supports:

        - ``bytes``
        - ``str``
        - ``int``
        - ``float``
        - ``bool``
        - ``None``
        - ``list`` (with the types listed here)
        - ``dict`` (with the types listed here)

        For more information, read the documentation for type casting.

        :param command: A string, representing the command the function should activate
            when receiving it.
        :type command: str
        :param threaded: A boolean, representing if the function should be run in a thread
            in order to not block the update loop.
            Default is False.
        :type threaded: bool, optional
        :param override: A boolean representing if the function should override the
            reserved function with the same name and to treat it as an unreserved function.
            Default is False.
        :type override: bool, optional

        :return: The same function (the decorator just appended the function to a stack).
        :rtype: function

        :raises TypeError: If the number of function arguments is invalid.
        """

        return self._on(self, command, threaded, override)

    # Getters
    def get_cache(
        self,
        idx: Union[int, slice, None] = None,
    ) -> list[MessageCacheMember]:
        """
        Gets the message cache.

        :param idx: An integer or ``slice``, specifying what specific message caches to return.

            Default is None (Retrieves the entire cache)
        :type idx: Union[int, slice], optional

        :return: A list of dictionaries, representing the cache
        :rtype: list[dict]
        """

        if idx is None:
            return self.cache
        return self.cache[idx]

    def get_client(self, client: Client):
        """
        Gets the client data for a client.

        :param client: The client name or IP+port to get.
        :type client: Client

        :return: The client data.
        :rtype: dict

        :raises ValueError: If the client IP is invalid.
        :raises ClientNotFound: If the client couldn't be found.
        :raises ServerException: If another error occurred.
        """

        try:
            validate_ipv4(iptup_to_str(client))
        except ValueError as e:
            # Names are allowed, too.
            if not isinstance(client, str):
                raise e

        self._send_raw(f"$GETCLT${client}")
        response = self.recv()
        response = _type_cast(
            type_cast=dict,
            content_to_type_cast=response,
            func_name="<get_client response>",
        )

        # Validate response
        if "traceback" not in response:
            return response
        if response["traceback"] == "$NOEXIST$":
            raise ClientNotFound(f"Client {client} not connected to the server.")
        raise ServerException(
            f"Failed to get client from server: {response['traceback']}"
        )

    def get_server_addr(self) -> tuple[str, int]:
        """
        Gets the address of where the hisock client is connected
        at.

        :return: A tuple, with the format (str IP, int port)
        :rtype: tuple[str, int]
        """

        return self.addr

    def get_client_addr(self) -> tuple[str, int]:
        """
        Gets the address of the hisock client that is connected
        to the server.

        :return: A tuple, with the format (str IP, int port)
        :rtype: tuple[str, int]
        """

        return self.sock.getsockname()

    # Transmit data

    def send(self, command: str, content: Sendable = None):
        """
        Sends a command & content to the server.

        :param command: A string, containing the command to send
        :type command: str
        :param content: The message / content to send
        :type content: Sendable, optional
        """

        data_to_send = (
            b"$CMD$" + command.encode() + b"$MSG$" + self._send_type_cast(content)
        )
        content_header = make_header(data_to_send, self.header_len)
        self.sock.send(content_header + data_to_send)

    def _send_raw(self, content: Sendable = None):
        """
        Sends a message to the server: NO COMMAND REQUIRED.
        This is preferable in some situations, where clients need to send
        multiple data over the server, without overcomplicating it with commands

        :param content: The message / content to send
        :type content: Sendable, optional
        """

        data_to_send = self._send_type_cast(content)
        header = make_header(data_to_send, self.header_len)
        self.sock.send(header + data_to_send)

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

        :return: The data received type casted as :param:`recv_as`.
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

    # Changers

    def change_name(self, new_name: Union[str, None]):
        """
        Changes the name of the client

        :param new_name: The new name for the client to be called
            If left blank, then the name will be reset.
        :type new_name: str, optional
        """

        data_to_send = "$CHNAME$" + (new_name if bool(new_name) else "")
        self._send_raw(data_to_send)

    def change_group(self, new_group: Union[str, None]):
        """
        Changes the client's group.

        :param new_group: The new group name of the client
        :type new_group: Union[str, None]
        """

        data_to_send = "$CHGROUP$" + (f" {new_group}" if bool(new_group) else "")
        self._send_raw(data_to_send)

    # Update

    def _update(self):
        """
        Handles new messages, and sends them to the appropriate functions. This method
        should be called in a while loop in a thread. If this function isn't in its
        own thread, then :meth:`recv` won't work.

        .. warning::
           Don't call this method on its own; instead use :meth:`start`.
        """

        if self.closed:
            # This shouldn't happen due to `start` handling it, but just in case...
            return

        try:
            ### Receiving data ###

            self._receiving_data = True

            content_header = False
            # Receive header
            try:
                content_header = self.sock.recv(self.header_len)
            except ConnectionResetError:
                raise ServerNotRunning(
                    "Server has stopped running, aborting..."
                ) from ConnectionResetError
            except ConnectionAbortedError:
                # Keepalive timeout reached
                self.closed = True
                self.close(emit_leave=False)

            # Most likely server has stopped running
            if not content_header:
                print("Connection forcibly closed by server, exiting...")
                raise SystemExit

            data = self.sock.recv(int(content_header.decode()))
            self._receiving_data = False
            decoded_data = data.decode()

            ### Reserved commands ###

            # Handle keepalive
            if decoded_data == "$KEEPALIVE$":
                self._handle_keepalive()
                return

            # Handle force disconnection
            if decoded_data == "$DISCONN$":
                self.close(emit_leave=False)  # The server already knows we're gone
                if "force_disconnect" in self.funcs:
                    self._call_function("force_disconnect", False)
                return

            # Handle new client connection
            if decoded_data.startswith("$CLTCONN$"):
                if "client_connect" not in self.funcs:
                    warnings.warn("client_connect", FunctionNotFoundWarning)
                    return

                client_content = _type_cast(
                    type_cast=dict,
                    content_to_type_cast=_removeprefix(decoded_data, "$CLTCONN$"),
                    func_name="<client connect in update>",
                )
                self._call_function("client_connect", False, client_content)
                return

            # Handle client disconnection
            if decoded_data.startswith("$CLTDISCONN$"):
                if "client_disconnect" not in self.funcs:
                    warnings.warn("client_disconnect", FunctionNotFoundWarning)
                    return

                client_content = _type_cast(
                    type_cast=dict,
                    content_to_type_cast=_removeprefix(decoded_data, "$CLTDISCONN$"),
                    func_name="<client disconnect in update>",
                )
                self._call_function("client_disconnect", False, client_content)
                return

            ### Unreserved commands ###

            # Handle random data
            if not decoded_data.startswith("$CMD$"):
                return

            has_listener = False  # For cache

            # Get the command and the message
            command = decoded_data.lstrip("$CMD$").split("$MSG$")[0]
            content = _removeprefix(decoded_data, f"$CMD${command}$MSG$")

            # No content? (`_removeprefix` didn't do anything)
            if not content or content == decoded_data:
                content = None

            # Call functions that are listening for this command from the `on`
            # decorator
            for matching_command, func in self.funcs.items():
                if not command == matching_command:
                    continue

                has_listener = True

                # Call function with dynamic args
                arguments = ()
                if len(func["type_hint"]) == 1:
                    arguments = (
                        _type_cast(
                            type_cast=func["type_hint"]["message"],
                            content_to_type_cast=content,
                            func_name=func["name"],
                        ),
                    )
                self._call_function(func["name"], True, *arguments)
                break

            # Handle data needed for `recv`
            for listener in self._recv_on_events:
                # Catch-all listeners
                # `listener` transverses in-order, so the first will be the minimum
                should_continue = True
                if listener.startswith("$") and listener.endswith("$"):
                    should_continue = False

                # Specific listeners
                if command == listener:
                    should_continue = False

                if should_continue:
                    continue

                self._recv_on_events[listener]["data"] = content
                self._recv_on_events[listener]["thread_event"].set()
                has_listener = True
                break

            # No listener found
            if not has_listener:
                warnings.warn(
                    f"No listener found for command {command}",
                    FunctionNotFoundWarning,
                )
                # No need for caching
                return

            # Caching
            if self.cache_size >= 0:
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

        except IOError as e:
            # Normal, means message has ended
            if not (
                e.errno != errno.EAGAIN
                and e.errno != errno.EWOULDBLOCK
                and not self.closed
            ):
                return

            # Fatal error, abort client
            traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
            print(
                "\nServer error encountered, aborting client...",
                file=sys.stderr,
            )
            self.close()

            raise SystemExit from e

    # Stop

    def close(self, emit_leave: bool = True):
        """
        Closes the client; running ``client.update()`` won't do anything now

        :param emit_leave: Decides if the client will emit `leave` to the server or not
        :type emit_leave: bool
        """

        self.closed = True
        if emit_leave:
            self._send_raw("$USRCLOSE$")
        self.sock.close()

    # Main loop

    def start(self):
        """Start the main loop for the client."""

        def loop():
            while not self.closed:
                try:
                    self._update()
                except KeyboardInterrupt:
                    self.close()

        loop_thread = threading.Thread(target=loop, daemon=False)
        loop_thread.start()


def connect(addr, name=None, group=None, blocking=True, header_len=16, cache_size=-1):
    """
    Creates a `HiSockClient` instance. See HiSockClient for more details

    :param addr: A two-element tuple containing the IP address and
        the port number of the server.
    :type addr: tuple
    :param name: A string containing the name of what the client should go by.
        This argument is optional.
    :type name: str, optional
    :param group: A string, containing the "group" the client is in.
        Groups can be utilized to send specific messages to them only.
        This argument is optional.
    :type group: str, optional
    :param blocking: A boolean specifying if the client should block or not
        in the socket.
        Default is True.
    :type blocking: bool, optional
    :param header_len: An integer defining the header length of every message.
        Default is True.
    :type header_len: int, optional

    :return: A :class:`HiSockClient` instance.
    :rtype: instance

    .. note::
        A simple way to use this function is to use :func:`utils.input_client_config`
        which will ask you for the server IP, port, name, and group. Then, you can
        call this function by simply doing ``connect(*input_client_config())``
    """

    return HiSockClient(addr, name, group, blocking, header_len, cache_size)


if __name__ == "__main__":
    print("Testing client!")
    client = connect(
        ("127.0.0.1", int(input("Port: "))),
        name=input("Name: "),
        group=input("Group: "),
    )

    print(
        "The HiSock police are on to you. "
        "You must change your name and group before they catch you."
    )
    client.change_name(input("New name: "))
    client.change_group(input("New group: "))

    @client.on("client_connect")
    def on_connect(client_data: dict):
        print(
            f'{client_data["name"]} has joined! '
            f'Their IP is {iptup_to_str(client_data["ip"])}. '
            f'Their group is {client_data["group"]}.'
        )

    @client.on("client_disconnect")
    def on_disconnect(client_data: dict):
        print(f'{client_data["name"]} disconnected from the server.')

    @client.on("force_disconnect")
    def on_force_disconnect():
        print("You have been disconnected from the server.")
        client.close()
        __import__('os')._exit(0)

    @client.on("message", threaded=True)
    def on_message(message: str):
        print(f"Message received:\n{message}")

    @client.on("genocide")
    def on_genocide():
        print("It's time to die!")
        client.close()
        __import__('os')._exit(0)

    def choices():
        print(
            "Your choices are:"
            "\n\tsend\n\tchange_name\n\tchange_group\n\tset_timer\n\tstop\n\tgenocide"
        )
        while True:
            choice = input("What would you like to do? ")
            if choice == "send":
                client.send("broadcast_message", input("Message: "))
            elif choice == "ping":
                client.send("ping")
                client.recv("pong")
            elif choice == "change_name":
                client.change_name(input("New name: "))
            elif choice == "change_group":
                client.change_group(input("New group: "))
            elif choice == "set_timer":
                client.send("set_timer", input("Seconds: "))
                client.recv("timer_done")
                print("Timer done!")
            elif choice == "get_all_clients":
                client.send("get_all_clients")
                print(client.recv("all_clients", recv_as=dict))
            elif choice == "stop":
                client.close()
                return
            elif choice == "genocide":
                input("You will kill many people. Do you wish to proceed? ")
                print("Just kidding, your input had no effect. Time for genocide!")
                client.send(
                    "set_timer", input("How many seconds for the genocide to last?")
                )
                client.recv("timer_done")
                print("Genociding...")
                client.send("commit_genocide")
            else:
                print("Invalid choice.")

    choices_thread = threading.Thread(target=choices, daemon=False)
    choices_thread.start()

    client.start()
