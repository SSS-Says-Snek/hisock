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

import inspect  # Inspect, for type-hinting detection
import socket  # Socket module, duh
import select  # Yes, we're using select for multiple clients
import json  # To send multiple data without 10 billion commands
import ast  # For certain type hints
import re  # Regex, to make sure arguments are passed correctly
import threading
import warnings  # Warnings, for errors that aren't severe
import builtins  # Builtins, to convert string methods into builtins
from typing import Callable, Union  # Typing, for cool type hints
from ipaddress import IPv4Address

# Utilities
from hisock import constants

try:
    from .utils import (
        NoHeaderWarning,
        NoMessageException,
        receive_message,
        _removeprefix,
        make_header,
        _dict_tupkey_lookup,
        _dict_tupkey_lookup_key,
        _type_cast_server,
    )
except ImportError:
    # relative import doesn't work for non-pip builds
    from utils import (
        NoHeaderWarning,
        NoMessageException,
        receive_message,
        _removeprefix,
        make_header,
        _dict_tupkey_lookup,
        _dict_tupkey_lookup_key,
        _type_cast_server,
    )


class HiSockServer:
    """
    The server class for hisock
    HiSockServer offers a neater way to send and receive data than
    sockets. You don't need to worry about headers now, yay!

    :param addr: A two-element tuple, containing the IP address and the
        port number of where the server should be hosted.
        Due to the nature of reserved ports, it is recommended to host the
        server with a port number that's higher than 1023.
        Only IPv4 currently supported
    :type addr: tuple
    :param blocking: A boolean, set to whether the server should block the loop
        while waiting for message or not.
        Default passed in by :meth:`start_server` is True
    :type blocking: bool, optional
    :param max_connections: The number of maximum connections :class:`HiSockServer` should accept, before
        refusing clients' connections. Pass in 0 for unlimited connections.
        Default passed in  by :meth:`start_server` is 0
    :type max_connections: int, optional
    :param header_len: An integer, defining the header length of every message.
        A smaller header length would mean a smaller maximum message
        length (about 10**header_len).
        Any client connecting MUST have the same header length as the server,
        or else it will crash.
        Default passed in by :meth:`start_server` is 16 (maximum length: 10 quadrillion bytes)
    :type header_len: int, optional

    :ivar tuple addr: A two-element tuple, containing the IP address and the
        port number
    :ivar int header_len: An integer, storing the header length of each "message"
    :ivar dict clients: A dictionary, with the socket as its key, and the client info as its value
    :ivar dict clients_rev: A dictionary, with the client info as its key, and the socket as its value
    :ivar dict funcs: A list of functions registered with decorator :meth:`on`.
        **This is mainly used for under-the-hood-code**

    .. note::

       It is advised to use :meth:`get_client` or :meth:`get_all_clients` instead of
       using :attr:`clients` and :attr:`clients_rev`

       Also, **only IPv4 is currently supported**
    """

    def __init__(
        self,
        addr: tuple[str, int],
        blocking: bool = True,
        max_connections: int = 0,
        header_len: int = 16,
        tls: Union[dict, str] = None,
    ):
        # Binds address and header length to class attributes
        self.addr = addr
        self.header_len = header_len

        # Socket initialization
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(blocking)
        try:
            self.sock.bind(addr)
        except socket.gaierror:
            raise TypeError("Connection failed (most likely due to invalid IP)")
        self.sock.listen(max_connections)

        # Function related storage
        self.funcs = {}
        self.reserved_functions = [
            "join",
            "leave",
            "message",
            "name_change",
            "group_change",
        ]

        # Dictionaries and Lists for client lookup
        self._sockets_list = [self.sock]
        self.clients = {}
        self.clients_rev = {}

        if tls is None:
            self.tls_arguments = {"tls": False}  # If TLS is false, then no TLS
        else:
            if isinstance(tls, dict):
                self.tls_arguments = tls
            elif isinstance(tls, str):
                if tls == "default":
                    self.tls_arguments = {
                        "rsa_authentication_dir": ".pubkeys",
                        "suite": "default",
                        "diffie_hellman": constants.DH_DEFAULT,
                    }
        self.called_run = False
        self._closed = False

    def __str__(self):
        """Example: <HiSockServer serving at 192.168.1.133:33333>"""
        return f"<HiSockServer serving at {':'.join(map(str, self.addr))}>"

    def __gt__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) > '192.168.1.131'"""
        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for > comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) > IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of port, if there is port

        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    def __ge__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) >= '192.168.1.131'"""
        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for >= comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) >= IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of port, if there is port

        return IPv4Address(self.addr[0]) >= IPv4Address(ip[0])

    def __lt__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) < '192.168.1.131'"""
        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for < comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) < IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of port, if there is port

        return IPv4Address(self.addr[0]) < IPv4Address(ip[0])

    def __le__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) <= '192.168.1.131'"""
        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for <= comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) <= IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of port, if there is port

        return IPv4Address(self.addr[0]) <= IPv4Address(ip[0])

    def __eq__(self, other: Union[HiSockServer, str]):
        """Example: HiSockServer(...) == '192.168.1.131'"""
        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for == comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) == IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of port, if there is port

        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    def __len__(self):
        """Example: len(HiSockServer(...)) -> Num clients"""
        return len(self.clients)

    class _TLS:
        """
        Base class for establishing TLS connections,
        and getting information about it

        TLS (Transport Layer Security) is a protocol, that basically is
        used on every internet connection. It establishes
        a secure connection between the client and the server, to prevent
        eavesdropping.

        While TLS usually allows clients and servers to pick what "suites"
        they have available, there is currently only one predefined suite
        to be used. Of course, as the projects gets bigger, more suites
        would be added.

        CLASS AND TLS IMPLEMENTATION NOT READY YET - DO NOT USE
        """

        def __init__(self, outer):
            self.outer = outer

    class _on:
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
                self.cmd_activation not in self.outer.reserved_functions
                or self.cmd_activation == "message"
            ):
                raise ValueError(
                    f"Incorrect number of arguments: {len(func_args)} != 2"
                )

            annots = inspect.getfullargspec(func).annotations

            if (
                self.cmd_activation not in self.outer.reserved_functions
                or self.cmd_activation == "message"
            ):
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
                "type_hint": {"clt": clt_annotation, "msg": msg_annotation},
            }

            self.outer.funcs[self.cmd_activation] = func_dict

            # Returns inner function, like a decorator would do
            return func

    def on(self, command: str):
        """
        A decorator that adds a function that gets called when the server
        receives a matching command

        Reserved functions are functions that get activated on
        specific events. Currently, there are 3 for HiSockServer:

        1. join - Activated when a client connects to the server

        2. leave - Activated when a client disconnects from the server

        3. message - Activated when a client messages to the server

        The parameters of the function depend on the command to listen.
        For example, reserved commands `join` and `leave` have only one
        client parameter passed, while reserved command `message` has two:
        Client Data, and Message.
        Other nonreserved functions will also be passed in the same
        parameters as `message`

        In addition, certain type casting is available to nonreserved functions.
        That means, that, using type hints, you can automatically convert
        between needed instances. The type casting currently supports:

        1. bytes -> int (Will raise exception if bytes is not numerical)

        2. bytes -> str (Will raise exception if there's a unicode error)

        Type casting for reserved commands is scheduled to be
        implemented, and is currently being worked on.

        :param command: A string, representing the command the function should activate
            when receiving it
        :type command: str

        :return: The same function (The decorator just appended the function to a stack)
        :rtype: function
        """
        # Passes in outer to _on decorator/class
        return self._on(self, command)

    def close(self):
        """
        Closes the server; ALL clients will be disconnected, then the
        server socket will be closed.

        Running `server.run()` won't do anything now.
        :return:
        """
        self._closed = True
        self.disconnect_all_clients()
        self.sock.close()

    def disconnect_client(
        self, client: str
    ):  # TODO: WILL ADD MORE DIVERSE SUPPORT FOR ARGS
        """
        Disconnects a specific client
        Different formats of the client is supported. It can be:

        - An IP + Port format, written as "ip:port"

        - A client name, if it exists

        :param client: The client to disconnect. The format could be either by IP+Port,
            or a client name
        """
        disconn_header = make_header(b"$DISCONN$", self.header_len)
        if isinstance(client, tuple):
            # Formats client IP tuple, and raises Exceptions if format's wrong
            if len(client) == 2 and isinstance(client[0], str):
                if re.search(r"^((\d?){3}\.){3}(\d\d?\d?)$", client[0]) and isinstance(
                    client[1], int
                ):
                    client = f"{client[0]}:{client[1]}"
                else:
                    raise ValueError(
                        f"Client tuple format should be ('ip.ip.ip.ip', port), not "
                        f"{client}"
                    )
            else:
                raise ValueError(
                    f"Client tuple format should be ('ip.ip.ip.ip', port), not "
                    f"{client}"
                )

        if re.search(r"^((\d?){3}\.){3}(\d\d?\d?):\d(\d?){4}$", client):
            # Matching: 523.152.135.231:92344   Invalid IP handled by Python
            # Try IP Address, should be unique
            split_client = client.split(":")
            reconstructed_client = []

            # Checks IP correctness
            try:
                reconstructed_client.append(map(int, split_client[0].split(".")))
            except ValueError:
                raise ValueError("IP is not numerical (only IPv4 currently supported)")
            try:
                reconstructed_client.append(int(split_client[1]))
            except ValueError:
                raise ValueError(
                    "Port is not numerical (only IPv4 currently supported)"
                )

            for subip in reconstructed_client[0]:
                if not 0 <= subip < 255:
                    raise ValueError(f"{client} is not a valid IP address")
            if not 0 < reconstructed_client[1] < 65535:
                raise ValueError(f"{split_client[1]} is not a valid port (1-65535)")

            try:
                client_sock = next(
                    _dict_tupkey_lookup(
                        (client.split(":")[0], reconstructed_client[1]),
                        self.clients_rev,
                        idx_to_match=0,
                    )
                )
            except StopIteration:
                raise TypeError(f"Client with IP {client} is not connected")
            client_sock.send(disconn_header + b"$DISCONN$")
        else:
            # Try name or group
            try:
                mod_clients_rev = {}
                for key, value in self.clients_rev.items():
                    mod_key = (key[0], key[1])  # Groups shouldn't count
                    mod_clients_rev[mod_key] = value

                client_sock = list(
                    _dict_tupkey_lookup(client, mod_clients_rev, idx_to_match=1)
                )
            except StopIteration:
                raise TypeError(f'Client with name "{client}"does not exist')

            if len(client_sock) > 1:
                warnings.warn(
                    f'{len(client_sock)} clients with name "{client}" detected; sending data to '
                    f"Client with IP {':'.join(map(str, client_sock[0].getpeername()))}"
                )

            client_sock[0].send(disconn_header + b"$DISCONN$")

    def disconnect_all_clients(self):
        """Disconnect all clients."""
        disconn_header = make_header(b"$DISCONN$", self.header_len)
        for client in self.clients:
            client.send(disconn_header + b"$DISCONN$")

    def send_all_clients(self, command: str, content: bytes):
        """
        Sends the commmand and content to *ALL* clients connected

        :param command: A string, representing the command to send to every client
        :type command: str
        :param content: A bytes-like object, containing the message/content to send
            to each client
        :type content: bytes
        """
        content_header = make_header(command.encode() + b" " + content, self.header_len)
        for client in self.clients:
            client.send(content_header + command.encode() + b" " + content)

    def send_group(self, group: str, command: str, content: bytes):
        """
        Sends data to a specific group.
        Groups are recommended for more complicated servers or multipurpose
        servers, as it allows clients to be divided, which allows clients to
        be sent different data for different purposes.

        :param group: A string, representing the group to send data to
        :type group: str
        :param command: A string, containing the command to send
        :type command: str
        :param content: A bytes-like object, with the content/message
            to send
        :type content: bytes
        :raise TypeError: The group does not exist
        """
        # Identifies group
        group_clients = _dict_tupkey_lookup(group, self.clients_rev, idx_to_match=2)
        group_clients = list(group_clients)

        if len(group_clients) == 0:
            raise TypeError(f"Group {group} does not exist")
        else:
            content_header = make_header(
                command.encode() + b" " + content, self.header_len
            )
            # Send content and header to all clients in group
            for clt_to_send in group_clients:
                clt_to_send.send(content_header + command.encode() + b" " + content)

    def send_client(self, client: Union[str, tuple], command: str, content: bytes):
        """
        Sends data to a specific client.
        Different formats of the client is supported. It can be:

        - An IP + Port format, written as "ip:port"

        - A client name, if it exists

        :param client: The client to send data to. The format could be either by IP+Port,
            or a client name
        :type client: Union[str, tuple]
        :param command: A string, containing the command to send
        :type command: str
        :param content: A bytes-like object, with the content/message
            to send
        :type content: bytes
        :raise ValueError: Client format is wrong
        :raise TypeError: Client does not exist
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected
        """
        content_header = make_header(command.encode() + b" " + content, self.header_len)
        # r"((\b(0*(?:[1-9]([0-9]?){2}|255))\b\.){3}\b(0*(?:[1-9][0-9]?[0-9]?|255))\b):(\b(0*(?:[1-9]([0-9]?){4}|65355))\b)"

        if isinstance(client, tuple):
            # Formats client IP tuple, and raises Exceptions if format's wrong
            if len(client) == 2 and isinstance(client[0], str):
                if re.search(r"^((\d?){3}\.){3}(\d\d?\d?)$", client[0]) and isinstance(
                    client[1], int
                ):
                    client = f"{client[0]}:{client[1]}"
                else:
                    raise ValueError(
                        f"Client tuple format should be ('ip.ip.ip.ip', port), not "
                        f"{client}"
                    )
            else:
                raise ValueError(
                    f"Client tuple format should be ('ip.ip.ip.ip', port), not "
                    f"{client}"
                )

        if re.search(r"^((\d?){3}\.){3}(\d\d?\d?):\d(\d?){4}$", client):
            # Matching: 523.152.135.231:92344   Invalid IP handled by Python
            # Try IP Address, should be unique
            split_client = client.split(":")
            reconstructed_client = []

            # Checks IP correctness
            try:
                reconstructed_client.append(map(int, split_client[0].split(".")))
            except ValueError:
                raise ValueError("IP is not numerical (only IPv4 currently supported)")
            try:
                reconstructed_client.append(int(split_client[1]))
            except ValueError:
                raise ValueError(
                    "Port is not numerical (only IPv4 currently supported)"
                )

            for subip in reconstructed_client[0]:
                if not 0 <= subip < 255:
                    raise ValueError(f"{client} is not a valid IP address")
            if not 0 < reconstructed_client[1] < 65535:
                raise ValueError(f"{split_client[1]} is not a valid port (1-65535)")

            try:
                client_sock = next(
                    _dict_tupkey_lookup(
                        (client.split(":")[0], reconstructed_client[1]),
                        self.clients_rev,
                        idx_to_match=0,
                    )
                )
            except StopIteration:
                raise TypeError(f"Client with IP {client} is not connected")

            client_sock.send(content_header + command.encode() + b" " + content)
        else:
            # Try name or group
            try:
                mod_clients_rev = {}
                for key, value in self.clients_rev.items():
                    mod_key = (key[0], key[1])  # Groups shouldn't count
                    mod_clients_rev[mod_key] = value

                client_sock = list(
                    _dict_tupkey_lookup(client, mod_clients_rev, idx_to_match=1)
                )
            except StopIteration:
                raise TypeError(f'Client with name "{client}"does not exist')

            content_header = make_header(
                command.encode() + b" " + content, self.header_len
            )

            if len(client_sock) > 1:
                warnings.warn(
                    f'{len(client_sock)} clients with name "{client}" detected; sending data to '
                    f"Client with IP {':'.join(map(str, client_sock[0].getpeername()))}"
                )

            client_sock[0].send(content_header + command.encode() + b" " + content)

    def send_client_raw(self, client, content: bytes):
        """
        Sends data to a specific client, *without a command*
        Different formats of the client is supported. It can be:

        - An IP + Port format, written as "ip:port"

        - A client name, if it exists

        :param client: The client to send data to. The format could be either by IP+Port,
            or a client name
        :type client: Union[str, tuple]
        :param content: A bytes-like object, with the content/message
            to send
        :type content: bytes
        :raise ValueError: Client format is wrong
        :raise TypeError: Client does not exist
        :raise Warning: Using client name and more than one client with
            the same name is detected
        """
        content_header = make_header(content, self.header_len)
        # r"((\b(0*(?:[1-9]([0-9]?){2}|255))\b\.){3}\b(0*(?:[1-9][0-9]?[0-9]?|255))\b):(\b(0*(?:[1-9]([0-9]?){4}|65355))\b)"

        if isinstance(client, tuple):
            if len(client) == 2 and isinstance(client[0], str):
                if re.search(r"(((\d?){3}\.){3}(\d?){3})", client[0]) and isinstance(
                    client[1], int
                ):
                    client = f"{client[0]}:{client[1]}"
                else:
                    raise ValueError(
                        f"Client tuple format should be ('ip.ip.ip.ip', port), not "
                        f"{client}"
                    )
            else:
                raise ValueError(
                    f"Client tuple format should be ('ip.ip.ip.ip', port), not "
                    f"{client}"
                )

        if re.search(r"(((\d?){3}\.){3}(\d?){3}):(\d?){5}", client):
            # Matching: 523.152.135.231:92344   Invalid IP handled by Python
            # Try IP Address, should be unique
            split_client = client.split(":")
            reconstructed_client = []
            try:
                reconstructed_client.append(map(int, split_client[0].split(".")))
            except ValueError:
                raise ValueError("IP is not numerical (only IPv4 currently supported)")
            try:
                reconstructed_client.append(int(split_client[1]))
            except ValueError:
                raise ValueError(
                    "Port is not numerical (only IPv4 currently supported)"
                )

            for subip in reconstructed_client[0]:
                if not 0 <= subip < 255:
                    raise ValueError(f"{client} is not a valid IP address")
            if not 0 < reconstructed_client[1] < 65535:
                raise ValueError(f"{split_client[1]} is not a valid port (1-65535)")

            try:
                client_sock = next(
                    _dict_tupkey_lookup(
                        (client.split(":")[0], reconstructed_client[1]),
                        self.clients_rev,
                        idx_to_match=0,
                    )
                )
            except StopIteration:
                raise TypeError(f"Client with IP {client} is not connected")

            client_sock.send(content_header + content)
        else:
            # Try name or group
            try:
                mod_clients_rev = {}
                for key, value in self.clients_rev.items():
                    mod_key = (key[0], key[1])  # Groups shouldn't count
                    mod_clients_rev[mod_key] = value

                client_sock = list(
                    _dict_tupkey_lookup(client, mod_clients_rev, idx_to_match=1)
                )
            except StopIteration:
                raise TypeError(f'Client with name "{client}"does not exist')

            content_header = make_header(content, self.header_len)

            if len(client_sock) > 1:
                # More than one client with same name
                warnings.warn(
                    f'{len(client_sock)} clients with name "{client}" detected; sending data to '
                    f"Client with IP {':'.join(map(str, client_sock[0].getpeername()))}"
                )

            # Sends to client
            client_sock[0].send(content_header + content)

    def send_group_raw(self, group: str, content: bytes):
        """
        Sends data to a specific group, without commands.
        Groups are recommended for more complicated servers or multipurpose
        servers, as it allows clients to be divided, which allows clients to
        be sent different data for different purposes.

        Non-command-attached content is recommended to be used alongside with
        :meth:`HiSockClient.recv_raw`

        :param group: A string, representing the group to send data to
        :type group: str
        :param content: A bytes-like object, with the content/message
            to send
        :type content: bytes
        :raise TypeError: The group does not exist
        """
        # Identifies group
        group_clients = _dict_tupkey_lookup(group, self.clients_rev, idx_to_match=2)
        group_clients = list(group_clients)

        if len(group_clients) == 0:
            raise TypeError(f"Group {group} does not exist")
        else:
            content_header = make_header(content, self.header_len)
            # Send content and header to all clients in group
            for clt_to_send in group_clients:
                clt_to_send.send(content_header + content)

    def run(self):
        """
        Runs the server. This method handles the sending and receiving of data,
        so it should be run once every iteration of a while loop, as to not
        lose valuable information
        """
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
                        self.funcs["join"]["func"](clt_info)

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
                            self.funcs["leave"]["func"](
                                {
                                    "ip": client_disconnect,
                                    "name": more_client_info["name"],
                                    "group": more_client_info["group"],
                                }
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

                        if message["data"] == b"$DH_NUMS$":
                            if not self.tls_arguments["tls"]:
                                # The server's not using TLS
                                no_tls_header = make_header("$NOTLS$", self.header_len)
                                notified_sock.send(no_tls_header + b"$NOTLS$")
                            continue
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

                                    self.funcs["name_change"]["func"](
                                        clt_dict, old_name, new_name
                                    )
                                elif (
                                    "group_change" in self.funcs
                                    and matching_reserve == b"$CHGROUP$"
                                ):
                                    old_group = clt_info["group"]
                                    new_group = name_or_group

                                    self.funcs["group_change"]["func"](
                                        clt_dict, old_group, new_group
                                    )

                        for matching_cmd, func in self.funcs.items():
                            if message["data"].startswith(matching_cmd.encode()):
                                parse_content = message["data"][len(matching_cmd) + 1 :]

                                temp_parse_content = _type_cast_server(
                                    func["type_hint"]["msg"],
                                    parse_content,
                                    parse_content,
                                )
                                if temp_parse_content is not None:
                                    parse_content = temp_parse_content
                                func["func"](clt_data, parse_content)

                        if "message" in self.funcs:
                            # Reserved function - message
                            inner_clt_data = self.clients[notified_sock]
                            parse_content = message["data"]

                            ####################################################
                            #         Type hinting -> Type casting             #
                            ####################################################

                            if self.funcs["message"]["type_hint"]["msg"] == str:
                                try:
                                    parse_content = message["data"].decode()
                                except UnicodeDecodeError as e:
                                    raise TypeError(
                                        f"Type casting from bytes to string failed\n{str(e)}"
                                    )
                            elif self.funcs["message"]["type_hint"]["msg"] == int:
                                try:
                                    parse_content = float(message["data"])
                                except ValueError as e:
                                    raise TypeError(
                                        f"Type casting from bytes to int failed for function "
                                        f"\"{self.funcs['message']['name']}\":\n"
                                        f"           {e}"
                                    ) from ValueError
                            elif self.funcs["message"]["type_hint"]["msg"] == float:
                                try:
                                    parse_content = int(message["data"])
                                except ValueError as e:
                                    raise TypeError(
                                        "Type casting from bytes to float failed for function "
                                        f"\"{self.funcs['message']['name']}\":\n"
                                        f"           {e}"
                                    ) from ValueError

                            for _type in [list, dict]:
                                if self.funcs["message"]["type_hint"]["msg"] == _type:
                                    try:
                                        parse_content = json.loads(
                                            message["data"].decode()
                                        )
                                    except UnicodeDecodeError:
                                        raise TypeError(
                                            f"Cannot decode message data during "
                                            f"bytes->{_type.__name__} type cast"
                                            "(current implementation requires string to "
                                            "type cast, not bytes)"
                                        ) from UnicodeDecodeError
                                    except ValueError:
                                        raise TypeError(
                                            f"Type casting from bytes to {_type.__name__} "
                                            f"failed for function \"{self.funcs['message']['name']}\""
                                            f":\n           Message is not a {_type.__name__}"
                                        ) from ValueError
                                    except Exception as e:
                                        raise TypeError(
                                            f"Type casting from bytes to {_type.__name__} "
                                            f"failed for function \"{self.funcs['message']['name']}\""
                                            f":\n           {e}"
                                        ) from type(e)

                            self.funcs["message"]["func"](inner_clt_data, parse_content)

    def get_group(self, group: str):
        """
        Gets all clients from a specific group

        :param group: A string, representing the group to look up
        :type group: str
        :raise TypeError: Group does not exist

        :return: A list of dictionaries of clients in that group, containing
          the address, name, group, and socket
        :rtype: list
        """
        group_clients = list(
            _dict_tupkey_lookup_key(group, self.clients_rev, idx_to_match=2)
        )
        mod_group_clients = []

        if len(group_clients) == 0:
            raise TypeError(f"Group {group} does not exist")

        for clt in group_clients:
            # Loops through group clients and append to list
            clt_conn = self.clients_rev[clt]
            mod_dict = {
                "ip": clt[0],
                "name": clt[1],
                "group": clt[2],
                "socket": clt_conn,
            }
            mod_group_clients.append(mod_dict)

        return mod_group_clients

    def get_all_clients(self, key: Union[Callable, str] = None):
        """
        Get all clients currently connected to the server.
        This is recommended over the class attribute `self._clients` or
        `self.clients_rev`, as it is in a dictionary-like format

        :param key: If specified, there are two outcomes: If it is a string,
            it will search for the dictionary for the key,
            and output it to a list (currently support "ip", "name", "group").
            Finally, if it is a callable, it will try to integrate the callable
            into the output (CURRENTLY NOT SUPPORTED YET)
        :type key: Union[Callable, str], optional
        :return: A list of dictionaries, with the clients
        :rtype: list[dict, ...]
        """
        clts = []
        for clt in self.clients_rev:
            clt_dict = {
                dict_key: clt[value]
                for value, dict_key in enumerate(["ip", "name", "group"])
            }
            clts.append(clt_dict)

        filter_clts = []
        if isinstance(key, str):
            if key in ["ip", "name", "group"]:
                for filter_clt in clts:
                    filter_clts.append(filter_clt[key])
        elif isinstance(key, Callable):
            filter_clts = list(filter(key, clts))

        if filter_clts:
            return filter_clts
        return clts

    def get_client(self, client: Union[str, tuple[str, int]]):
        """
        Gets a specific client's information, based on either:

        1. The client name

        2. The client IP+Port

        3. The client IP+Port, in a 2-element tuple

        :param client: A parameter, representing the specific client to look up.
            As shown above, it can either be represented
            as a string, or as a tuple.
        :type client: Union[str, tuple]
        :raise ValueError: Client argument is invalid
        :raise TypeError: Client does not exist

        :return: A dictionary of the client's info, including
          IP+Port, Name, Group, and Socket
        :rtype: dict
        """
        if isinstance(client, tuple):
            if len(client) == 2 and isinstance(client[0], str):
                if re.search(r"(((\d?){3}\.){3}(\d?){3})", client[0]) and isinstance(
                    client[1], int
                ):
                    client = f"{client[0]}:{client[1]}"
                else:
                    raise ValueError(
                        f"Client tuple format should be ('ip.ip.ip.ip', port), not "
                        f"{client}"
                    )
            else:
                raise ValueError(
                    f"Client tuple format should be ('ip.ip.ip.ip', port), not "
                    f"{client}"
                )

        if re.search(r"(((\d?){3}\.){3}(\d?){3}):(\d?){5}", client):
            # Matching: 523.152.135.231:92344   Invalid IP handled by Python
            # Try IP Address, should be unique
            split_client = client.split(":")
            reconstructed_client = []
            try:
                reconstructed_client.append(map(int, split_client[0].split(".")))
            except ValueError:
                raise ValueError("IP is not numerical (only IPv4 currently supported)")
            try:
                reconstructed_client.append(int(split_client[1]))
            except ValueError:
                raise ValueError(
                    "Port is not numerical (only IPv4 currently supported)"
                )

            for subip in reconstructed_client[0]:
                if not 0 <= subip < 255:
                    raise ValueError(f"{client} is not a valid IP address")
            if not 0 < reconstructed_client[1] < 65535:
                raise ValueError(f"{split_client[1]} is not a valid port (1-65535)")

            try:
                client_tup = (client.split(":")[0], reconstructed_client[1])
                client_sock = next(
                    _dict_tupkey_lookup(client_tup, self.clients_rev, idx_to_match=0)
                )
                client_info = next(
                    _dict_tupkey_lookup_key(
                        client_tup, self.clients_rev, idx_to_match=0
                    )
                )
                client_dict = {
                    "ip": client_info[0],
                    "name": client_info[1],
                    "group": client_info[2],
                    "socket": client_sock,
                }

                return client_dict
            except StopIteration:
                raise TypeError(f"Client with IP {client} is not connected")
        else:
            mod_clients_rev = {}
            for key, value in self.clients_rev.items():
                mod_key = (key[0], key[1])  # Groups shouldn't count
                mod_clients_rev[mod_key] = value

            client_sock = list(
                _dict_tupkey_lookup(client, mod_clients_rev, idx_to_match=1)
            )

            if len(client_sock) == 0:
                raise TypeError(f'Client with name "{client}"does not exist')
            elif len(client_sock) > 1:
                warnings.warn(
                    f'{len(client_sock)} clients with name "{client}" detected; getting info from '
                    f"Client with IP {':'.join(map(str, client_sock[0].getpeername()))}"
                )

            client_info = next(
                _dict_tupkey_lookup_key(client, self.clients_rev, idx_to_match=1)
            )

            client_dict = {
                "ip": client_info[0],
                "name": client_info[1],
                "group": client_info[2],
                "socket": client_sock[0],
            }

            return client_dict

    def get_addr(self):
        """
        Gets the address of where the hisock server is serving
        at.

        :return: A tuple, with the format (str IP, int port)
        """
        return self.addr


class _BaseThreadServer(HiSockServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _run(self):
        HiSockServer.run(self)


class ThreadedHiSockServer(_BaseThreadServer):
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
    """

    def __init__(self, addr, blocking=True, max_connections=0, header_len=16):
        super().__init__(addr, blocking, max_connections, header_len)
        self._thread = threading.Thread(target=self.run)

        self._stop_event = threading.Event()

    def stop_server(self):
        """Stops the server"""
        self._stop_event.set()
        self.sock.close()

    def run(self):
        """
        The main while loop to run the thread

        Refer to :class:`HiSockServer` for more details

        .. warning::
           This method is **NOT** recommended to be used in an actual
           production enviroment. This is used internally for the thread, and should
           not be interacted with the user
        """
        while self._stop_event:
            try:
                self._run()
            except (OSError, ValueError):
                break

    def start_server(self):
        """Starts the main server loop"""
        self._thread.start()

    def join(self):
        """Waits for the thread to be killed"""
        self._thread.join()


def start_server(addr, blocking=True, max_connections=0, header_len=16):
    """
    Creates a :class:`HiSockServer` instance. See :class:`HiSockServer` for more details

    :return: A :class:`HiSockServer` instance
    """
    return HiSockServer(addr, blocking, max_connections, header_len)


def start_threaded_server(addr, blocking=True, max_connections=0, header_len=16):
    """
    Creates a :class:`ThreadedHiSockServer` instance. See :class:`ThreadedHiSockServer`
    for more details

    :return: A :class:`ThreadedHiSockServer` instance
    """
    return ThreadedHiSockServer(addr, blocking, max_connections, header_len)


if __name__ == "__main__":
    print("Starting server...")
    # s = HiSockServer(('192.168.1.131', 33333))
    s = start_server(("192.168.1.131", 33333))

    @s.on("join")
    def test_sussus(yum_data):
        print("Whomst join, ahh it is", yum_data["name"])
        s.send_all_clients("Joe", b"Bidome")
        s.send_client(f"{yum_data['ip'][0]}:{yum_data['ip'][1]}", "Bruh", b"E")
        s.send_client(yum_data["ip"], "e", b"E")

        s.send_group("Amogus", "Test", b"TTT")

    @s.on("leave")
    def bruh(yum_data):
        print("Hmmm whomst leaved, ah it is", yum_data["name"])

    @s.on("name_change")
    def smth(clt_info, old_name, new_name):
        print(f"Bruh, {old_name} renamed to {new_name}!")
        s.disconnect_all_clients()

    # @s.on("message")
    # def why(client_data, message: str):
    #     print("Message reserved function aaa")
    #     print("Client data:", client_data)
    #     print("Message:", message)

    @s.on("Sussus")
    def a(_, msg):  # _ actually is clt_data
        s.send_all_clients("pog", msg)

    while True:
        s.run()
