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
        FunctionNotFoundWarning,
        ClientNotFound,
        GroupNotFound,
        ClientInfo,
        Sendable,
        Client,
        _removeprefix,
        _dict_tupkey_lookup,
        _type_cast,
        receive_message,
        make_header,
        validate_ipv4,
        ipstr_to_tup,
    )
    from ._shared import _HiSockBase
except ImportError:
    # Relative import doesn't work for non-pip builds
    from utils import (
        ServerException,
        ClientException,
        FunctionNotFoundWarning,
        ClientNotFound,
        GroupNotFound,
        ClientInfo,
        Sendable,
        Client,
        _removeprefix,
        _dict_tupkey_lookup,
        _type_cast,
        receive_message,
        make_header,
        validate_ipv4,
        ipstr_to_tup,
    )
    from _shared import _HiSockBase


# ░█████╗░░█████╗░██╗░░░██╗████████╗██╗░█████╗░███╗░░██╗██╗
# ██╔══██╗██╔══██╗██║░░░██║╚══██╔══╝██║██╔══██╗████╗░██║██║
# ██║░░╚═╝███████║██║░░░██║░░░██║░░░██║██║░░██║██╔██╗██║██║
# ██║░░██╗██╔══██║██║░░░██║░░░██║░░░██║██║░░██║██║╚████║╚═╝
# ╚█████╔╝██║░░██║╚██████╔╝░░░██║░░░██║╚█████╔╝██║░╚███║██╗
# ░╚════╝░╚═╝░░╚═╝░╚═════╝░░░░╚═╝░░░╚═╝░╚════╝░╚═╝░░╚══╝╚═╝
#   Change this code only if you know what you are doing!
# If this code is changed, the server may not work properly


