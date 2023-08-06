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

import json  # Handle sending dictionaries
import select  # Handle multiple clients at once
import socket
import threading  # Threaded server and decorators
from ipaddress import IPv4Address  # Comparisons
from typing import Callable, Iterable, Optional, Union  # Type hints

try:
    from . import _typecast
    from ._shared import _HiSockBase
    from .utils import (ClientException, ClientInfo, ClientNotFound,
                        GroupNotFound, Sendable, ServerException,
                        _removeprefix, ipstr_to_tup, make_header,
                        receive_message, validate_ipv4)
except ImportError:
    import _typecast
    from _shared import _HiSockBase
    from utils import (ClientException, ClientInfo, ClientNotFound,
                       GroupNotFound, Sendable, ServerException, _removeprefix,
                       ipstr_to_tup, make_header, receive_message,
                       validate_ipv4)


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
        Default is False FOR NOW. Investigating further.
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
        keepalive: bool = False,  # DISABLE KEEPALIVE FOR NOW
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

        # Dictionaries and lists for client lookup
        self._sockets_list = [self.socket]  # Our socket will always be the first
        self.clients: dict[socket.socket, ClientInfo] = {}
        self.clients_rev: dict[ClientInfo, socket.socket] = {}
        
        self._reserved_funcs = {"join": 1, "leave": 1, "message": 3, "name_change": 3, "group_change": 3, "*": 3}
        self._unreserved_func_arguments = ("client", "message")

        # Keepalive
        self._keepalive_event = threading.Event()
        self._unresponsive_clients = []
        self._keepalive = keepalive

        if self._keepalive:
            keepalive_thread = threading.Thread(target=self._keepalive_thread, daemon=True)
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

    def _new_client_connection(self, connection: socket.socket, address: tuple[str, int]):
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
        client_hello = receive_message(connection, self.header_len, self.RECV_BUFFERSIZE)
        if not client_hello:
            raise ClientException("Client disconnected or had an error.")
        client_hello = _removeprefix(client_hello["data"], b"$CLTHELLO$")
        try:
            client_hello = json.loads(client_hello)
        except json.JSONDecodeError:
            raise ClientException("Client sent an invalid hello.") from None

        client_info = ClientInfo(address, client_hello["name"], client_hello["group"])
        self.clients[connection] = client_info
        self.clients_rev[client_info] = connection

        # Send reserved command to existing clients
        self._send_all_clients_raw(f"$CLTCONN${json.dumps(client_info.as_dict())}".encode())

        self._call_function_reserved("join", client_info)

    def _client_disconnection(self, client_socket: socket.socket):
        """
        Handle a client disconnection.

        :raises ClientNotFound: The client wasn't connected to the server.
        """

        client_info = self.clients[client_socket]

        if client_socket not in self._sockets_list:
            raise ClientNotFound(f'Client "{client_socket}" is not connected.')

        try:
            client_socket.close()
        except OSError:
            # Already closed
            pass
        self._sockets_list.remove(client_socket)
        del self.clients[client_socket]
        del self.clients_rev[client_info]
        # Note: ``self._unresponsive_clients`` should be handled by the keepalive

        # Send the client disconnection event to the clients
        self._send_all_clients_raw(f"$CLTDISCONN${json.dumps(client_info.as_dict())}".encode())

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
                for client_socket in self.clients:
                    if client_socket not in self.clients:
                        continue

                    self._unresponsive_clients.append(client_socket)
                    client_socket.sendall(b"$KEEPALIVE$")

            # Keepalive acknowledgments will be handled in `_handle_keepalive`
            self._keepalive_event.wait(30)

            # Keepalive response wait is over, remove the unresponsive clients
            if not self._keepalive_event.is_set():
                for client_socket in self._unresponsive_clients:
                    try:
                        self.disconnect_client(
                            self.clients[client_socket],
                            force=True,
                            call_func=True,
                        )
                    except KeyError:  # Client already left
                        pass
                self._unresponsive_clients.clear()

    # On decorator

    def on(self, command: str, threaded: bool = False, override: bool = False) -> Callable:
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

        .. versionchanged:: 3.0
            Manual type casting has been removed in favor of automatic type casting. This means that
            annotations now do not matter in the context of how data will be manipulated, and that 
            supported datatypes should automatically be casted to and from bytes.

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

    def _get_clientinfo(self, client: Union[tuple[str, int], str, ClientInfo]):
        if isinstance(client, ClientInfo):
            return client

        for client_info in self.clients_rev:
            if isinstance(client, tuple) and client_info.ip == client:
                return client_info
            elif isinstance(client, str) and client_info.name == client:
                return client_info

        return None

    def _get_client_socket(self, client: Union[tuple[str, int], str, ClientInfo]) -> Optional[socket.socket]:
        """
        Gets a client socket from a name or tuple in the form of (ip, port).

        :param client: The name or tuple of the client.
        :type client: ClientInfo

        :return: The socket of the client.
        :rtype: socket.socket

        :raises UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        client = self._get_clientinfo(client)
        if client is not None:
            return self.clients_rev[client]
        return None

    def _get_group_sockets(self, group: str) -> Iterable[socket.socket]:
        """
        An iterable that returns all client sockets in a group

        :param group: The group to get the sockets from.
        :type group: str

        :return: An iterable of client sockets in the group.
        :rtype: Iterable[socket.socket]

        .. note::
           If the group does not exist, an empty iterable is returned.
        """

        return map(
            lambda client: self.clients_rev[client], filter(lambda client: client.group == group, self.clients_rev)
        )

    def get_group(self, group: Union[ClientInfo, str]) -> list[ClientInfo]:
        """
        Gets all clients from a specific group.

        :param group: Either a ClientInfo representing a client in a group, or a string, representing the group to look up
        :type group: Union[ClientInfo, str]

        :raises GroupNotFound: Group does not exist

        :return: A list of ClientInfo
        :rtype: list[ClientInfo]
        """

        if isinstance(group, ClientInfo):
            group = group.group

        group_clients = []  # Will be a list of dicts

        for client_socket in self._get_group_sockets(group):
            group_clients.append(self.clients[client_socket])

        if len(group_clients) == 0:
            raise GroupNotFound(f'Group "{group}" does not exist.')
        return group_clients

    def get_all_clients(self, key: Optional[str] = None) -> list[Union[ClientInfo, tuple[str, int], str]]:
        """
        Get all clients currently connected to the server.

        :param key: If a string is specified as a key,
            it will search through the ClientInfo for the key, and output it to a list
        :type key: Union[Callable, str], optional

        :return: A list of either ClientInfo or the content as filtered by the key
        :rtype: list[Union[ClientInfo, tuple[str, int], str]]
        """

        clients = list(self.clients.values())
        if key is None:
            return clients

        filter_clients = []
        if key in ["ip", "name", "group"]:
            for filter_client in clients:
                filter_clients.append(filter_client.as_dict()[key])
        return filter_clients

    def get_client(self, client: Union[str, tuple[str, int]]) -> ClientInfo:
        """
        Gets the client data for a client from a name or tuple in the form of (ip, port).

        :return: The client info.
        :rtype: ClientInfo

        :raises ClientNotFound: Client does not exist.
        :raises UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        client_socket = self._get_client_socket(client)
        if client_socket is None:
            raise ClientNotFound(f"Client {client} does not exist.")

        return self.clients[client_socket]

    def get_addr(self) -> tuple[str, int]:
        """
        Gets the address of where the HiSock server is serving at.

        :return: A tuple of the address in the form of (ip, port)
        :rtype: tuple[str, int]
        """

        return self.addr

    # Transmit data

    def _send_all_clients_raw(self, content: bytes):
        """
        Sends the command and content to *ALL* clients connected *without a command*.

        :param content: The message / content to send
        :type content: Sendable
        """

        content_header = make_header(content, self.header_len)
        for client in self.clients:
            client.sendall(content_header + content)

    def send_all_clients(self, command: str, content: Optional[Sendable] = None):
        """
        Sends the command and content to *ALL* clients connected.

        :param command: A string, representing the command to send to every client.
        :type command: str
        :param content: The message / content to send
        :type content: Sendable, optional
        """

        data = self._prepare_send(command, content)
        for client in self.clients:
            client.sendall(data)

    def send_group(self, group: Union[ClientInfo, str], command: str, content: Optional[Sendable] = None):
        """
        Sends data to a specific group.
        Groups are recommended for more complicated servers or multipurpose
        servers, as it allows clients to be divided, which allows clients to
        be sent different data for different purposes.

        :param group: Either a ClientInfo representing a client in a group, or a string representing the group to send data to.
        :type group: str
        :param command: A string, containing the command to send
        :type command: str
        :param content: A bytes-like object, with the content/message to send
        :type content: Union[bytes, dict]

        :raises TypeError: If the group does not exist, or the client
            is not in a group (``ClientInfo``).
        """

        if isinstance(group, ClientInfo):
            group = group.group

        data = self._prepare_send(command, content)
        for client in self._get_group_sockets(group):
            client.sendall(data)

    def send_client(
        self, client: Union[str, tuple[str, int], ClientInfo], command: str, content: Optional[Sendable] = None
    ):
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

        data = self._prepare_send(command, content)
        self._get_client_socket(client).sendall(data)

    # Disconnect

    def disconnect_client(
        self, client: Union[tuple[str, int], str, ClientInfo], force: bool = False, call_func: bool = False
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

        client_socket = self._get_client_socket(client)
        if client_socket is None:
            raise ClientNotFound(f"Client {client} does not exist.")

        client_info = self.clients[client_socket]

        if not force:
            try:
                client_socket.sendall(b"$DISCONN$")
            except BrokenPipeError:
                # Client is already gone
                pass
        self._client_disconnection(client_socket)

        if call_func and "leave" in self.funcs:
            self._call_function_reserved("leave", client_info)

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

        read_socket, write_socket, exception_socket = select.select(self._sockets_list, [], self._sockets_list)

        client_socket: socket.socket
        for client_socket in read_socket:
            try:
                ### Reserved commands ###

                # Handle bad client
                if client_socket.fileno() == -1:
                    # Client already disconnected
                    # This can happen in the case of a keepalive that wasn't responded to
                    # or the client already disconnected and it was already handled
                    if client_socket not in self.clients:
                        continue

                    self.disconnect_client(self.clients[client_socket], force=True, call_func=False)
                    continue

                # Handle new connection
                # select.select() returns the server socket if a new connection is made
                if client_socket == self.socket:
                    self._new_client_connection(*self.socket.accept())
                    continue

                ### Receiving data ###
                data: bytes = b""

                # {"header": bytes, "data": bytes} or False
                self._receiving_data = True
                raw_data = receive_message(client_socket, self.header_len, self.RECV_BUFFERSIZE)
                self._receiving_data = False

                if isinstance(raw_data, dict):
                    data = raw_data["data"]

                try:
                    client_info = self.clients[client_socket]
                except KeyError:
                    raise ClientNotFound("Client data not found, but is not a new client.") from KeyError

                ### Reserved commands ###

                # Handle client disconnection
                if not raw_data or data.startswith(  # Most likely client disconnect, could be client error
                    b"$USRCLOSE$"
                ):

                    try:
                        self.disconnect_client(client_info, force=False, call_func=True)
                    except BrokenPipeError:  # UNIX
                        # Client is already gone
                        pass
                    except ConnectionResetError:
                        self.disconnect_client(client_info, force=True, call_func=True)

                    continue

                # Change name or group
                for matching_reserve, key in zip((b"$CHNAME$", b"$CHGROUP$"), ("name", "group")):

                    if not data.startswith(matching_reserve):
                        continue

                    change_to = _removeprefix(data, matching_reserve).decode()
                    client_info_dict = client_info.as_dict()

                    # Resetting
                    if change_to == "":
                        change_to = client_info_dict[key]

                    # Change it
                    new_client_info_dict = client_info.as_dict()
                    new_client_info_dict[key] = change_to

                    new_client_info = ClientInfo.from_dict(new_client_info_dict)
                    self.clients[client_socket] = new_client_info

                    del self.clients_rev[client_info]
                    self.clients_rev[new_client_info] = client_socket

                    # Call reserved function
                    reserved_func_name = f"{key}_change"
                    old_value = client_info_dict[key]
                    new_value = new_client_info_dict[key]

                    self._call_function(
                        reserved_func_name,
                        new_client_info,
                        old_value,
                        new_value,
                    )

                    return

                # Handle keepalive acknowledgement
                if data.startswith(b"$KEEPACK$"):
                    self._handle_keepalive(client_socket)
                    continue

                # Get client
                elif data.startswith(b"$GETCLT$"):
                    try:
                        client_identifier = _removeprefix(data, b"$GETCLT$").decode()

                        # Determine if the client identifier is a name or an IP+port
                        try:
                            validate_ipv4(client_identifier)
                            client_identifier = ipstr_to_tup(client_identifier)
                        except ValueError:
                            pass

                        client = self.get_client(client_identifier).as_dict()
                    except ValueError as e:
                        client = {"traceback": str(e)}
                    except ClientNotFound:
                        client = {"traceback": "$NOEXIST$"}

                    self.clients_rev[client_info].sendall(json.dumps(client).encode())
                    continue

                ### Unreserved commands ###
                has_listener = False  # For cache

                # Get command and message
                command = data.lstrip(b"$CMD$").split(b"$MSG$")[0].decode()
                content = _removeprefix(data, f"$CMD${command}$MSG$".encode())
                unfmt_content = content

                fmt = ""
                # No content? (`_removeprefix` didn't do anything)
                if not content or content == data:
                    content = None
                else:
                    fmt_len = int(content[:8])
                    fmt = content[8 : 8 + fmt_len].decode()
                    content = content[8 + fmt_len :]

                fmt_ast = _typecast.read_fmt(fmt)
                typecasted_content = _typecast.typecast_data(fmt_ast, content)

                # Call functions that are listening for this command from the `on`
                # decorator
                for matching_command, func in self.funcs.items():
                    if command != matching_command:
                        continue

                    has_listener = True

                    # Call function with dynamic args
                    arguments = ()
                    # client_info
                    if func["num_args"] == 1:
                        arguments = (client_info,)
                    # client_info, message
                    elif func["num_args"] >= 2:
                        arguments = (client_info, typecasted_content)
                    self._call_function(matching_command, *arguments)
                    break

                else:
                    has_listener = self._handle_recv_commands(command, unfmt_content)

                # No listener found
                if not has_listener and "*" in self.funcs:
                    # No recv and no catchall. A command and some data.
                    self._call_wildcard_function(client_info=client_info, command=command, content=typecasted_content)

                # Caching
                self._cache(has_listener, command, content, data, raw_data["header"])

                # Call `message` function
                if "message" in self.funcs:
                    self._call_function_reserved("message", client_info, command, typecasted_content)
            except (BrokenPipeError, ConnectionResetError):
                if client_socket in self.clients:
                    # Does it need to be forced?? Investigate further
                    self.disconnect_client(self.clients[client_socket]["ip"], force=True)
                print("[DEBUG] 10054 exception, we're investigating")

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
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            # Bad file descriptor
            ...
        self.socket.close()

    # Main loop

    def start(self, callback: Callable = None, error_handler: Callable = None):
        """
        Start the main loop for the server.

        :param callback: A function that will be called every time the
            client receives and handles a message.
        :type callback: Callable, optional
        :param error_handler: A function that will be called every time the
            client encounters an error.
        :type error_handler: Callable, optional
        """

        try:
            while not self.closed:
                self._run()
                if isinstance(callback, Callable):
                    callback()
        except Exception as e:
            if isinstance(error_handler, Callable):
                error_handler(e)
            else:
                raise e
        finally:
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
        self._thread: threading.Thread = None
        self._stop_event = threading.Event()

    def close(self):
        """
        Closes the server. Blocks the thread until the server is closed.
        For documentation, see :meth:`HiSockServer.close`.
        """

        super().close()
        self._stop_event.set()
        try:
            self._thread.join()
        except RuntimeError:
            # Cannot join current thread
            return

    def start(self, callback: Callable = None, error_handler: Callable = None):
        """
        Starts the main server loop.
        For documentation, see :meth:`HiSockServer.start`.
        """

        self._thread = threading.Thread(target=self._start, args=(callback, error_handler))
        self._thread.start()

    def _start(self, callback: Callable = None, error_handler: Callable = None):
        """Start the main loop for the threaded server."""

        def updated_callback():
            if self._stop_event.is_set() and not self.closed:
                self.close()

            # Original callback
            if isinstance(callback, Callable):
                callback()

        super().start(callback=updated_callback, error_handler=error_handler)


def start_server(addr, max_connections=0, header_len=16):
    """
    Creates a :class:`HiSockServer` instance. See :class:`HiSockServer` for
    more details and documentation.

    :return: A :class:`HiSockServer` instance.
    """

    return HiSockServer(addr=addr, max_connections=max_connections, header_len=header_len)


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
    def on_join(client: ClientInfo):
        print(
            f"{client.name} has joined! "
            f'Their IP is {":".join(map(str, client.ip))}. '
            f"Their group is {client.group}."
        )

    @server.on("leave")
    def on_leave(client: ClientInfo):
        print(f"{client.name} has left!")
        server.send_all_clients("client_disconnect", {"name": client.name, "reason": "they left"})

    @server.on("message")
    def on_message(client: ClientInfo, command: str, message: str):
        print(f"[MESSAGE CATCH-ALL] {client.name} sent a command, {command} " f'with the message "{message}".')

    @server.on("name_change")
    def on_name_change(_, old_name: str, new_name: str):  # Client data isn't used
        print(f"{old_name} changed their name to {new_name}.")

    @server.on("group_change")
    def on_group_change(client: ClientInfo, old_group: str, new_group: str):
        print(f"{client.name} changed their group to {new_group}.")
        # Alert clients of change
        server.send_group(
            old_group,
            "message",
            f"{client.name} has left to move to {new_group}.",
        )
        server.send_group(
            new_group,
            "message",
            f"{client.name} has joined from {old_group}.",
        )

    @server.on("ping")
    def on_ping(client: ClientInfo):
        print(f"{client.name} pinged!")
        server.send_client(client, "pong")

    @server.on("get_all_clients")
    def on_all_clients(client: ClientInfo):
        print(f"{client.name} asked for all clients!")
        server.send_client(client, "all_clients", server.get_all_clients())

    @server.on("broadcast_message")
    def on_broadcast_message(client: ClientInfo, message: str):
        print(f'{client.name} said "{message}"!')
        server.send_all_clients("message", message)

    @server.on("broadcast_message_to_group")
    def on_broadcast_message_to_group(client: ClientInfo, message: str):
        print(f'{client.name} said "{message}" to their group, {client.group}!')
        server.send_group(client, "message", message)

    @server.on("set_timer", threaded=True)
    def on_set_timer(client: ClientInfo, seconds: int):
        print(f"{client.name} set a timer for {seconds} seconds!")
        __import__("time").sleep(seconds)
        print(f"{client.name}'s timer is done!")
        server.send_client(client, "timer_done")

    @server.on("commit_genocide")
    def on_commit_genocide():
        print("It's time to genocide the connected clients.")
        server.send_all_clients("genocide")

    @server.on("*")
    def on_wildcard(client: ClientInfo, command: str, data: bytes):
        print(f"There was some unhandled data from {client.name}. " f"{command=}, {data=}")

        server.send_client(client, "uncaught_command", data.replace("a", "ඞ"))

    server.start()
