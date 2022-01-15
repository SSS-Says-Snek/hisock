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
from typing import Callable, Union, Any  # Type hints
from ipaddress import IPv4Address  # Comparisons
from hisock import constants

try:
    # Pip builds require relative import
    from .utils import (
        NoHeaderWarning,
        NoMessageException,
        InvalidTypeCast,
        ServerException,
        FunctionNotFoundException,
        FunctionNotFoundWarning,
        ClientNotFound,
        GroupNotFound,
        MessageCacheMember,
        Sendable,
        Client,
        _removeprefix,
        _dict_tupkey_lookup,
        _dict_tupkey_lookup_key,
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
        NoHeaderWarning,
        NoMessageException,
        InvalidTypeCast,
        ServerException,
        FunctionNotFoundException,
        FunctionNotFoundWarning,
        ClientNotFound,
        GroupNotFound,
        MessageCacheMember,
        Sendable,
        Client,
        _removeprefix,
        _dict_tupkey_lookup,
        _dict_tupkey_lookup_key,
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

    :raise TypeError: If the address is not a tuple.
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
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(blocking)
        try:
            self.sock.bind(addr)
        except socket.gaierror:  # getaddrinfo error
            raise TypeError("The IP address and/or port are invalid.")
        self.sock.listen(max_connections)

        # Function related storage
        # {"func_name": {"func": Callable, "name": str, "type_hint": {"arg": Any}, "threaded": bool}}
        self.funcs = {}
        # Stores the names of the reserved functions
        # Used for the `on` decorator
        self._reserved_functions = (
            "join",
            "leave",
            "message",
            "name_change",
            "group_change",
        )
        # Stores the number of parameters each reserved function takes
        # Used for the `on` decorator
        self._reserved_functions_parameters_num = (
            1,  # join
            1,  # leave
            2,  # message
            3,  # name_change
            3,  # group_change
        )

        # Cache
        self.cache_size = cache_size
        # cache_size <= 0: No cache
        if cache_size > 0:
            self.cache = []

        # Dictionaries and lists for client lookup
        self._sockets_list = [self.sock]  # Our socket will always be the first
        # socket: {"ip": (ip, port), "name": str, "group": str}
        self.clients = {}
        # ((ip: str, port: int), name: str, group: str): socket
        self.clients_rev = {}

        # Flags
        self.closed = False

        # Keepalive
        self._keepalive_event = threading.Event()
        self._unresponsive_clients = []
        self.keepalive = keepalive

        if self.keepalive:
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

        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for > comparison.")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) > IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    def __ge__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) >= "192.168.1.133:5000" """

        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for >= comparison.")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) >= IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) >= IPv4Address(ip[0])

    def __lt__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) < "192.168.1.133:5000" """

        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for < comparison.")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) < IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) < IPv4Address(ip[0])

    def __le__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) <= "192.168.1.133:5000" """

        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for <= comparison.")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) <= IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) <= IPv4Address(ip[0])

    def __eq__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) == "192.168.1.133:5000" """

        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for == comparison.")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) == IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    # Internal methods

    def _new_client_connection(
        self, connection: socket.socket, address: tuple[str, int]
    ):
        """
        Handle the client hello handshake

        :param connection: The client socket
        :type connection: socket.socket
        :param address: The client address
        :type address: tuple[str, int]

        :raise ServerException: If the client is already connected
        """

        if connection in self._sockets_list:
            raise ServerException("Client already connected.")

        self._sockets_list.append(connection)

        # Receive the client hello
        client_hello = receive_message(connection, self.header_len)

        client_hello = _removeprefix(client_hello["data"].decode(), "$CLTHELLO$ ")
        client_hello = json.loads(client_hello)

        client_info = {
            "ip": address,
            "name": client_hello["name"],
            "group": client_hello["group"],
        }
        self.clients[connection] = client_info
        self._update_clients_rev_dict()

        # Send reserved command to existing clients
        self.send_all_clients_raw(f"$CLTCONN$ {json.dumps(client_info)}".encode())

        if "join" in self.funcs:
            self._call_function("join", False, client_info)
            return

        warnings.warn("join", FunctionNotFoundWarning)

    def _client_disconnection(self, client: socket.socket, call_func: bool = True):
        """
        Handle a client disconnecting

        :param client: The client socket
        :type client: socket.socket
        :param call_func: Whether to call the leave function
        :type call_func: bool

        :raise ClientNotFound: The client wasn't connected to the server
        """

        if client not in self._sockets_list:
            raise ClientNotFound(f'Client "{client}" is not connected.')

        # Save the client info for leave command
        client_info = self.clients[client]

        # Remove socket from lists and dictionaries
        self._sockets_list.remove(client)
        del self.clients[client]
        self._update_clients_rev_dict()

        if not call_func:
            return

        if "leave" in self.funcs:
            self._call_function("leave", False, client_info)
            return

        warnings.warn("leave", FunctionNotFoundWarning)

    def _update_clients_rev_dict(self, idx: int = None):
        """
        Updates the reversed clients dictionary to the normal dictionary

        :param idx: Index of the client to update if known. If not known,
            the whole dictionary will be updated.
        :type idx: int

        :raise IndexError: If the client idx doesn't exist.
        :raise TypeError: If the client idx is not an integer.
        :raise KeyError: If the client doesn't exist in :ivar:`self.clients`
        :raise KeyError: If the client isn't a valid client.
        """

        clients = self.clients
        if idx is not None:
            clients = (self.clients[self._sockets_list[idx]],)

        # There was a client removed
        if len(self.clients_rev) > len(self._sockets_list) - 1:
            self.clients_rev.clear()

        for client_socket, client_info in clients.items():
            self.clients_rev[
                (client_info["ip"], client_info["name"], client_info["group"])
            ] = client_socket

    def _send_type_cast(self, content: Sendable = None) -> bytes:
        """
        Type casting content for the send methods.
        This method exists so type casting can easily be changed without changing
        it in all 6 send methods.

        :param content: The content to type cast
        :type content: Sendable
        :return: The type casted content
        :rtype: bytes

        :raise InvalidTypeCast: If the content cannot be type casted
        """

        return _type_cast(bytes, content, "<server sending function>")

    # Keepalive

    def _handle_keepalive(self, client_socket: socket.socket):
        """
        Handles a keepalive acknowledgment sent by a client.

        :param client_socket: The client socket that sent the acknowledgment.
        :type client_socket: socket.socket
        """

        if client_socket in self._unresponsive_clients:
            self._unresponsive_clients.remove(client_socket)

        # DEBUG PRINT PLEASE REMOVE LATER
        print(f"{self.clients[client_socket]['ip']} is alive.")

    def _keepalive_thread(self):
        while not self._keepalive_event.is_set():
            self._keepalive_event.wait(30)

            # Send keepalive to all clients
            if not self._keepalive_event.is_set():
                for client in self.clients:
                    self._unresponsive_clients.append(client)
                    self.send_client_raw(self.clients[client]["ip"], "$KEEPALIVE$")

            # Keepalive acknowledgments will be handled in `_handle_keepalive`
            self._keepalive_event.wait(30)

            # Keepalive response wait is over, remove the unresponsive clients
            if not self._keepalive_event.is_set():
                for client in self._unresponsive_clients:
                    self.disconnect_client(self.clients[client]["ip"], force=True)
                self._unresponsive_clients.clear()

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

        :raise FunctionNotFoundException: If the function is not found.
        """

        func: dict

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
        """Decorator used to handle something when receiving command"""

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

            :raise ValueError: If the number of function arguments is invalid.
            """

            func_args = inspect.getfullargspec(func).args

            # Overriding a reserved command, remove it from reserved functions
            if self.override:
                if self.command in self.outer.reserved_commands.keys():
                    self.outer.funcs.pop(self.command)

                index = self.outer._reserved_functions.index(self.command)
                self.outer._reserved_functions.pop(index)
                self.outer._reserved_functions_parameters_num.pop(index)

            self._assert_num_func_args_valid(len(func_args))

            # Store annotations of function
            annotations = _str_type_to_type_annotations_dict(
                inspect.getfullargspec(func).annotations
            )  # {"param": type}
            parameter_annotations = {}

            # Process unreserved commands and reserved `message` (only reserved
            # command to have 2 arguments)
            if (
                self.command not in self.outer._reserved_functions
                or self.command == "message"
            ):
                # Map function arguments into type hint compliant ones
                for func_argument, argument_name in zip(
                    func_args, ("client_data", "message")
                ):
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

            :raise ValueError: If the number of function arguments is invalid.
            """

            valid = False
            needed_number_of_args = "0-2"

            # Reserved commands
            try:
                index_of_reserved_command = (
                    self.outer._reserved_functions.index(self.command),
                )[0]
                needed_number_of_args = (
                    self.outer._reserved_functions_parameters_num[
                        index_of_reserved_command
                    ],
                )[0]
                valid = number_of_func_args == needed_number_of_args

            # Unreserved commands
            except ValueError:
                valid = not (number_of_func_args > 2)

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
        receives a matching command

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

        For more information, read the wiki for type casting.

        :param command: A string representing the command the function should activate
            when receiving it.
        :type command: str
        :param threaded: A boolean representing if the function should be run in a thread
            in order to not block the run() loop.
            Default is False.
        :type threaded: bool
        :param override: A boolean representing if the function should override the
            reserved function with the same name and to treat it as an unreserved function.
            Default is False.
        :type override: bool
        :return: The same function (the decorator just appended the function to a stack).
        :rtype: function

        :raise ValueError: If the number of function arguments is invalid.
        """

        # Passes in outer to _on decorator/class
        return self._on(self, command, threaded, override)

    # Getters

    def _get_client_from_name_or_ip_port(self, client: Client) -> socket.socket:
        """
        Gets a client socket from a name or tuple in the form of (ip, port).

        :param client: The name or tuple of the client.
        :type client: Client
        :return: The socket of the client.
        :rtype: socket.socket

        :raise ValueError: Client format is wrong.
        :raise ClientNotFound: Client does not exist.
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        ret_client_socket = None

        # Search by IPv4
        if isinstance(client, tuple):
            try:
                validate_ipv4(client)  # Raises ValueError if invalid
                client_socket: socket.socket = next(
                    _dict_tupkey_lookup(
                        client,
                        self.clients_rev,
                        idx_to_match=0,
                    )
                )
            except StopIteration:
                raise ClientNotFound(f'Client with IP "{client}" is not connected.')

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
                raise TypeError(f'Client with name "{client}" does not exist.')

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

    def _get_all_client_sockets_in_group(self, group: str) -> iter[socket.socket]:
        """
        An iterable that returns all client sockets in a group

        :param group: The group to get the sockets from.
        :type group: str
        :return: An iterable of client sockets in the group.
        :rtype: iter[socket.socket]

        .. note::
           If the group does not exist, an empty iterable is returned.
        """

        return _dict_tupkey_lookup(group, self.clients_rev, idx_to_match=2)

    def get_group(self, group: str) -> list[dict[str, Union[str, socket.socket]]]:
        """
        Gets all clients from a specific group

        :param group: A string, representing the group to look up
        :type group: str

        :raise GroupNotFound: Group does not exist

        :return: A list of dictionaries of clients in that group, containing
          the address, name, group, and socket
        :rtype: list

        .. note::
            If you want to get them from :ivar:`clients_rev` directly, use
            :meth:`_get_all_client_sockets_in_group` instead.
        """

        mod_group_clients = []  # Will be a list of dicts

        for client in self._get_all_client_sockets_in_group(group):
            socket = self.clients_rev[client]
            mod_dict = {
                "ip": client[0],
                "name": client[1],
                "group": client[2],
                "socket": socket,
            }
            mod_group_clients.append(mod_dict)

        if len(mod_group_clients) == 0:
            raise GroupNotFound(f'Group "{group}" does not exist.')

        return mod_group_clients

    def get_all_clients(
        self, key: Union[Callable, str] = None
    ) -> list[dict[str, str]]:  # TODO: Add socket output as well
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

        clients = []
        for client in self.clients_rev:
            client_dict = {
                dict_key: client[value]
                for value, dict_key in enumerate(("ip", "name", "group"))
            }
            clients.append(client_dict)

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

        :raise ValueError: Client format is wrong.
        :raise ClientNotFound: Client does not exist.
        :raise UserWarning: Using client name, and more than one client with
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

    def send_all_clients_raw(self, content: Sendable = None):
        """
        Sends the command and content to *ALL* clients connected *without a command*.

        :param content: The message / content to send
        :type content: Sendable
        """

        content_header = make_header(content, self.header_len)
        for client in self.clients:
            client.send(content_header + content)

    def send_group(self, group: str, command: str, content: Sendable = None):
        """
        Sends data to a specific group.
        Groups are recommended for more complicated servers or multipurpose
        servers, as it allows clients to be divided, which allows clients to
        be sent different data for different purposes.

        :param group: A string, representing the group to send data to.
        :type group: str
        :param command: A string, containing the command to send.
        :type command: str
        :param content: The message / content to send
        :type content: Sendable

        :raise GroupNotFound: The group does not exist.
        """

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

        :raise ValueError: Client format is wrong.
        :raise ClientNotFound: Client does not exist.
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        data_to_send = (
            b"$CMD$" + command.encode() + b"$MSG$" + self._send_type_cast(content)
        )
        content_header = make_header(data_to_send, self.header_len)
        self._get_client_from_name_or_ip_port(client).send(
            content_header + data_to_send
        )

    def send_client_raw(self, client: Client, content: Sendable = None):
        """
        Sends data to a specific client, *without a command*
        Different formats of the client is supported. It can be:

        :param client: The client to send data to. The format could be either by IP+port,
            or a client name.
        :type client: Client
        :param content: The message / content to send.
        :type content: Sendable

        :raise ValueError: Client format is wrong.
        :raise TypeError: Client does not exist.
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        data_to_send = self._send_type_cast(content)
        content_header = make_header(data_to_send, self.header_len)
        print(f"{content_header=}, {data_to_send=}")
        self._get_client_from_name_or_ip_port(client).send(
            content_header + data_to_send
        )

    def send_group_raw(self, group: str, content: Sendable = None):
        """
        Sends data to a specific group, without commands.
        Groups are recommended for more complicated servers or multipurpose
        servers, as it allows clients to be divided, which allows clients to
        be sent different data for different purposes.

        Non-command-attached content is recommended to be used alongside with
        :meth:`HiSockClient.recv_raw`.

        :param group: A string, representing the group to send data to.
        :type group: str
        :param content: The message / content to send
        :type content: Sendable

        :raise GroupNotFound: The group does not exist.
        """

        data_to_send = self._send_type_cast(content)
        content_header = make_header(data_to_send, self.header_len)
        for client in self._get_all_client_sockets_in_group(group):
            client.send(content_header + data_to_send)

    def recv_raw(self, ignore_reserved: bool = False) -> bytes:
        """
        Waits (blocks) until a message is sent, and returns that message.
        This is not recommended for content with commands attached;
        it is meant to be used alongside with :func:`HiSockClient.send_raw`.

        :param ignore_reserved: A boolean, representing if the function should ignore
            reserved commands.
            Default is False.
        :type ignore_reserved: bool, optional

        .. note::
            If the message is a keepalive, the client will send an acknowledgement and
            then ignore it, even if ``ignore_reserved`` is False.

        :return: A bytes-like object, containing the content/message
            the client first receives
        :rtype: bytes
        """

        def _handle_data(data: bytes):
            # DEBUG PRINT PLEASE REMOVE LATER
            print(f"Received data: {data}")

            # Reserved commands
            reserved_command = True
            try:
                validate_command_not_reserved(str(data))
            except ValueError:
                reserved_command = False

            if reserved_command and not ignore_reserved:
                return self.recv_raw()

            return data

        # Sometimes, `update` can be running at the same time as this is running
        # (e.x. if this is in a thread). In this case, `update` will receive the data
        # and send it to us, as we cannot receive data at the same time as it receives
        # data.

        if self._receiving_data:
            self._recv_data = "I NEED YOUR DATA"

            # Wait until the data is received
            while self._recv_data == "I NEED YOUR DATA":
                "...waiting..."

            # Data is received
            data_received = self._recv_data
            self._recv_data = ""
            return _handle_data(data_received)

        self._receiving_data = True
        message_len = int(self.sock.recv(self.header_len).decode())
        data_received = self.sock.recv(message_len)
        self._receiving_data = False

        return _handle_data(data_received)

    # Disconnect

    def disconnect_client(self, client: Client, force: bool = False):
        """
        Disconnects a specific client.

        :param client: The client to send data to. The format could be either by IP+port,
            or a client name.
        :type client: Client

        :raise ValueError: If the client format is wrong.
        :raise ClientNotFound: If the client does not exist.
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        client_socket = self._get_client_from_name_or_ip_port(client)

        if not force:
            self.send_client_raw(self.clients[client_socket]["ip"], b"$DISCONN$")
            return

        client_socket.close()
        self._sockets_list.remove(client_socket)
        del self.clients[client_socket]
        self._update_clients_rev_dict()
        # Note: ``self._unresponsive_clients`` should be handled by the keepalive

    def disconnect_all_clients(self, force=False):
        """Disconnect all clients."""

        if not force:
            self.send_all_clients_raw("$DISCONN$")
            return

        (conn.close() for conn in self._sockets_list)
        self._sockets_list.clear()
        self.clients.clear()
        self.clients_rev.clear()
        self._unresponsive_clients.clear()

    def run(self):
        """
        Runs the server. This method handles the sending and receiving of data,
        so it should be run once every iteration of a while loop, as to not
        lose valuable information.
        """

        if self.closed:
            return

        read_sock, write_sock, exception_sock = select.select(
            self._sockets_list, [], self._sockets_list
        )

        for client_socket in read_sock:
            # Handle bad client
            if client_socket.fileno() == -1:
                self._client_disconnection(client_socket, call_func=False)
                continue

            ### Reserved ###

            # Handle new connection
            if client_socket == self.sock:
                self._new_client_connection(*self.sock.accept())
                continue

            # Receiving data

            # "header" - The header of the message, mostly unneeded
            # "data" - The actual data/content of the message (type: bytes)
            data = receive_message(client_socket, self.header_len)

            # DEBUG PRINT PLEASE REMOVE LATER
            print(f"{data=}")

            # Handle client disconnection
            if (
                not data  # Most likely client disconnect, could be client error
                or data["data"] == b"$USRCLOSE$"
            ):
                self._client_disconnection(client_socket)
                continue

            # Handle keepalive acknowledgement
            if data["data"].startswith(b"$KEEPACK$"):
                self._handle_keepalive(client_socket)
                continue

            # Actual client message received
            client_data = self.clients[client_socket]

            # Get client
            if data["data"].startswith(b"$GETCLT$"):
                try:
                    client_identifier = _removeprefix(
                        data["data"], b"$GETCLT$ "
                    ).decode()

                    # Determine if the client identifier is a name or an IP+port
                    try:
                        validate_ipv4(client_identifier)
                        client_identifier = ipstr_to_tup(client_identifier)
                    except ValueError:
                        pass

                    client = self.get_client(client_identifier)
                except ValueError as e:
                    client = {"traceback": f"{e!s}"}
                except ClientNotFound:
                    client = {"traceback": f"$NOEXIST$"}

                self.send_client_raw(self.clients[client_socket]["ip"], client)
                continue

            # Change name or group
            for matching_reserve, key in zip(
                (b"$CHNAME$", b"$CHGROUP$"), ("name", "group")
            ):
                if not data["data"].startswith(matching_reserve):
                    continue

                change_to = _removeprefix(
                    data["data"], matching_reserve + b" "
                ).decode()

                # Resetting
                if change_to == data["data"].decode():
                    change_to = None

                client_info = self.clients[client_socket]

                # Change it
                changed_client_info = client_info.copy()
                changed_client_info[key] = change_to
                self.clients[client_socket] = changed_client_info
                self._update_clients_rev_dict()

                # Call reserved function
                reserved_func_name = f"{key}_change"

                if reserved_func_name in self._reserved_functions:
                    old_value = client_info[key]
                    new_value = changed_client_info[key]

                    self._call_function(
                        reserved_func_name,
                        False,
                        changed_client_info,
                        old_value,
                        new_value,
                    )

            ### Unreserved ###

            has_corresponding_function = False  # For cache

            decoded_data = data["data"].decode()
            if decoded_data.startswith("$CMD$"):
                command = decoded_data.lstrip("$CMD$").split("$MSG$")[0]
                content = _removeprefix(decoded_data, "$CMD$" + command + "$MSG$")
                # No content? (_removeprefix didn't do anything)
                if not content or content == decoded_data:
                    content = None

                for matching_command, func in self.funcs.items():
                    if not command == matching_command:
                        continue

                    # Call function with dynamic args

                    arguments = ()
                    # client_data
                    if len(func["type_hint"].keys()) == 1:
                        arguments = (client_data,)
                    # client_data, message
                    elif len(func["type_hint"].keys()) >= 2:
                        arguments = (
                            client_data,
                            _type_cast(
                                func["type_hint"]["message"], content, func["name"]
                            ),
                        )

                    # DEBUG PRINT PLEASE REMOVE LATER
                    print(
                        f"{command=} {arguments=} len: {len(arguments)} {arguments}"
                        f"list of type hints: {tuple(func['type_hint'].keys())}"
                    )

                    self._call_function(func["name"], True, *arguments)
            else:
                # Not a reserved or unreserved message??
                # Should it be handled by `recv_raw`?
                print(f'Unhandled message: {data["data"]}')

            # Caching
            if self.cache_size >= 0:
                cache_content = content if has_corresponding_function else data["data"]
                self.cache.append(
                    MessageCacheMember(
                        {
                            "header": data["header"],
                            "command": command,
                            "content": cache_content,
                            "called": has_corresponding_function,
                        }
                    )
                )

                # Pop oldest from stack
                if len(self.cache) > self.cache_size:
                    self.cache.pop(0)

            # Extra special case! Message reserved (listens on every command)
            if "message" not in self.funcs.keys():
                continue

            client_data = self.clients[client_socket]
            content = data["data"]

            self._call_function(
                "message",
                False,
                client_data,
                _type_cast(
                    self.funcs["message"]["type_hint"]["message"],
                    content,
                    func_name="message",
                ),
            )

    def close(self):
        """
        Closes the server; ALL clients will be disconnected, then the
        server socket will be closed.

        Running `server.run()` won't do anything now.
        """

        self.closed = True
        self._keepalive_event.set()
        self.disconnect_all_clients()
        self.sock.close()


