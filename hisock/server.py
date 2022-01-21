"""
This module contains the HiSockServer, used to power the server
of HiSock, but also contains a `start_server` function, to pass in
things automatically. It is strongly advised to use `start_server`
over `HiSockServer`

====================================
Copyright SSS_Says_Snek 2021-present
====================================
"""

# Imports
from __future__ import annotations  # Remove when 3.10 is used by majority

import socket
import inspect  # Type-hinting detection for type casting
import select  # Handle multiple clients at once
import json  # Handle sending dictionaries
import threading  # Threaded server and decorators
import warnings  # Non-severe errors
from typing import Callable, Union, Iterable  # Type hints
from ipaddress import IPv4Address  # Comparisons

try:
    # Pip builds require relative import
    from .utils import (
        ServerException,
        ClientException,
        FunctionNotFoundException,
        FunctionNotFoundWarning,
        ClientNotFound,
        GroupNotFound,
        MessageCacheMember,
        ClientInfo,
        Sendable,
        Client,
        _removeprefix,
        _dict_tupkey_lookup,
        _type_cast,
        _str_type_to_type_annotations_dict,
        receive_message,
        make_header,
        validate_ipv4,
        validate_command_not_reserved,
        ipstr_to_tup,
    )
except ImportError:
    # Relative import doesn't work for non-pip builds
    from utils import (
        ServerException,
        ClientException,
        FunctionNotFoundException,
        FunctionNotFoundWarning,
        ClientNotFound,
        GroupNotFound,
        MessageCacheMember,
        ClientInfo,
        Sendable,
        Client,
        _removeprefix,
        _dict_tupkey_lookup,
        _type_cast,
        _str_type_to_type_annotations_dict,
        receive_message,
        make_header,
        validate_ipv4,
        validate_command_not_reserved,
        ipstr_to_tup,
    )


# ░█████╗░░█████╗░██╗░░░██╗████████╗██╗░█████╗░███╗░░██╗██╗
# ██╔══██╗██╔══██╗██║░░░██║╚══██╔══╝██║██╔══██╗████╗░██║██║
# ██║░░╚═╝███████║██║░░░██║░░░██║░░░██║██║░░██║██╔██╗██║██║
# ██║░░██╗██╔══██║██║░░░██║░░░██║░░░██║██║░░██║██║╚████║╚═╝
# ╚█████╔╝██║░░██║╚██████╔╝░░░██║░░░██║╚█████╔╝██║░╚███║██╗
# ░╚════╝░╚═╝░░╚═╝░╚═════╝░░░░╚═╝░░░╚═╝░╚════╝░╚═╝░░╚══╝╚═╝
#   Change this code only if you know what you are doing!
# If this code is changed, the server may not work properly