class HiSockServer(_HiSockBase):
    """
    The server class for :mod:`HiSock`.

    :param addr: A two-element tuple, containing the IP address and the
        port number of where the server should be hosted.
        Due to the nature of reserved ports, it is recommended to host the
        server with a port number that's greater than or equal to 1024.
        **Only IPv4 is currently supported.**
    :type addr: tuple
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
    :param cache_size: The size of the message cache.
        -1 or below for no message cache, 0 for an unlimited cache size,
        and any other number for the cache size.
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
        max_connections: int = 0,
        header_len: int = 16,
        cache_size: int = -1,
        keepalive: bool = True,
    ):
        super().__init__(addr=addr, header_len=header_len, cache_size=cache_size)

        # Socket initialization
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(True)
        try:
            self.socket.bind(addr)
        except socket.gaierror as e:  # getaddrinfo error
            raise TypeError("The IP address and/or port are invalid.") from e
        self.socket.listen(max_connections)

        # Stores the names of the reserved functions and information about them
        # Used for the `on` decorator
        self._reserved_funcs = {
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
            "*": {
                "number_arguments": 3,
                "type_cast_arguments": ("client_data", "command", "message"),
            },
        }
        self._unreserved_func_arguments = ("client_data", "message")

        # Dictionaries and lists for client lookup
        self._sockets_list = [self.socket]  # Our socket will always be the first
        # socket: {"ip": (ip, port), "name": str, "group": str}
        self.clients: dict[socket.socket, dict] = {}
        # ((ip: str, port: int), name: str, group: str): socket
        self.clients_rev: dict[tuple, socket.socket] = {}

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

        self._call_function_reserved(
            "join",
            self._type_cast_client_data(command="join", client_data=client_data),
        )

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
                    try:
                        self.disconnect_client(
                            self.clients[client_socket]["ip"],
                            force=True,
                            call_func=True,
                        )
                    except KeyError:  # Client already left
                        pass
                self._unresponsive_clients.clear()

    # On decorator

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
            If you want to get them from ``clients_rev`` directly, use
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
        This is recommended over the class attribute ``self._clients`` or
        ``self.clients_rev``, as it is in a dictionary-like format.

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
        :param content: A bytes-like object, with the content/message to send
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

        if call_func and "leave" in self.funcs:
            self._call_function_reserved(
                "leave",
                self._type_cast_client_data(command="leave", client_data=client_data),
            )

    def disconnect_all_clients(self, force=False):
        """Disconnect all clients."""

        if not force:
            self._send_all_clients_raw(b"$DISCONN$")
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
                # Client already disconnected
                # This can happen in the case of a keepalive that wasn't responded to
                # or the client already disconnected and it was already handled
                if client_socket not in self.clients:
                    continue

                self.disconnect_client(
                    self.clients[client_socket]["ip"], force=True, call_func=False
                )
                continue

            # Handle new connection
            # select.select() returns the server socket if a new connection is made
            if client_socket == self.socket:
                self._new_client_connection(*self.socket.accept())
                continue

            ### Receiving data ###
            data: bytes = b""
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
                except ConnectionResetError:
                    self.disconnect_client(
                        client_data["ip"], force=True, call_func=True
                    )

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

                if reserved_func_name in self._reserved_funcs:
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

                return

            # Handle keepalive acknowledgement
            if decoded_data.startswith("$KEEPACK$"):
                self._handle_keepalive(client_socket)
                continue

            # Get client
            elif decoded_data.startswith("$GETCLT$"):
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

            ### Unreserved commands ###

            # Handle random data with no command
            elif not decoded_data.startswith("$CMD$"):
                if "*" in self.funcs:
                    self._call_wildcard_function(
                        client_data=client_data, command=None, content=data
                    )
                return

            has_listener = False  # For cache

            # Get command and message
            command = decoded_data.lstrip("$CMD$").split("$MSG$")[0]
            content = _removeprefix(decoded_data, f"$CMD${command}$MSG$")

            # No content? (`_removeprefix` didn't do anything)
            if not content or content == decoded_data:
                content = None

            # Call functions that are listening for this command from the `on`
            # decorator
            for matching_command, func in self.funcs.items():
                if command != matching_command:
                    continue

                has_listener = True

                # Call function with dynamic args
                arguments = ()
                if len(func["type_hint"]) != 0:
                    type_casted_client_data = self._type_cast_client_data(
                        command=matching_command, client_data=client_data
                    )
                # client_data
                if len(func["type_hint"]) == 1:
                    arguments = (type_casted_client_data,)
                # client_data, message
                elif len(func["type_hint"]) >= 2:
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

            else:
                has_listener = self._handle_recv_commands(command, content)

            # No listener found
            if not has_listener and "*" in self.funcs:
                # No recv and no catchall. A command and some data.
                self._call_wildcard_function(
                    client_data=client_data, command=command, content=content
                )

            # Caching
            self._cache(
                has_listener, command, content, decoded_data, raw_data["header"]
            )

            # Call `message` function
            if "message" in self.funcs:
                self._call_function_reserved(
                    "message",
                    self._type_cast_client_data(
                        command="message", client_data=client_data
                    ),
                    _type_cast(
                        type_cast=self.funcs["message"]["type_hint"]["command"],
                        content_to_type_cast=command,
                        func_name="<message call in run command>",
                    ),
                    _type_cast(
                        type_cast=self.funcs["message"]["type_hint"]["message"],
                        content_to_type_cast=content,
                        func_name="<message call in run message>",
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

        try:
            while not self.closed:
                self._run()
        finally:
            self.disconnect_all_clients(force=True)
            self.close()


class ThreadedHiSockServer(HiSockServer):
    """
    :class:`HiSockClient`, but running in its own thread as to not block the
    main loop. Please note that while this is running in its own thread, the
    event handlers will still be running in the main thread. To avoid this,
    use the ``threaded=True`` argument for the ``on`` decorator.

    For documentation purposes, see :class:`HiSockClient`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._thread = threading.Thread(target=super().start)
        self._stop_event = threading.Event()

    def close(self):
        """
        Closes the server. Blocks the thread until the server is closed.
        For documentation, see :meth:`HiSockServer.close`.
        """

        super().close()
        self._stop_event.set()
        self.join()

    def start(self):
        """
        Starts the main server loop.
        For documentation, see :meth:`HiSockServer.start`.
        """

        self._thread.start()

    def join(self):
        """
        Waits for the thread to be killed.
        XXX: Should this be removed?
        """

        self._thread.join()


