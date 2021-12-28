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
import re  # Make sure arguments are passed correctly
import threading  # Threaded server and decorators
import warnings  # Non-severe errors
from typing import Callable, Union, optional, Any  # Type hints
from ipaddress import IPv4Address  # Comparisons
from hisock import constants

try:
    # Pip builds require relative import
    from .utils import (
        NoHeaderWarning,
        NoMessageException,
        InvalidTypeCast,
        receive_message,
        _removeprefix,
        make_header,
        _dict_tupkey_lookup,
        _dict_tupkey_lookup_key,
        _type_cast,
        validate_ipv4,
        MessageCacheMember,
    )
except ImportError:
    # Relative import doesn't work for non-pip builds
    from utils import (
        NoHeaderWarning,
        NoMessageException,
        InvalidTypeCast,
        receive_message,
        _removeprefix,
        make_header,
        _dict_tupkey_lookup,
        _dict_tupkey_lookup_key,
        _type_cast,
        validate_ipv4,
        MessageCacheMember,
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

    :ivar tuple addr: A two-element tuple containing the IP address and the port.
    :ivar int header_len: An integer storing the header length of each "message".
    :ivar dict clients: A dictionary with the socket as its key and the
        client info as its value.
    :ivar dict clients_rev: A dictionary with the client info as its key
        and the socket as its value (for reverse lookup, up-to-date with
        :attr:`clients`).
    :ivar dict funcs: A list of functions registered with decorator :meth:`on`.
        **This is mainly used for under-the-hood-code.**
    """

    def __init__(
        self,
        addr: tuple[str, int],
        blocking: bool = True,
        max_connections: int = 0,
        header_len: int = 16,
        cache_size: int = -1,
        tls: optional[Union[dict, str]] = None,
    ):
        self.addr = addr
        self.header_len = header_len

        # Socket initialization
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(blocking)
        try:
            self.sock.bind(addr)
        except socket.gaierror:  # getaddrinfo error
            raise TypeError("The IP address and/or port are invalid!")
        self.sock.listen(max_connections)

        # Function related storage
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
            2,  # join
            2,  # leave
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
        self.clients = {}  # socket: {"addr": (ip, port), "name": str, "group": str}
        self.clients_rev = {}  # ((ip, port), name, group): socket

        # Flags
        self.called_run = False
        self._closed = False

        # TLS
        if tls is None:
            self.tls_arguments = {"tls": False}  # If TLS is false, then no TLS
            return
        if isinstance(tls, dict):
            self.tls_arguments = tls
            return
        if isinstance(tls, str) and tls == "default":
            self.tls_arguments = {
                "rsa_authentication_dir": ".pubkeys",
                "suite": "default",
                "diffie_hellman": constants.DH_DEFAULT,
            }

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
            raise TypeError("Type not supported for > comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) > IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    def __ge__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) >= "192.168.1.133:5000" """

        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for >= comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) >= IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) >= IPv4Address(ip[0])

    def __lt__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) < "192.168.1.133:5000" """

        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for < comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) < IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) < IPv4Address(ip[0])

    def __le__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) <= "192.168.1.133:5000" """

        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for <= comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) <= IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) <= IPv4Address(ip[0])

    def __eq__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) == "192.168.1.133:5000" """

        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for == comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) == IPv4Address(other.addr[0])
        ip = other.split(":")
        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    # Internal methods
    def _update_clients_rev_dict(self, idx: optional[int] = None):
        """
        Updates the reversed clients dictionary to the normal dictionary

        :param idx: Index of the client to update if known. If not known,
            the whole dictionary will be updated.
        :raises IndexError: If the client idx doesn't exist.
        :raises TypeError: If the client idx is not an integer.
        :raises KeyError: If the client doesn't exist in :ivar:`self.clients`
        :raises KeyError: If the client isn't a valid client.
        """

        if idx is not None:
            clients = (self.clients[self._sockets_list[idx]],)
        else:
            clients = self.clients

        for client in clients:
            self.clients_rev[
                (client["address"], client["name"], client["group"])
            ] = client

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

        :raises TypeError: If the function is not found.
        """

        # Check if the function exists
        if func_name not in self.funcs:
            raise TypeError(f"Function {func_name} not found")

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
            self, outer: HiSockServer, cmd_activation: str, threaded: bool = False
        ):
            self.outer = outer
            self.cmd_activation = cmd_activation
            self.threaded = threaded

        def __call__(self, func: Callable) -> Callable:
            """
            Adds a function that gets called when the server receives a matching command.

            :raises TypeError: If the number of function arguments is invalid.
            """

            func_args = inspect.getfullargspec(func).args
            self._assert_num_func_args_valid(len(func_args))

            # Store annotations of function
            annotations = inspect.getfullargspec(func).annotations  # {"param": type}
            parameter_annotations = {"clt_data": None, "msg": None}

            # Process unreserved commands and reserved `message` (only reserved
            # command to have 2 arguments)
            if (
                self.cmd_activation not in self.outer._reserved_functions
                or self.cmd_activation == "message"
            ):
                # Map function arguments into type hint compliant ones
                for func_argument, argument_name in zip(func_args, ("clt_data", "msg")):
                    if func_argument not in annotations:
                        continue
                    parameter_annotations[argument_name] = annotations[func_argument]

            # Creates function dictionary to add to `outer.funcs`
            self.outer.funcs[self.cmd_activation] = {
                "func": func,
                "name": func.__name__,
                "type_hint": parameter_annotations,
            }

            # Decorator stuff
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

    def on(self, command: str, threaded: bool = False) -> Callable:
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
            in order to not block the run() loop.
            Default is False.
        :return: The same function (the decorator just appended the function to a stack).
        :rtype: function
        """

        # Passes in outer to _on decorator/class
        return self._on(self, command, threaded)

    # Getters

    def _get_client_from_name_or_ip_port(
        self, client: Union[str, tuple]
    ) -> socket.socket:
        """
        Gets a client socket from a name or tuple in the form of (ip, port).

        :raise ValueError: Client format is wrong
        :raise TypeError: Client does not exist
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected

        .. warning::
            This is the same as :meth:`get_client`... should this be removed?
            IDK because the other naming style for getting clients is like this...
        """

        ret_client_socket = None

        # Search by IPv4
        if isinstance(client, tuple):
            try:
                validate_ipv4(client)  # Raises ValueError if invalid
                client_socket: socket.socket = next(
                    _dict_tupkey_lookup(
                        (client.split(":")[0], client.split(":")[0][1]),
                        self.clients_rev,
                        idx_to_match=0,
                    )
                )
            except StopIteration:
                raise TypeError(f"Client with IP {client} is not connected")

            ret_client_socket = client_socket

        # Search by name
        elif isinstance(client, str):
            try:
                # Modify dictionary so only names and IPs are included
                mod_clients_rev = {}
                for key, value in self.clients_rev.items():
                    mod_key = (key[0], key[1])
                    mod_clients_rev[mod_key] = value

                client_socket: socket.socket = list(
                    _dict_tupkey_lookup(client, mod_clients_rev, idx_to_match=1)
                )
            except StopIteration:
                raise TypeError(f'Client with name "{client}" doesn\'t exist')

            if len(client_socket) > 1:
                warnings.warn(
                    f'{len(client_socket)} clients with name "{client}" detected; sending data to '
                    f"Client with IP {':'.join(map(str, client_socket[0].getpeername()))}"
                )
                ret_client_socket = client_socket[0]

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

        return _dict_tupkey_lookup_key(group, self.clients_rev, idx_to_match=2)

    def get_group(self, group: str) -> list[dict[str, Union[str, socket.socket]]]:
        """
        Gets all clients from a specific group

        :param group: A string, representing the group to look up
        :type group: str
        :raise TypeError: Group does not exist

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
            raise TypeError(f"Group {group} does not exist")


        return mod_group_clients

    def get_all_clients(
        self, key: optional[Union[Callable, str]] = None
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
        Gets a client socket from a name or tuple in the form of (ip, port).

        :return: The client socket
        :rtype: socket.socket

        :raise ValueError: Client format is wrong
        :raise TypeError: Client does not exist
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected
        """

        return self._get_client_from_name_or_ip_port(client)

    def get_addr(self) -> tuple[str, int]:
        """
        Gets the address of where the hisock server is serving at.

        :return: A tuple of the address in the form of (ip, port)
        :rtype: tuple[str, int]
        """

        return self.addr

    # Send

    def send_all_clients(self, command: str, content: bytes):
        """
        Sends the command and content to *ALL* clients connected.

        :param command: A string, representing the command to send to every client.
        :type command: str
        :param content: A bytes-like object, containing the message/content to send
            to each client.
        :type content: bytes
        """

        data_to_send = command.encode() + b" " + content
        content_header = make_header(data_to_send, self.header_len)
        for client in self.clients:
            client.send(content_header + data_to_send)

    def send_group(self, group: str, command: str, content: bytes):
        """
        Sends data to a specific group.
        Groups are recommended for more complicated servers or multipurpose
        servers, as it allows clients to be divided, which allows clients to
        be sent different data for different purposes.

        :param group: A string, representing the group to send data to.
        :type group: str
        :param command: A string, containing the command to send.
        :type command: str
        :param content: A bytes-like object, with the content/message
            to send.
        :type content: bytes
        :raise TypeError: The group does not exist.
        """

        data_to_send = command.encode() + b" " + content
        content_header = make_header(data_to_send, self.header_len)
        for client in self._get_all_client_sockets_in_group(group):
            client.send(content_header + data_to_send)

    def send_client(self, client: Union[str, tuple], command: str, content: bytes):
        """
        Sends data to a specific client.

        :param client: The client to send data to. The format could be either by IP+port,
            or a client name.
        :type client: Union[str, tuple]
        :param command: A string, containing the command to send.
        :type command: str
        :param content: A bytes-like object, with the content/message
            to send.
        :type content: bytes
        :raise ValueError: Client format is wrong.
        :raise TypeError: Client does not exist.
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        data_to_send = command.encode() + b" " + content
        content_header = make_header(data_to_send, self.header_len)
        self._get_client_from_name_or_ip_port(client).send(
            content_header + data_to_send
        )

    def send_client_raw(self, client, content: bytes):
        """
        Sends data to a specific client, *without a command*
        Different formats of the client is supported. It can be:

        :param client: The client to send data to. The format could be either by IP+port,
            or a client name
        :type client: Union[str, tuple]
        :param content: A bytes-like object, with the content/message
            to send
        :type content: bytes

        :raise ValueError: Client format is wrong
        :raise TypeError: Client does not exist
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected
        """

        data_to_send = content
        content_header = make_header(data_to_send, self.header_len)
        self._get_client_from_name_or_ip_port(client).send(
            content_header + data_to_send
        )

    def send_group_raw(self, group: str, content: bytes):
        """
        Sends data to a specific group, without commands.
        Groups are recommended for more complicated servers or multipurpose
        servers, as it allows clients to be divided, which allows clients to
        be sent different data for different purposes.

        Non-command-attached content is recommended to be used alongside with
        :meth:`HiSockClient.recv_raw`.

        :param group: A string, representing the group to send data to.
        :type group: str
        :param content: A bytes-like object, with the content/message
            to send.
        :type content: bytes
        :raise TypeError: The group does not exist.
        """

        data_to_send = content
        content_header = make_header(data_to_send, self.header_len)
        for client in self._get_all_client_sockets_in_group(group):
            client.send(content_header + data_to_send)

    # Disconnect

    def disconnect_client(self, client: Union[str, tuple], force: bool = False):
        """
        Disconnects a specific client.

        :param client: The client to send data to. The format could be either by IP+port,
            or a client name.
        :type client: Union[str, tuple]
        :param command: A string, containing the command to send.
        :type command: str
        :param content: A bytes-like object, with the content/message
            to send.
        :type content: bytes
        :raise ValueError: Client format is wrong.
        :raise TypeError: Client does not exist.
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected.
        """

        client_socket = self._get_client_from_name_or_ip_port(client)

        if not force:
            disconn_header = make_header(b"$DISCONN$", self.header_len)
            client_socket.send(disconn_header)
            return

        client_socket.close()
        del self.clients[client_socket]
        self._update_clients_rev_dict()

    def disconnect_all_clients(self, force=False):
        """Disconnect all clients."""

        if not force:
            disconn_header = make_header(b"$DISCONN$", self.header_len)
            for client in self.clients:
                client.send(disconn_header + b"$DISCONN$")
            return

        (conn.close() for conn in self._sockets_list)
        self._sockets_list.clear()
        self.clients.clear()
        self.clients_rev.clear()

    def run(self):
        """
        Runs the server. This method handles the sending and receiving of data,
        so it should be run once every iteration of a while loop, as to not
        lose valuable information
        """
        # FIXME: refactor

        self.called_run = True

        if not self._closed:
            # gets all sockets from select.select
            read_sock, write_sock, exception_sock = select.select(
                self._sockets_list, [], self._sockets_list
            )

            for notified_sock in read_sock:
                # loops through all sockets
                if notified_sock == self.sock:  # Got new connection
                    connection, address = self.sock.accept()

                    # Handle client hello
                    client = receive_message(connection, self.header_len)

                    client_hello = _removeprefix(client["data"].decode(), "$CLTHELLO$ ")
                    client_hello = json.loads(client_hello)

                    # Establishes socket lists and dicts
                    self._sockets_list.append(connection)

                    clt_info = {
                        "ip": address,
                        "name": client_hello["name"],
                        "group": client_hello["group"],
                    }

                    self.clients[connection] = clt_info
                    self.clients_rev[
                        (address, client_hello["name"], client_hello["group"])
                    ] = connection

                    if "join" in self.funcs:
                        # Reserved function - Join
                        self._call_function("join", clt_info)

                    # Send reserved functions over to existing clients
                    clt_cnt_header = make_header(
                        f"$CLTCONN$ {json.dumps(clt_info)}", self.header_len
                    )
                    clt_to_send = [clt for clt in self.clients if clt != connection]

                    for sock_client in clt_to_send:
                        sock_client.send(
                            clt_cnt_header
                            + f"$CLTCONN$ {json.dumps(clt_info)}".encode()
                        )

                else:
                    # "header" - The header of the msg, mostly not needed
                    # "data" - The actual data/content of the msg
                    message = receive_message(notified_sock, self.header_len)

                    if not message or message["data"] == b"$USRCLOSE$":
                        # Most likely client disconnect, sometimes can be client error
                        client_disconnect = self.clients[notified_sock]["ip"]
                        more_client_info = self.clients[notified_sock]

                        # Remove socket from lists and dictionaries
                        self._sockets_list.remove(notified_sock)
                        del self.clients[notified_sock]
                        del self.clients_rev[
                            next(
                                _dict_tupkey_lookup_key(
                                    client_disconnect, self.clients_rev
                                )
                            )
                        ]

                        if "leave" in self.funcs:
                            # Reserved function - Leave
                            self._call_function(
                                "leave",
                                {
                                    "ip": client_disconnect,
                                    "name": more_client_info["name"],
                                    "group": more_client_info["group"],
                                },
                            )

                        # Send reserved functions to existing clients
                        clt_dcnt_header = make_header(
                            f"$CLTDISCONN$ {json.dumps(more_client_info)}",
                            self.header_len,
                        )

                        for clt_to_send in self.clients:
                            clt_to_send.send(
                                clt_dcnt_header
                                + f"$CLTDISCONN$ {json.dumps(more_client_info)}".encode()
                            )
                    else:
                        # Actual client message received
                        clt_data = self.clients[notified_sock]
                        usr_sent_dict = False

                        if message["data"] == b"$DH_NUMS$":
                            if not self.tls_arguments["tls"]:
                                # The server's not using TLS
                                no_tls_header = make_header("$NOTLS$", self.header_len)
                                notified_sock.send(no_tls_header + b"$NOTLS$")
                            continue
                        elif message["data"].startswith(b"$USRSENTDICT$"):
                            message["data"] = _removeprefix(
                                message["data"], b"$USRSENTDICT$"
                            )
                            usr_sent_dict = True
                        elif message["data"].startswith(b"$GETCLT$"):
                            try:
                                result = self.get_client(
                                    _removeprefix(
                                        message["data"], b"$GETCLT$ "
                                    ).decode()
                                )
                                del result["socket"]

                                clt = json.dumps(result)
                            except ValueError as e:
                                clt = '{"traceback": "' + str(e) + '"'
                            except TypeError:
                                clt = '{"traceback": "$NOEXIST$"}'

                            clt_header = make_header(clt.encode(), self.header_len)

                            print(clt)
                            notified_sock.send(clt_header + clt.encode())

                        for matching_reserve in [b"$CHNAME$", b"$CHGROUP$"]:
                            if message["data"].startswith(matching_reserve):
                                name_or_group = _removeprefix(
                                    message["data"], matching_reserve + b" "
                                ).decode()

                                if name_or_group == message["data"].decode():
                                    # Most likely request to reset name
                                    name_or_group = None

                                clt_info = self.clients[notified_sock]
                                clt_dict = {"ip": clt_info["ip"]}

                                if matching_reserve == b"$CHNAME$":
                                    clt_dict["name"] = name_or_group
                                    clt_dict["group"] = clt_info["group"]

                                elif matching_reserve == b"$CHGROUP$":
                                    clt_dict["name"] = clt_info["name"]
                                    clt_dict["group"] = name_or_group

                                del self.clients[notified_sock]
                                self.clients[notified_sock] = clt_dict

                                for key, value in dict(self.clients_rev).items():
                                    if value == notified_sock:
                                        del self.clients_rev[key]
                                self.clients_rev[
                                    tuple(clt_dict.values())
                                ] = notified_sock

                                if (
                                    "name_change" in self.funcs
                                    and matching_reserve == b"$CHNAME$"
                                ):
                                    old_name = clt_info["name"]
                                    new_name = name_or_group

                                    self._call_function(
                                        "name_change", clt_dict, old_name, new_name
                                    )
                                elif (
                                    "group_change" in self.funcs
                                    and matching_reserve == b"$CHGROUP$"
                                ):
                                    old_group = clt_info["group"]
                                    new_group = name_or_group

                                    self._call_function(
                                        "group_change", clt_dict, old_group, new_group
                                    )

                        if "message" in self.funcs:
                            # Reserved function - message
                            inner_clt_data = self.clients[notified_sock]
                            parse_content = message["data"]

                            ####################################
                            ### Type hinting -> Type casting ###
                            ####################################
                            if usr_sent_dict:
                                parse_content = json.loads(message["data"].decode())
                            temp_parse_content = _type_cast(
                                self.funcs["message"]["type_hint"]["msg"],
                                message["data"],
                                self.funcs["message"],
                            )

                            if temp_parse_content == parse_content and usr_sent_dict:
                                parse_content = json.loads(message["data"])
                            elif temp_parse_content is not None:
                                parse_content = temp_parse_content
                            elif temp_parse_content is None:
                                raise InvalidTypeCast(
                                    f"{self.funcs['message']['type_hint']['msg']} is an invalid "
                                    f"type cast!"
                                )

                            self._call_function(
                                "message", inner_clt_data, parse_content
                            )

                        has_corresponding_function = False
                        parse_content = None  # FINE pycharm
                        command = None

                        for matching_cmd, func in self.funcs.items():
                            if message["data"].startswith(matching_cmd.encode()):
                                has_corresponding_function = True
                                command = matching_cmd

                                parse_content = message["data"][len(matching_cmd) + 1 :]

                                temp_parse_content = _type_cast(
                                    func["type_hint"]["msg"],
                                    parse_content,
                                    func,
                                )

                                if (
                                    temp_parse_content == parse_content
                                    and usr_sent_dict
                                ):
                                    parse_content = json.loads(parse_content)
                                elif temp_parse_content is not None:
                                    parse_content = temp_parse_content
                                elif temp_parse_content is None:
                                    raise InvalidTypeCast(
                                        f"{func['type_hint']['msg']} is an invalid "
                                        f"type cast!"
                                    )

                                if not func["threaded"]:
                                    func["func"](clt_data, parse_content)
                                else:
                                    function_thread = threading.Thread(
                                        target=func["func"],
                                        args=(
                                            clt_data,
                                            parse_content,
                                        ),
                                    )
                                    function_thread.setDaemon(
                                        True
                                    )  # FORGIVE ME PEP 8 FOR I HAVE SINNED
                                    function_thread.start()

                        # Caching
                        if self.cache_size >= 0:
                            if has_corresponding_function:
                                cache_content = parse_content
                            else:
                                cache_content = message["data"]
                            self.cache.append(
                                MessageCacheMember(
                                    {
                                        "header": message["header"],
                                        "content": cache_content,
                                        "called": has_corresponding_function,
                                        "command": command,
                                    }
                                )
                            )

                            if 0 < self.cache_size < len(self.cache):
                                self.cache.pop(0)

    def close(self):
        """
        Closes the server; ALL clients will be disconnected, then the
        server socket will be closed.

        Running `server.run()` won't do anything now.
        """

        self._closed = True
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
        # so we will kindly exterminate it
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
    print("Why are you running this file? You're weird...")