class HiSockServer:
    """
    The server class for :mod:`HiSock`.

    :param addr: A two-element tuple, containing the IP address and the
        port number of where the server should be hosted.
        Due to the nature of reserved ports, it is recommended to host the
        server with a port number that's greater than or equal to 1024.
        **Only IPv4 is currently supported.**
    :type addr: tuple
    :param blocking: A boolean, set to whether the server should block the loop
        while waiting for message or not.
        Default passed in by :meth:`start_server` is True.
    :type blocking: bool, optional
    :param max_connections: The number of maximum connections the server
        should accept before refusing client connections. Pass in 0 for
        unlimited connections.
        Default passed in  by :meth:`start_server` is 0.
    :type max_connections: int, optional
    :param header_len: An integer, defining the header length of every message.
        A larger header length would mean a larger maximum message length
        (about 10**header_len).
        Any client connecting **MUST** have the same header length as the server,
        or else it will crash.
        Default passed in by :meth:`start_server` is 16 (maximum length: 10
        quadrillion bytes).
    :type header_len: int, optional
    :param cache_size: The number of messages to cache.
        Default passed in by :meth:`start_server` is -1.
    :type cache_size: int, optional
    :param keepalive: A bool indicating whether a keepalive signal should be sent or not.
        If this is True, then a signal will be sent to every client every minute to prevent
        hanging clients in the server. The clients have thirty seconds to send back an
        acknowledge signal to show that they are still alive.
        Default is True.
    :type keepalive: bool, optional

    :ivar tuple addr: A two-element tuple containing the IP address and the port.
    :ivar int header_len: An integer storing the header length of each "message".
    :ivar dict clients: A dictionary with the socket as its key and the
        client info as its value.
    :ivar dict clients_rev: A dictionary with the client info as its key
        and the socket as its value (for reverse lookup, up-to-date with
        :attr:`clients`).
    :ivar dict funcs: A list of functions registered with decorator :meth:`on`.
        **This is mainly used for under-the-hood-code.**

    :raises TypeError: If the address is not a tuple.
    """

    def __init__(
        self,
        addr: tuple[str, int],
        blocking: bool = True,
        max_connections: int = 0,
        header_len: int = 16,
        cache_size: int = -1,
        keepalive: bool = True,
    ):
        self.addr = addr
        self.header_len = header_len

        # Socket initialization
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(blocking)
        try:
            self.socket.bind(addr)
        except socket.gaierror as e:  # getaddrinfo error
            raise TypeError("The IP address and/or port are invalid.") from e
        self.socket.listen(max_connections)

        # Function related storage
        # {"command": {"func": Callable, "name": str, "type_hint": {"arg": Any}, "threaded": bool}}
        self.funcs = {}

        # Stores the names of the reserved functions and information about them
        # Used for the `on` decorator
        self._reserved_functions = {
            "join": {
                "number_arguments": 1,
                "type_cast_arguments": ("client_data",),
            },
            "leave": {
                "number_arguments": 1,
                "type_cast_arguments": ("client_data",),
            },
            "message": {
                "number_arguments": 3,
                "type_cast_arguments": ("client_data", "command", "message"),
            },
            "name_change": {
                "number_arguments": 3,
                "type_cast_arguments": ("client_data",),
            },
            "group_change": {
                "number_arguments": 3,
                "type_cast_arguments": ("client_data",),
            },
        }
        # {event_name: {"thread_event": threading.Event, "data": Union[None, bytes]}}
        # If catching all, then event_name will be a number sandwiched by dollar signs
        # Then `update` will handle the event with the lowest number
        self._recv_on_events = {}

        # Cache
        self.cache_size = cache_size
        # cache_size <= 0: No cache
        if cache_size > 0:
            self.cache = []

        # Dictionaries and lists for client lookup
        self._sockets_list = [self.socket]  # Our socket will always be the first
        # socket: {"ip": (ip, port), "name": str, "group": str}
        self.clients: dict[socket.socket, dict] = {}
        # ((ip: str, port: int), name: str, group: str): socket
        self.clients_rev: dict[tuple, socket.socket] = {}

        # Flags
        self.closed = False
        self._receiving_data = False

        # Keepalive
        self._keepalive_event = threading.Event()
        self._unresponsive_clients = []
        self._keepalive = keepalive

        if self._keepalive:
            keepalive_thread = threading.Thread(
                target=self._keepalive_thread, daemon=True
            )
            keepalive_thread.start()

    def __str__(self):
        """Example: <HiSockServer serving at 192.168.1.133:5000>"""

        return f"<HiSockServer serving at {':'.join(map(str, self.addr))}>"

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        """Returns how many clients are connected"""

        return len(self.clients)

    # Comparisons
    def __gt__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) > "192.168.1.133:5000" """

        if type(other) not in (self.__class__, str):
            raise TypeError("Type not supported for > comparison.")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) > IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    def __ge__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) >= "192.168.1.133:5000" """

        if type(other) not in (self.__class__, str):
            raise TypeError("Type not supported for >= comparison.")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) >= IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) >= IPv4Address(ip[0])

    def __lt__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) < "192.168.1.133:5000" """

        if type(other) not in (self.__class__, str):
            raise TypeError("Type not supported for < comparison.")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) < IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) < IPv4Address(ip[0])

    def __le__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) <= "192.168.1.133:5000" """

        if type(other) not in (self.__class__, str):
            raise TypeError("Type not supported for <= comparison.")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) <= IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) <= IPv4Address(ip[0])

    def __eq__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) == "192.168.1.133:5000" """

        if type(other) not in (self.__class__, str):
            raise TypeError("Type not supported for == comparison.")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) == IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    # Internal methods

    @staticmethod
    def _send_type_cast(content: Sendable = None) -> bytes:
        """
        Type casting content for the send methods.
        This method exists so type casting can easily be changed without changing
        it in all 6 send methods.

        :param content: The content to type cast
        :type content: Sendable
        :return: The type casted content
        :rtype: bytes

        :raises InvalidTypeCast: If the content cannot be type casted
        """

        return _type_cast(
            type_cast=bytes,
            content_to_type_cast=content,
            func_name="<server sending function>",
        )

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

    def _new_client_connection(
        self, connection: socket.socket, address: tuple[str, int]
    ):
        """
        Handle the client hello handshake.

        :param connection: The client socket.
        :type connection: socket.socket
        :param address: The client address.
        :type address: tuple[str, int]

        :raises ServerException: If the client is already connected.
        :raises ClientException: If the client disconnected or had an error.
        """

        if connection in self._sockets_list:
            raise ServerException("Client already connected.")

        self._sockets_list.append(connection)

        # Receive the client hello
        client_hello = receive_message(connection, self.header_len)
        if not client_hello:
            raise ClientException("Client disconnected or had an error.")
        client_hello = _removeprefix(client_hello["data"].decode(), "$CLTHELLO$")
        try:
            client_hello = json.loads(client_hello)
        except json.JSONDecodeError:
            raise ClientException("Client sent an invalid hello.") from None

        client_data = {
            "ip": address,
            "name": client_hello["name"],
            "group": client_hello["group"],
        }
        self.clients[connection] = client_data
        self.clients_rev[
            (
                address,
                client_hello["name"],
                client_hello["group"],
            )
        ] = connection

        # Send reserved command to existing clients
        self._send_all_clients_raw(f"$CLTCONN$ {json.dumps(client_data)}".encode())

        if "join" in self.funcs:
            self._call_function(
                "join",
                self._type_cast_client_data(command="join", client_data=client_data),
            )
            return

        warnings.warn("join", FunctionNotFoundWarning)

    def _client_disconnection(self, client_socket: socket.socket):
        """
        Handle a client disconnection.

        :raises ClientNotFound: The client wasn't connected to the server.
        """

        client_data = self.clients[client_socket]

        if client_socket not in self._sockets_list:
            raise ClientNotFound(f'Client "{client_socket}" is not connected.')

        try:
            client_socket.close()
        except OSError:
            # Already closed
            pass
        self._sockets_list.remove(client_socket)
        del self.clients[client_socket]
        del self.clients_rev[
            (client_data["ip"], client_data["name"], client_data["group"])
        ]
        # Note: ``self._unresponsive_clients`` should be handled by the keepalive

    # Keepalive

    def _handle_keepalive(self, client_socket: socket.socket):
        """
        Handles a keepalive acknowledgment sent by a client.

        :param client_socket: The client socket that sent the acknowledgment.
        :type client_socket: socket.socket
        """

        if client_socket in self._unresponsive_clients:
            self._unresponsive_clients.remove(client_socket)

    def _keepalive_thread(self):
        while not self._keepalive_event.is_set():
            self._keepalive_event.wait(30)

            # Send keepalive to all clients
            if not self._keepalive_event.is_set():
                for client_socket, client_data in self.clients.items():
                    self._unresponsive_clients.append(client_socket)
                    self._send_client_raw(client_data["ip"], "$KEEPALIVE$")

            # Keepalive acknowledgments will be handled in `_handle_keepalive`
            self._keepalive_event.wait(30)

            # Keepalive response wait is over, remove the unresponsive clients
            if not self._keepalive_event.is_set():
                for client_socket in self._unresponsive_clients:
                    self.disconnect_client(
                        self.clients[client_socket]["ip"], force=True, call_func=True
                    )
                self._unresponsive_clients.clear()

    def _call_function(self, func_name: str, *args, **kwargs):
        """
        Calls a function with the given arguments and returns the result.

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

    # On decorator

    class _on:
        """Decorator used to handle something when receiving command."""

        def __init__(
            self,
            outer: HiSockServer,
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
            if self.override and self.command in self.outer._reserved_functions:
                self.outer.funcs.pop(self.command, None)
                del self.outer._reserved_functions[self.command]

            self._assert_num_func_args_valid(len(func_args))

            # Store annotations of function
            annotations = _str_type_to_type_annotations_dict(
                inspect.getfullargspec(func).annotations
            )  # {"param": type}
            parameter_annotations = {}

            # Map function arguments into type hint compliant ones
            type_cast_arguments: tuple
            if self.command in self.outer._reserved_functions:
                type_cast_arguments = (
                    self.outer._reserved_functions[self.command]["type_cast_arguments"],
                )[0]
            else:
                type_cast_arguments = ("client_data", "message")

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
            }

            # Decorator stuff
            return func

        def _assert_num_func_args_valid(self, number_of_func_args: int):
            """
            Asserts the number of function arguments is valid.

            :raises ValueError: If the number of function arguments is invalid.
            """

            valid = False
            needed_number_of_args = "0-2"

            # Reserved commands
            try:
                needed_number_of_args = (
                    self.outer._reserved_functions[self.command]["number_arguments"],
                )[0]
                valid = number_of_func_args == needed_number_of_args

            # Unreserved commands
            except KeyError:
                valid = number_of_func_args <= 2

            if not valid:
                raise ValueError(
                    f"{self.command} command must have {needed_number_of_args} "
                    f"arguments, not {number_of_func_args}."
                )

    def on(
        self, command: str, threaded: bool = False, override: bool = False
    ) -> Callable:
        """
        A decorator that adds a function that gets called when the server
        receives a matching command.

        Reserved functions are functions that get activated on
        specific events, and they are:

        1. ``join`` - Activated when a client connects to the server
        2. ``leave`` - Activated when a client disconnects from the server
        3. ``message`` - Activated when a client messages to the server
        4. ``name_change`` - Activated when a client changes its name
        5. ``group_change`` - Activated when a client changes its group

        The parameters of the function depend on the command to listen.
        For example, reserved commands ``join`` and ``leave`` have only one
        client parameter passed, while reserved command ``message`` has two:
        client data and message.
        Other unreserved functions will also be passed in the same
        parameters as ``message``.

        In addition, certain type casting is available to both reserved and unreserved
        functions.
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
            in order to not block the run loop.
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

    def _get_client_from_name_or_ip_port(self, client: Client) -> socket.socket:
        """
        Gets a client socket from a name or tuple in the form of (ip, port).

        :param client: The name or tuple of the client.
        :type client: Client

        :return: The socket of the client.
        :rtype: socket.socket

        :raises ValueError: Client format is wrong.
        :raises ClientNotFound: Client does not exist.
        :raises UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        ret_client_socket: socket.socket

        # Search by IPv4
        if isinstance(client, tuple):
            validate_ipv4(client)  # Raises ValueError if invalid
            try:
                client_socket: socket.socket = next(
                    _dict_tupkey_lookup(
                        client,
                        self.clients_rev,
                        idx_to_match=0,
                    )
                )
            except StopIteration:
                raise ClientNotFound(
                    f'Client with IP "{client}" is not connected.'
                ) from None
            ret_client_socket = client_socket

        # Search by name
        elif isinstance(client, str):
            try:
                # Modify dictionary so only names are included
                try:
                    client = ipstr_to_tup(client)
                except ValueError:
                    client_sockets = list(
                        _dict_tupkey_lookup(
                            client,
                            self.clients_rev,
                            idx_to_match=1,
                        )
                    )
                else:
                    client_sockets = list(
                        _dict_tupkey_lookup(
                            client,
                            self.clients_rev,
                            idx_to_match=0,
                        )
                    )

            except StopIteration:
                raise TypeError(
                    f'Client with name "{client}" does not exist.'
                ) from None

            if len(client_sockets) > 1:
                warnings.warn(
                    f'{len(client_sockets)} clients with name "{client}" detected; sending data to '
                    f"Client with IP {':'.join(map(str, client_sockets[0].getpeername()))}"
                )
            ret_client_socket = client_sockets[0]
        else:
            raise ValueError("Client format is wrong (must be of type tuple or str).")

        if ret_client_socket is None:
            raise ValueError("Client socket does not exist.")

        return ret_client_socket

    def _get_all_client_sockets_in_group(self, group: str) -> Iterable[socket.socket]:
        """
        An iterable that returns all client sockets in a group

        :param group: The group to get the sockets from.
        :type group: str

        :return: An iterable of client sockets in the group.
        :rtype: Iterable[socket.socket]

        .. note::
           If the group does not exist, an empty iterable is returned.
        """

        return _dict_tupkey_lookup(group, self.clients_rev, idx_to_match=2)

    def get_group(self, group: str) -> list[dict[str, Union[str, socket.socket]]]:
        """
        Gets all clients from a specific group.

        .. note::
            If you want to get them from :ivar:`clients_rev` directly, use
            :meth:`_get_all_client_sockets_in_group` instead.

        :param group: A string, representing the group to look up
        :type group: str

        :raises GroupNotFound: Group does not exist

        :return: A list of dictionaries of clients in that group, containing
          the address, name, group, and socket
        :rtype: list
        """

        mod_group_clients = []  # Will be a list of dicts

        for client in self._get_all_client_sockets_in_group(group):
            client_dict = self.clients[client]
            mod_dict = {
                "ip": client_dict["ip"],
                "name": client_dict["name"],
                "group": client_dict["group"],
                "socket": client,
            }
            mod_group_clients.append(mod_dict)

        if len(mod_group_clients) == 0:
            raise GroupNotFound(f'Group "{group}" does not exist.')

        return mod_group_clients

    def get_all_clients(self, key: Union[Callable, str] = None) -> list[dict[str, str]]:
        """
        Get all clients currently connected to the server.
        This is recommended over the class attribute :ivar:`self._clients` or
        :ivar:`self.clients_rev`, as it is in a dictionary-like format.

        :param key: If specified, there are two outcomes: If it is a string,
            it will search for the dictionary for the key, and output it to a list
            (currently supports "ip", "name", "group").
            If it is a callable, it will try to integrate the callable
            into the output with the :meth:`filter` function.
        :type key: Union[Callable, str], optional

        :return: A list of dictionaries, with the clients
        :rtype: list[dict, ...]
        """

        clients = list(self.clients.values())

        if key is None:
            return clients

        filter_clients = []
        if isinstance(key, str):
            if key in ["ip", "name", "group"]:
                for filter_client in clients:
                    filter_clients.append(filter_client[key])
        elif isinstance(key, Callable):
            filter_clients = list(filter(key, clients))

        return filter_clients

    def get_client(
        self, client: Union[str, tuple[str, int]]
    ) -> dict[str, Union[str, socket.socket]]:
        """
        Gets the client data for a client from a name or tuple in the form of (ip, port).

        :return: The client data without the socket.
        :rtype: dict

        :raises ValueError: Client format is wrong.
        :raises ClientNotFound: Client does not exist.
        :raises UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        return self.clients[self._get_client_from_name_or_ip_port(client)]

    def get_addr(self) -> tuple[str, int]:
        """
        Gets the address of where the HiSock server is serving at.

        :return: A tuple of the address in the form of (ip, port)
        :rtype: tuple[str, int]
        """

        return self.addr

    # Transmit data

    def send_all_clients(self, command: str, content: Sendable = None):
        """
        Sends the command and content to *ALL* clients connected.

        :param command: A string, representing the command to send to every client.
        :type command: str
        :param content: The message / content to send
        :type content: Sendable, optional
        """

        data_to_send = (
            b"$CMD$" + command.encode() + b"$MSG$" + self._send_type_cast(content)
        )
        content_header = make_header(data_to_send, self.header_len)
        for client in self.clients:
            client.send(content_header + data_to_send)

    def _send_all_clients_raw(self, content: Sendable = None):
        """
        Sends the command and content to *ALL* clients connected *without a command*.

        .. note::
           This has been deprecated for dynamic arguments.
           Use :meth:`send_all_clients` instead.

        .. warning::
           The server will throw out any data that is not an unreserved
           or reserved command.

        :param content: The message / content to send
        :type content: Sendable
        """

        content_header = make_header(content, self.header_len)
        for client in self.clients:
            client.send(content_header + content)

    def send_group(
        self, group: Union[str, ClientInfo], command: str, content: Sendable = None
    ):
        """
        Sends data to a specific group.
        Groups are recommended for more complicated servers or multipurpose
        servers, as it allows clients to be divided, which allows clients to
        be sent different data for different purposes.
        :param group: A string or a ClientInfo, representing the group to send data to.
            If the group is a ClientInfo, and the client is in a group, the method will
            send data to that group.
        :type group: Union[str, ClientInfo]
        :param command: A string, containing the command to send
        :type command: str
        :param content: A bytes-like object, with the content/message
            to send
        :type content: Union[bytes, dict]

        :raises TypeError: If the group does not exist, or the client
            is not in a group (``ClientInfo``).
        """

        if isinstance(group, ClientInfo):
            client = group
            group = client.group  # Please don't confuse this

            if group is None:
                raise TypeError(f"Client {client} does not belong to a group")

        data_to_send = (
            b"$CMD$" + command.encode() + b"$MSG$" + self._send_type_cast(content)
        )
        content_header = make_header(data_to_send, self.header_len)
        for client in self._get_all_client_sockets_in_group(group):
            client.send(content_header + data_to_send)

    def send_client(self, client: Client, command: str, content: Sendable = None):
        """
        Sends data to a specific client.

        :param client: The client to send data to. The format could be either by IP+port,
            or a client name.
        :type client: Client
        :param command: A string, containing the command to send.
        :type command: str
        :param content: The message / content to send
        :type content: Sendable

        :raises ValueError: Client format is wrong.
        :raises ClientNotFound: Client does not exist.
        :raises UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        if isinstance(client, ClientInfo):
            client = client.ip

        data_to_send = (
            b"$CMD$" + command.encode() + b"$MSG$" + self._send_type_cast(content)
        )
        content_header = make_header(data_to_send, self.header_len)
        self._get_client_from_name_or_ip_port(client).send(
            content_header + data_to_send
        )

    def _send_client_raw(self, client: Client, content: Sendable = None):
        """
        Sends data to a specific client, *without a command*
        Different formats of the client is supported. It can be:

        :param client: The client to send data to. The format could be either by IP+port,
            or a client name.
        :type client: Client
        :param content: The message / content to send.
        :type content: Sendable

        :raises ValueError: Client format is wrong.
        :raises TypeError: Client does not exist.
        :raises UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        if isinstance(client, ClientInfo):
            client = client.ip

        data_to_send = self._send_type_cast(content)
        content_header = make_header(data_to_send, self.header_len)
        self._get_client_from_name_or_ip_port(client).send(
            content_header + data_to_send
        )

    def _send_group_raw(self, group: str, content: Sendable = None):
        """
        Sends data to a specific group, without commands.
        Groups are recommended for more complicated servers or multipurpose
        servers, as it allows clients to be divided, which allows clients to
        be sent different data for different purposes.
        :param group: A string or a ClientInfo, representing the group to send data to.
            If the group is a ClientInfo, and the client is in a group, the method will
            send data to that group. If the client's not in a group, it will return a
            ``TypeError``
        :type group: Union[str, ClientInfo]
        :param content: A bytes-like object, with the content/message
            to send
        :type content: Union[bytes, dict]
        :raise TypeError: The group does not exist, or the client
            is not in a group (``ClientInfo``)
        """

        if isinstance(group, ClientInfo):
            client = group
            group = client.group  # Please don't confuse this

            if group is None:
                raise TypeError(f"Client {client} does not belong to a group")

        data_to_send = self._send_type_cast(content)
        content_header = make_header(data_to_send, self.header_len)
        for client in self._get_all_client_sockets_in_group(group):
            client.send(content_header + data_to_send)

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
                if listener.startswith("$") and listener.endswith("$"):
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

    # Disconnect

    def disconnect_client(
        self, client: Client, force: bool = False, call_func: bool = False
    ):
        """
        Disconnects a specific client.

        :param client: The client to send data to. The format could be either by IP+port,
            a client name, or a ``ClientInfo`` instance.
        :type client: Client
        :param force: A boolean, specifying whether to force a disconnection
            or not. Defaults to False.
        :type force: bool, optional
        :param call_func: A boolean, specifying whether to call the ``leave`` reserved
            function when client is disconnected. Defaults to False.

        :raises ValueError: If the client format is wrong.
        :raises ClientNotFound: If the client does not exist.
        :raises UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        if isinstance(client, ClientInfo):
            client = client.ip

        client_socket = self._get_client_from_name_or_ip_port(client)
        client_data = self.clients[client_socket]

        if not force:
            try:
                self._send_client_raw(client, "$DISCONN$")
            except BrokenPipeError:
                # Client is already gone
                pass
        self._client_disconnection(client_socket)

        if call_func:
            if "leave" in self.funcs:
                self._call_function(
                    "leave",
                    self._type_cast_client_data(
                        command="leave", client_data=client_data
                    ),
                )
                return
            warnings.warn("leave", FunctionNotFoundWarning)

    def disconnect_all_clients(self, force=False):
        """Disconnect all clients."""

        if not force:
            self._send_all_clients_raw("$DISCONN$")
            return

        for conn in self._sockets_list:
            conn.close()

        self._sockets_list.clear()
        self._sockets_list.append(self.socket)  # Server socket must be first
        self.clients.clear()
        self.clients_rev.clear()
        self._unresponsive_clients.clear()  # BrokenPipeError with keepalive w/out clear

    # Run

    def _run(self):
        """
        Handles new messages and sends them to the appropriate functions. This method
        should be called in a while loop in a thread. If this function isn't in its
        own thread, then :meth:`recv` won't work.

        .. warning::
           Don't call this method on its own; instead use :meth:`start`.
        """

        if self.closed:
            return

        read_socket, write_socket, exception_socket = select.select(
            self._sockets_list, [], self._sockets_list
        )

        client_socket: socket.socket
        for client_socket in read_socket:
            ### Reserved commands ###

            # Handle bad client
            if client_socket.fileno() == -1:
                self.disconnect_client(
                    self.clients[client_socket]["ip"], force=True, call_func=False
                )
                continue

            # Handle new connection
            if client_socket == self.socket:
                self._new_client_connection(*self.socket.accept())
                continue

            ### Receiving data ###
            decoded_data: str = ""

            # {"header": bytes, "data": bytes} or False
            self._receiving_data = True
            raw_data = receive_message(client_socket, self.header_len)
            self._receiving_data = False

            if isinstance(raw_data, dict):
                data = raw_data["data"]
                decoded_data = data.decode()

            try:
                client_data = self.clients[client_socket]
            except KeyError:
                raise ClientNotFound(
                    "Client data not found, but is not a new client."
                ) from KeyError

            ### Reserved commands ###

            # Handle client disconnection
            if (
                not raw_data  # Most likely client disconnect, could be client error
                or decoded_data.startswith("$USRCLOSE$")
            ):
                try:
                    self.disconnect_client(
                        client_data["ip"], force=False, call_func=True
                    )
                except BrokenPipeError:  # UNIX
                    # Client is already gone
                    pass
                continue

            # Handle keepalive acknowledgement
            if decoded_data.startswith("$KEEPACK$"):
                self._handle_keepalive(client_socket)
                continue

            # Get client
            if decoded_data.startswith("$GETCLT$"):
                try:
                    client_identifier = _removeprefix(decoded_data, "$GETCLT$")

                    # Determine if the client identifier is a name or an IP+port
                    try:
                        validate_ipv4(client_identifier)
                        client_identifier = ipstr_to_tup(client_identifier)
                    except ValueError:
                        pass

                    client = self.get_client(client_identifier)
                except ValueError as e:
                    client = {"traceback": str(e)}
                except ClientNotFound:
                    client = {"traceback": "$NOEXIST$"}

                self._send_client_raw(client_data["ip"], client)
                continue

            # Change name or group
            for matching_reserve, key in zip(
                ("$CHNAME$", "$CHGROUP$"), ("name", "group")
            ):
                if not decoded_data.startswith(matching_reserve):
                    continue

                change_to = _removeprefix(decoded_data, matching_reserve)

                # Resetting
                if change_to == "":
                    change_to = client_data[key]

                # Change it
                changed_client_data = client_data.copy()
                changed_client_data[key] = change_to
                self.clients[client_socket] = changed_client_data

                del self.clients_rev[
                    (
                        client_data["ip"],
                        client_data["name"],
                        client_data["group"],
                    )
                ]
                self.clients_rev[
                    (
                        changed_client_data["ip"],
                        changed_client_data["name"],
                        changed_client_data["group"],
                    )
                ] = client_socket

                # Call reserved function
                reserved_func_name = f"{key}_change"

                if reserved_func_name in self._reserved_functions:
                    old_value = client_data[key]
                    new_value = changed_client_data[key]

                    self._call_function(
                        reserved_func_name,
                        self._type_cast_client_data(
                            command=reserved_func_name,
                            client_data=changed_client_data,
                        ),
                        old_value,
                        new_value,
                    )

            ### Unreserved commands ###

            if not decoded_data.startswith("$CMD$"):
                return  # Random data? No need to cache anyways...

            has_listener = False  # For cache

            # Get command and message
            command = decoded_data.lstrip("$CMD$").split("$MSG$")[0]
            content = _removeprefix(decoded_data, "$CMD$" + command + "$MSG$")

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
                if len(func["type_hint"]) != 0:
                    type_casted_client_data = self._type_cast_client_data(
                        command=matching_command, client_data=client_data
                    )
                # client_data
                if len(func["type_hint"].keys()) == 1:
                    arguments = (type_casted_client_data,)
                # client_data, message
                elif len(func["type_hint"].keys()) >= 2:
                    arguments = (
                        type_casted_client_data,
                        _type_cast(
                            type_cast=func["type_hint"]["message"],
                            content_to_type_cast=content,
                            func_name=func["name"],
                        ),
                    )
                self._call_function(matching_command, *arguments)
                break

            # Handle data needed for `recv`
            for listener in self._recv_on_events:
                # Catch-all listeners
                # `listener` transverses in-order, so the first will be the minimum
                should_continue = False
                if not (listener.startswith("$") and listener.endswith("$")):
                    should_continue = True

                # Specific listeners
                if listener not in self._recv_on_events:
                    should_continue = True

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
                            "header": raw_data["header"],
                            "command": command,
                            "content": cache_content,
                            "called": has_listener,
                        }
                    )
                )

                # Pop oldest from stack
                if len(self.cache) > self.cache_size:
                    self.cache.pop(0)

            # Call `message` function
            if "message" not in self.funcs:
                continue

            self._call_function(
                "message",
                self._type_cast_client_data(command="message", client_data=client_data),
                _type_cast(
                    type_cast=self.funcs["message"]["type_hint"]["command"],
                    content_to_type_cast=command,
                    func_name="message <command>",
                ),
                _type_cast(
                    type_cast=self.funcs["message"]["type_hint"]["message"],
                    content_to_type_cast=content,
                    func_name="message <message>",
                ),
            )

    # Stop

    def close(self):
        """
        Closes the server; ALL clients will be disconnected, then the
        server socket will be closed.

        Running `server.run()` won't do anything now.
        """

        self.closed = True
        self._keepalive_event.set()
        self.disconnect_all_clients()
        self.socket.close()

    # Main loop

    def start(self):
        """Start the main loop for the server."""

        def loop():
            while not self.closed:
                try:
                    self._run()
                except KeyboardInterrupt:
                    self.close()

        loop_thread = threading.Thread(target=loop, daemon=False)
        loop_thread.start()