def start_server(addr, max_connections=0, header_len=16):
    """
    Creates a :class:`HiSockServer` instance. See :class:`HiSockServer` for
    more details and documentation.

    :return: A :class:`HiSockServer` instance.
    """

    return HiSockServer(
        addr=addr, max_connections=max_connections, header_len=header_len
    )


def start_threaded_server(*args, **kwargs):
    """
    Creates a :class:`ThreadedHiSockServer` instance. See :class:`ThreadedHiSockServer`
    for more details. For documentation, see :func:`start_server`.

    :return: A :class:`ThreadedHiSockServer` instance
    """

    return ThreadedHiSockServer(*args, **kwargs)


if __name__ == "__main__":
    print("Testing server!")
    server = start_server(("127.0.0.1", int(input("Port: "))))

    @server.on("join")
    def on_join(client_data):
        print(
            f"{client_data.name} has joined! "
            f'Their IP is {":".join(map(str, client_data.ip))}. '
            f'Their group is {client_data["group"]}.'
        )

    @server.on("leave")
    def on_leave(client_data):
        print(f"{client_data.name} has left!")
        server.send_all_clients(
            "client_disconnect", {"name": client_data.name, "reason": "they left"}
        )

    @server.on("message")
    def on_message(client_data, command: str, message: str):
        print(
            f"[MESSAGE CATCH-ALL] {client_data.name} sent a command, {command} "
            f'with the message "{message}".'
        )

    @server.on("name_change")
    def on_name_change(_, old_name: str, new_name: str):  # Client data isn't used
        print(f"{old_name} changed their name to {new_name}.")

    @server.on("group_change")
    def on_group_change(client_data, old_group: str, new_group: str):
        print(f"{client_data.name} changed their group to {new_group}.")
        # Alert clients of change
        server.send_group(
            old_group,
            "message",
            f"{client_data.name} has left to move to {new_group}.",
        )
        server.send_group(
            new_group,
            "message",
            f"{client_data.name} has joined from {old_group}.",
        )

    @server.on("ping")
    def on_ping(client_data):
        print(f"{client_data.name} pinged!")
        server.send_client(client_data.ip, "pong")

    @server.on("get_all_clients")
    def on_all_clients(client_data):
        print(f"{client_data.name} asked for all clients!")
        server.send_client(client_data.ip, "all_clients", server.get_all_clients())

    @server.on("broadcast_message")
    def on_broadcast_message(client_data, message: str):
        print(f'{client_data.name} said "{message}"!')
        server.send_all_clients("message", message)

    @server.on("broadcast_message_to_group")
    def on_broadcast_message_to_group(client_data, message: str):
        print(
            f'{client_data.name} said "{message}" to their group, {client_data.group}!'
        )
        server.send_group(client_data, "message", message)

    @server.on("set_timer", threaded=True)
    def on_set_timer(client_data, seconds: int):
        print(f"{client_data.name} set a timer for {seconds} seconds!")
        __import__("time").sleep(seconds)
        print(f"{client_data.name}'s timer is done!")
        server.send_client(client_data.ip, "timer_done")

    @server.on("commit_genocide")
    def on_commit_genocide():
        print("It's time to genocide the connected clients.")
        server.send_all_clients("genocide")

    @server.on("*")
    def on_wildcard(client_data, command: str, data: str):
        print(
            f"There was some unhandled data from {client_data.name}. "
            f"{command=}, {data=}"
        )

        server.send_client(client_data, "uncaught_command", data.replace("a", "ඞ"))

    server.start()