class ThreadedHiSockServer(HiSockServer):
    """
    A downside of :class:`HiSockServer` is that you need to constantly
    :meth:`run` it in a while loop, which may block the program. Fortunately,
    in Python, you can use threads to do two different things at once. Using
    :class:`ThreadedHiSockServer`, you would be able to run another
    blocking program, without ever fearing about blocking and all that stuff.

    .. note::
       In some cases though, :class:`HiSockServer` offers more control than
       :class:`ThreadedHiSockServer`, so be careful about when to use
       :class:`ThreadedHiSockServer` over :class:`HiSockServer`

    .. note::
        For documentation, see :class:`HiSockServer`.
    """

    def __init__(
        self, addr, *args, blocking=True, max_connections=0, header_len=16, **kwargs
    ):
        super().__init__(addr, blocking, max_connections, header_len, *args, **kwargs)
        self._thread = threading.Thread(target=self._run)

        self._stop_event = threading.Event()

        # This class shouldn't be able to be called through :meth:`HiSockServer.run`,
        # so we will kindly "exterminate" it
        # If you want to run it manually, you need to call :meth:`_run`
        del self.run

    def start_server(self):
        """Starts the main server loop"""

        self._thread.start()

    def stop_server(self):
        """Stops the server"""

        self._stop_event.set()
        self.sock.close()

    def _run(self):
        """
        The main while loop to run the thread

        Refer to :class:`HiSockServer` for more details

        .. warning::
           This method is **NOT** recommended to be used in an actual
           production environment. This is used internally for the thread, and should
           not be interacted with the user.
        """

        while not self._stop_event.is_set():
            try:
                HiSockServer.run(self)  # We deleted :meth:`self.run`
            except (OSError, ValueError):
                break

    def _join(self):
        """Waits for the thread to be killed"""

        self._thread.join()