def start_server(addr, blocking=True, max_connections=0, header_len=16):
    """
    Creates a :class:`HiSockServer` instance. See :class:`HiSockServer` for
    more details and documentation.

    :return: A :class:`HiSockServer` instance.
    """

    return HiSockServer(addr, blocking, max_connections, header_len)


if __name__ == "__main__":
    print("Testing server!")
    server = start_server(("127.0.0.1", int(input("Port: "))))

    @server.on("join")
    def on_join(client_data: dict):
        print(
            f'{client_data["name"]} has joined! '
            f'Their IP is {":".join(map(str, client_data["ip"]))}. '
            f'Their group is {client_data["group"]}.'
        )

    @server.on("leave")
    def on_leave(client_data: dict):
        print(f'{client_data["name"]} has left!')

    @server.on("message")
    def on_message(client_data: dict, command: str, message: str):
        print(
            f'[MESSAGE CATCH-ALL] {client_data["name"]} sent a command, {command} '
            f'with the message "{message}".'
        )

    @server.on("name_change")
    def on_name_change(_: dict, old_name: str, new_name: str):  # Client data isn't used
        print(f"{old_name} changed their name to {new_name}.")

    @server.on("group_change")
    def on_group_change(client_data: dict, old_group: str, new_group: str):
        print(f"{client_data['name']} changed their group to {new_group}.")
        # Alert clients of change
        server.send_group(
            old_group,
            "message",
            f'{client_data["name"]} has left to move to {new_group}.',
        )
        server.send_group(
            new_group,
            "message",
            f'{client_data["name"]} has joined from {old_group}.',
        )

    @server.on("ping")
    def on_ping(client_data: dict):
        print(f"{client_data['name']} pinged!")
        server.send_client(client_data["ip"], "pong")

    @server.on("get_all_clients")
    def on_all_clients(client_data: dict):
        print(f"{client_data['name']} asked for all clients!")
        server.send_client(client_data["ip"], "all_clients", server.get_all_clients())

    @server.on("broadcast_message")
    def on_broadcast_message(client_data: dict, message: str):
        print(f'{client_data["name"]} said "{message}"!')
        server.send_all_clients("message", message)

    @server.on("set_timer", threaded=True)
    def on_set_timer(client_data: dict, seconds: int):
        print(f'{client_data["name"]} set a timer for {seconds} seconds!')
        __import__("time").sleep(seconds)
        print(f'{client_data["name"]}\'s timer is done!')
        server.send_client(client_data["ip"], "timer_done")

    @server.on("commit_genocide")
    def on_commit_genocide():
        print("It's time to genocide the connected clients.")
        server.send_all_clients("genocide", None)

    server.start()
