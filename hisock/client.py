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
import re  # Make sure arguments are passed correctly
import errno  # Handle fatal errors with the server
import sys  # Utilize stderr
import threading  # Threaded client and decorators
import warnings  # Handle warnings
import builtins  # Convert string methods into builtins
import traceback  # Error handling
from typing import Callable, Union, Any  # Type hints
from ipaddress import IPv4Address  # Comparisons
from time import time  # Unix timestamp support

# Utilities
try:
    # Pip builds require relative import
    from .utils import (
        make_header,
        _removeprefix,
        ServerNotRunning,
        ClientException,
        FunctionNotFoundException,
        Sendable,
        Client,
        iptup_to_str,
        _type_cast,
        MessageCacheMember,
    )
except ImportError:
    # Relative import doesn't work for non-pip builds
    from utils import (
        make_header,
        _removeprefix,
        ServerNotRunning,
        ClientException,
        FunctionNotFoundException,
        Sendable,
        Client,
        iptup_to_str,
        _type_cast,
        MessageCacheMember,
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
        Pass in NoneType for no group (:meth:`connect` should handle that)
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

        # Function and cache storage
        self.funcs = {}
        self.cache_size = cache_size
        if cache_size >= 0:
            # cache_size <= -1: No cache
            self.cache = []

        # Stores the names of the reserved functions
        # Used for the `on` decorator
        self._reserved_functions = ("client_connect", "client_disconnect")
        # Stores the number of parameters each reserved function takes
        # Used for the `on` decorator
        self._reserved_functions_parameters_num = (
            1,  # client_connect
            1,  # client_disconnect
        )

        # TLS arguments
        self.tls_arguments = {"tls": False}  # If TLS is false, then no TLS

        # Flags
        self._closed = False
        self.connected = False
        self.connect_time = 0  # Unix timestamp
        self.sock.setblocking(blocking)

    def __str__(self) -> str:
        """Example: <HiSockClient connected to 192.168.1.133:5000>"""

        return f"<HiSockClient connected to {iptup_to_str(self.addr)}>"

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        """Returns how many clients are connected"""

    # Comparisons

    def __gt__(self, other: Union[HiSockClient, str]) -> bool:
        """Example: HiSockClient(...) > "192.168.1.133:5000" """
        if type(other) not in [HiSockClient, str]:
            raise TypeError("Type not supported for > comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) > IPv4Address(other.addr[0])
        ip = other.split(":")

        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    def __ge__(self, other: Union[HiSockClient, str]) -> bool:
        """Example: HiSockClient(...) >= "192.168.1.133:5000" """
        if type(other) not in [HiSockClient, str]:
            raise TypeError("Type not supported for >= comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) >= IPv4Address(other.addr[0])
        ip = other.split(":")

        return IPv4Address(self.addr[0]) >= IPv4Address(ip[0])

    def __lt__(self, other: Union[HiSockClient, str]) -> bool:
        """Example: HiSockClient(...) < "192.168.1.133:5000" """
        if type(other) not in [HiSockClient, str]:
            raise TypeError("Type not supported for < comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) < IPv4Address(other.addr[0])
        ip = other.split(":")

        return IPv4Address(self.addr[0]) < IPv4Address(ip[0])

    def __le__(self, other: Union[HiSockClient, str]) -> bool:
        """Example: HiSockClient(...) <= "192.168.1.133:5000" """
        if type(other) not in [HiSockClient, str]:
            raise TypeError("Type not supported for <= comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) <= IPv4Address(other.addr[0])
        ip = other.split(":")

        return IPv4Address(self.addr[0]) <= IPv4Address(ip[0])

    def __eq__(self, other: Union[HiSockClient, str]) -> bool:
        """Example: HiSockClient(...) == "192.168.1.133:5000" """
        if type(other) not in [HiSockClient, str]:
            raise TypeError("Type not supported for == comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) == IPv4Address(other.addr[0])
        ip = other.split(":")

        return IPv4Address(self.addr[0]) == IPv4Address(ip[0])

    # Internal methods

    def _send_client_hello(self):
        """
        Sends a hello to the server for the first connection

        :raises ClientException: If the client is already connected
        """

        if self.connected:
            raise ClientException(
                f"Client is already connected! (connected {time() - self.connect_time} seconds ago)"
            )

        hello_dict = {"name": self.name, "group": self.group}
        conn_header = make_header(
            f"$CLTHELLO$ {json.dumps(hello_dict)}", self.header_len
        )

        self.sock.send(conn_header + f"$CLTHELLO$ {json.dumps(hello_dict)}".encode())
        self.connected = True
        self.connect_time = time()

    def _send_type_cast(self, content: Sendable) -> bytes:
        """
        Type casting content for the send methods.
        This method exists so type casting can easily be changed without changing
        all the send methods.

        :param content: The content to type cast
        :type content: Sendable
        :return: The type casted content
        :rtype: bytes

        :raise InvalidTypeCast: If the content cannot be type casted
        """

        return _type_cast(bytes, content, "<client sending function>")

    # On decorator

    def _call_function(self, func_name, *args, **kwargs) -> Any:
        """
        Calls a function with the given arguments and returns the result.

        :param func_name: The name of the function to call.
        :type func_name: str
        :param args: The arguments to pass to the function.
        :param kwargs: The keyword arguments to pass to the function.
        :return: The result of the function call.
        :rtype: Any

        :raises FunctionNotFoundException: If the function is not found.
        """

        # Check if the function exists
        if func_name not in self.funcs:
            raise FunctionNotFoundException(f"Function {func_name} not found")

        # Normal
        if not self.funcs[func_name]["threaded"]:
            return self.funcs[func_name]["func"](*args, **kwargs)

        # Threaded
        function_thread = threading.Thread(
            target=self.funcs[func_name]["func"],
            args=args,
            kwargs=kwargs,
            daemon=True,
        )
        function_thread.start()

    class _on:
        """Decorator used to handle something when receiving command"""

        def __init__(
            self, outer: HiSockClient, command: str, threaded: bool, override: bool
        ):
            self.outer = outer
            self.command = command
            self.threaded = threaded
            self.override = override

        def __call__(self, func: Callable) -> Callable:
            """Adds a function that gets called when the client receives a matching command"""

            # Checks for illegal $cmd$ notation (used for reserved functions)
            if re.search(r"\$.+\$", self.command):
                raise ValueError(
                    'The format "$command$" is used for reserved functions - '
                    "Consider using a different format"
                )

            func_args = inspect.getfullargspec(func).args
            self._assert_num_func_args_valid(len(func_args))

            annotations = inspect.getfullargspec(func).annotations  # {"param": type}
            parameter_annotations = {"msg": None}

            # Process unreserved commands
            if self.command not in self.outer._reserved_functions:
                # Map function arguments into type hint compliant ones
                # Note: this is the same code as in `HiSockServer` which is why
                # this could support multiple arguments. However, for now, the
                # only argument is `msg`.
                for func_argument, argument_name in zip(func_args, ("msg",)):
                    if func_argument not in annotations:
                        continue
                    parameter_annotations[argument_name] = annotations[func_argument]

            # Creates function dictionary to add to `outer.funcs`
            func_dict = {
                "func": func,
                "name": func.__name__,
                "type_hint": parameter_annotations,
                "threaded": self.threaded,
            }
            self.outer.funcs[self.command] = func_dict

            # Returns the inner function, like a decorator
            return func

        def _assert_num_func_args_valid(self, actual_num_func_args: int):
            """
            Asserts the number of function arguments is valid.

            :raises TypeError: If the number of function arguments is invalid.
            """

            number_of_func_args = 2  # Normal commands

            # Reserved commands
            try:
                index_of_reserved_cmd = self.outer._reserved_functions.index(
                    self.cmd_activation
                )
                # Get the number of parameters for the reserved command
                number_of_func_args = self.outer._reserved_functions_parameters_num[
                    index_of_reserved_cmd
                ]

            except ValueError:
                # Not a reserved command
                pass

            # Check if the number of function arguments is valid
            if actual_num_func_args != number_of_func_args:
                raise TypeError(
                    f"{self.cmd_activation} command must have {number_of_func_args} "
                    f"arguments, not {actual_num_func_args}"
                )

    def on(
        self, command: str, threaded: bool = False, override: bool = False
    ) -> Callable:
        """
        A decorator that adds a function that gets called when the client
        receives a matching command

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

        - ``bytes`` -> ``bytes``
        - ``bytes`` -> ``str``
        - ``bytes`` -> ``int``
        - ``bytes`` -> ``dict``
        - ``dict`` -> ``dict``
        - ``dict`` -> ``bytes``

        :param command: A string, representing the command the function should activate
            when receiving it.
        :type command: str
        :param threaded: A boolean, representing if the function should be run in a thread
            in order to not block the update() loop.
            Default is False
        :type threaded: bool, optional
                :param override: A boolean representing if the function should override the
            reserved function with the same name and to treat it as an unreserved function.
            Default is False.
        :type override: bool, optional
        :return: The same function (the decorator just appended the function to a stack)
        :rtype: function
        """

        # Passes in outer to _on decorator/class
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
        else:
            return self.cache[idx]

    def get_client(self, client: Union[str, tuple[str, int]]):
        """PROTOTYPE; DO NOT USE YET"""
        if isinstance(client, tuple):
            if len(client) == 2:
                client = f"{client[0]}:{client[1]}"
            else:
                raise TypeError("Client tuple not correctly formatted")
        get_client_header = make_header(b"$GETCLT$ " + client.encode(), self.header_len)
        self.sock.send(get_client_header + b"$GETCLT$ " + client.encode())

        client = self.recv_raw()

        print(client)
        raise NotImplementedError("BRUH IT'S NOT IMPLEMENTED")

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

    # Send

    def send(self, command: str, content: Sendable):
        """
        Sends a command & content to the server.

        :param command: A string, containing the command to send
        :type command: str
        :param content: The message / content to send
        :type content: Sendable
        """

        data_to_send = command.encode() + b" " + self._send_type_cast(content)
        content_header = make_header(data_to_send, self.header_len)
        self.sock.send(content_header + data_to_send)

    def send_raw(self, content: Sendable):
        """
        Sends a message to the server: NO COMMAND REQUIRED.
        This is preferable in some situations, where clients need to send
        multiple data over the server, without overcomplicating it with commands

        :param content: The message / content to send
        :type content: Sendable
        """

        data_to_send = self._send_type_cast(content)
        header = make_header(data_to_send, self.header_len)
        self.sock.send(header + data_to_send)

    def recv_raw(self) -> bytes:
        """
        Waits (blocks) until a message is sent, and returns that message.
        This is not recommended for content with commands attached;
        it is meant to be used alongside with :func:`HiSockServer.send_client_raw` and
        :func:`HiSockServer.send_group_raw`

        :return: A bytes-like object, containing the content/message
          the client first receives
        :rtype: bytes
        """

        # Blocks depending on your blocking settings, until message
        msg_len = int(self.sock.recv(self.header_len).decode())
        message = self.sock.recv(msg_len)

        # Returns message
        return message

    def change_name(self, new_name: Union[str, None]):
        """
        Changes the name of the client

        :param new_name: The new name for the client to be called
            If left blank, then the name will be reset.
        :type new_name: str, optional
        """

        data_to_send = "$CHNAME$" + (f" {new_name}" or "")
        self.send_raw(data_to_send)

    def change_group(self, new_group: Union[str, None]):
        """
        Changes the client's group.

        :param new_group: The new group name of the client
        :type new_group: Union[str, None]
        """

        data_to_send = "$CHGROUP$" + (f" {new_group}" or "")
        self.send_raw(data_to_send)

    def update(self):
        """
        Handles newly received messages, excluding the received messages for :meth:`wait_recv`
        This method must be called every iteration of a while loop, as to not lose valuable info.
        In some cases, it is recommended to run this in a thread, as to not block the
        program
        """

        if self._closed:
            return

        try:
            # Receive header
            try:
                content_header = self.sock.recv(self.header_len)
            except ConnectionResetError:
                raise ServerNotRunning(
                    "Server has stopped running, aborting..."
                ) from ConnectionResetError

            # Most likely server has stopped running
            if not content_header:
                print("Connection forcibly closed by server, exiting...")
                raise SystemExit

            content = self.sock.recv(int(content_header.decode()))

            ### Reserved ###

            # Handle force disconnection
            if content == b"$DISCONN$":
                self.close()
                if "force_disconnect" in self.funcs:
                    self._call_function("force_disconnect")
                return

            # Handle new client connection
            if (
                content.startswith(b"$CLTCONN$")  # No standalone code for this
                and "client_connect" in self.funcs
            ):
                clt_content = json.loads(_removeprefix(content, b"$CLTCONN$ "))
                self._call_function("client_connect", clt_content)
                return

            # Handle client disconnection
            if (
                content.startswith(b"$CLTDISCONN$")  # No standalone code for this
                and "client_disconnect" in self.funcs
            ):
                # Client disconnected from server; parse and call function
                clt_content = json.loads(_removeprefix(content, b"$CLTDISCONN$ "))
                self._call_function("client_disconnect", clt_content)

            ### Unreserved ###

            # Declaring these here for cache after this
            has_corresponding_function = False
            parse_content = None
            command = None

            for matching_command, func in self.funcs.items():
                if (
                    content.startswith(matching_command.encode())
                    and matching_command not in self._reserved_functions
                ):
                    has_corresponding_function = True
                    command = matching_command
                    parse_content = content[len(matching_command) + 1 :]

                    parse_content = _type_cast(
                        func["type_hint"], parse_content, func["name"]
                    )

                    # Call function
                    self._call_function(func["name"], parse_content)
                    break  # only one command can be received at a time for now

            # Caching
            if self.cache_size >= 0:
                if has_corresponding_function:
                    cache_content = parse_content
                else:
                    cache_content = content
                self.cache.append(
                    MessageCacheMember(
                        {
                            "header": content_header,
                            "content": cache_content,
                            "called": has_corresponding_function,
                            "command": command,
                        }
                    )
                )

                if 0 < self.cache_size < len(self.cache):
                    self.cache.pop(0)

        except IOError as e:
            # Normal, means message has ended
            if not (
                e.errno != errno.EAGAIN
                and e.errno != errno.EWOULDBLOCK
                and not self._closed
            ):
                return

            # Fatal error, abort client (print exception, print log, exit python)
            traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
            print(
                "\nServer error encountered, aborting client...",
                file=sys.stderr,
            )
            self.close()

            raise SystemExit

    def close(self, emit_leave: bool = True):
        """
        Closes the client; running `client.update()` won't do anything now

        :param emit_leave: Decides if the client will emit `leave` to the server or not
        :type emit_leave: bool
        """

        self._closed = True  # Prevents :meth:`update` from running
        if emit_leave:
            close_header = make_header(b"$USRCLOSE$", self.header_len)
            self.sock.send(close_header + b"$USRCLOSE$")
        self.sock.close()


class ThreadedHiSockClient(HiSockClient):
    """
    A downside of :class:`HiSockClient` is that you need to constantly
    :meth:`run` it in a while loop, which may block the program. Fortunately,
    in Python, you can use threads to do two different things at once. Using
    :class:`ThreadedHiSockClient`, you would be able to run another
    blocking program, without ever fearing about blocking and all that stuff.

    .. note::
       In some cases though, :class:`HiSockClient` offers more control than
       :class:`ThreadedHiSockClient`, so be careful about when to use
       :class:`ThreadedHiSockClient` over :class:`HiSockClient`
    """

    def __init__(
        self, addr, name=None, group=None, blocking=True, header_len=16, cache_size=-1
    ):
        super().__init__(addr, name, group, blocking, header_len, cache_size)
        self._thread = threading.Thread(target=self.run)

        self._stop_event = threading.Event()

    def stop_client(self):
        """Stops the client"""
        self._closed = True
        self._stop_event.set()
        self.sock.close()

    def _run(self):
        """
        The main while loop to run the thread

        Refer to :class:`HiSockClient` for more details

        .. warning::
           This method is **NOT** recommended to be used in an actual
           production environment. This is used internally for the thread, and should
           not be interacted with the user
        """
        while not self._stop_event.is_set():
            try:
                self.update()
            except (OSError, ValueError):
                break

    def start_client(self):
        """Starts the main server loop"""
        self._thread.start()

    def join(self):
        """Waits for the thread to be killed"""
        self._thread.join()


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

    :return: A :class:`HiSockClient` instance
    :rtype: instance

    .. note::
        A simple way to use this function is to use :func:`utils.input_client_config`
        which will ask you for the server IP, port, name, and group. Then, you can
        call this function by simply doing ``connect(*input_client_config())``
    """

    return HiSockClient(addr, name, group, blocking, header_len, cache_size)


def threaded_connect(
    addr, name=None, group=None, blocking=True, header_len=16, cache_size=-1
):
    """
    Creates a :class:`ThreadedHiSockClient` instance. See :class:`ThreadedHiSockClient`
    for more details

    :return: A :class:`ThreadedHiSockClient` instance
    """

    return ThreadedHiSockClient(addr, name, group, blocking, header_len, cache_size)


if __name__ == "__main__":
    print("Why are you running this file? You're weird...")