def start_server(addr, blocking=True, max_connections=0, header_len=16):
    """
    Creates a :class:`HiSockServer` instance. See :class:`HiSockServer` for
    more details and documentation.

    :return: A :class:`HiSockServer` instance.
    """

    return HiSockServer(addr, blocking, max_connections, header_len)


def start_threaded_server(addr, blocking=True, max_connections=0, header_len=16):
    """
    Creates a :class:`ThreadedHiSockServer` instance. See :class:`HiSockServer`
    for more details and documentation.

    :return: A :class:`ThreadedHiSockServer` instance.
    """

    return ThreadedHiSockServer(addr, blocking, max_connections, header_len)


if __name__ == "__main__":
    # Tests
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
    def on_message(client_data: dict, message: str):
        print(f'[MESSAGE CATCH-ALL] {client_data["name"]} says "{message}".')

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
        server.send_client_raw(client_data["ip"], "pong")

    @server.on("all_clients")
    def on_all_clients(client_data: dict):
        print(f"{client_data['name']} asked for all clients!")
        server.send_client_raw(client_data["ip"], server.get_all_clients())

    @server.on("broadcast_message")
    def on_broadcast_message(client_data: dict, message: str):
        print(f'{client_data["name"]} said "{message}"!')
        server.send_all_clients("message", message)

    @server.on("set_timer", threaded=True)
    def on_set_timer(client_data: dict, seconds: int):
        print(f'{client_data["name"]} set a timer for {seconds} seconds!')
        __import__("time").sleep(seconds)
        print(f'{client_data["name"]}\'s timer is done!')
        server.send_client_raw(client_data["ip"], "timer_done")

    @server.on("commit_genocide")
    def on_commit_genocide():
        print("It's time to genocide the connected clients.")
        server.send_all_clients("genocide", None)

    while True:
        server.run()
