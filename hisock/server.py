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
import re  # Regex, to make sure arguments are passed correctly
import threading
import warnings  # Warnings, for errors that aren't severe
import builtins  # Builtins, to convert string methods into builtins
from typing import Callable, Union  # Typing, for cool type hints
from ipaddress import IPv4Address  # ipaddress, for conparisons with <, >, ==, etc

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
        _type_cast,
        MessageCacheMember,
    )
    from . import utils
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
        _type_cast,
        MessageCacheMember,
    )
    import utils


# ░█████╗░░█████╗░██╗░░░██╗████████╗██╗░█████╗░███╗░░██╗██╗
# ██╔══██╗██╔══██╗██║░░░██║╚══██╔══╝██║██╔══██╗████╗░██║██║
# ██║░░╚═╝███████║██║░░░██║░░░██║░░░██║██║░░██║██╔██╗██║██║
# ██║░░██╗██╔══██║██║░░░██║░░░██║░░░██║██║░░██║██║╚████║╚═╝
# ╚█████╔╝██║░░██║╚██████╔╝░░░██║░░░██║╚█████╔╝██║░╚███║██╗
# ░╚════╝░╚═╝░░╚═╝░╚═════╝░░░░╚═╝░░░╚═╝░╚════╝░╚═╝░░╚══╝╚═╝
#      Change the above code IF and only IF you know
#                  what you are doing!


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
    :param cache_size: The size of the message cache.
        -1 or below for no message cache, 0 for an unlimited cache size,
        and any other number for the cache size.
    :type cache_size: int, optional
    :param keepalive: A bool indicating whether a keepalive signal should be sent or not.

        If this is True, then a signal will be sent to every client every minute to prevent
        hanging clients in the server. The clients have thirty seconds to send back an
        acknowledge signal to show that they are still alive.

        Defaults to True.
    :type keepalive: bool, optional
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
        cache_size: int = -1,
        keepalive: bool = True,
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
        self.cache_size = cache_size
        if cache_size >= 0:
            # cache_size <= -1: No cache
            self.cache = []

        # Dictionaries and Lists for client lookup
        self._sockets_list = [self.sock]
        self.clients = {}
        self.clients_rev = {}

        self.called_run = False
        self.closed = False

        # Keepalive
        self._keepalive_event = threading.Event()
        self._unresponsive_clients = []
        self.keepalive = keepalive

        if self.keepalive:
            keepalive_thread = threading.Thread(target=self._keepalive_thread)
            keepalive_thread.setDaemon(True)  # Another sin
            keepalive_thread.start()

    def __str__(self) -> str:
        """Example: <HiSockServer serving at 192.168.1.133:33333>"""
        return f"<HiSockServer serving at {':'.join(map(str, self.addr))}>"

    def __gt__(self, other: Union[HiSockServer, str]) -> bool:
        """Example: HiSockServer(...) > '192.168.1.131'"""
        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for > comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) > IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of port, if there is port

        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    def __ge__(self, other: Union[HiSockServer, str]) -> bool:
        """Example: HiSockServer(...) >= '192.168.1.131'"""
        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for >= comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) >= IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of port, if there is port

        return IPv4Address(self.addr[0]) >= IPv4Address(ip[0])

    def __lt__(self, other: Union[HiSockServer, str]) -> bool:
        """Example: HiSockServer(...) < '192.168.1.131'"""
        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for < comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) < IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of port, if there is port

        return IPv4Address(self.addr[0]) < IPv4Address(ip[0])

    def __le__(self, other: Union[HiSockServer, str]) -> bool:
        """Example: HiSockServer(...) <= '192.168.1.131'"""
        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for <= comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) <= IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of port, if there is port

        return IPv4Address(self.addr[0]) <= IPv4Address(ip[0])

    def __eq__(self, other: Union[HiSockServer, str]) -> bool:
        """Example: HiSockServer(...) == '192.168.1.131'"""
        if type(other) not in [self.__class__, str]:
            raise TypeError("Type not supported for == comparison")
        if isinstance(other, HiSockServer):
            return IPv4Address(self.addr[0]) == IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of port, if there is port

        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    def __len__(self) -> int:
        """Example: len(HiSockServer(...)) -> Num clients"""
        return len(self.clients)

    class _on:
        """Decorator used to handle something when receiving command"""

        def __init__(
            self, outer: HiSockServer, cmd_activation: str, threaded: bool = False
        ):
            # `outer` arg is for the HiSockServer instance
            # `cmd_activation` is the command... on activation (WOW)
            self.outer = outer
            self.cmd_activation = cmd_activation
            self.threaded = threaded

        def __call__(self, func: Callable) -> Callable:
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
                "threaded": self.threaded,
            }

            self.outer.funcs[self.cmd_activation] = func_dict

            # Returns inner function, like a decorator would do
            return func

    def _force_remove(self, sock):
        clt = self.clients[sock]["ip"]

        self._sockets_list.remove(sock)
        del self.clients[sock]
        del self.clients_rev[
            next(
                _dict_tupkey_lookup_key(
                    clt, self.clients_rev
                )
            )
        ]

    def _call_function(self, func_name, *args, **kwargs):
        if not self.funcs[func_name]["threaded"]:
            self.funcs[func_name]["func"](*args, **kwargs)
        else:
            function_thread = threading.Thread(
                target=self.funcs[func_name]["func"], args=args, kwargs=kwargs
            )
            function_thread.setDaemon(True)  # FORGIVE ME PEP 8 FOR I HAVE SINNED
            function_thread.start()

    def _keepalive_thread(self):
        keepalive_header = make_header(b"$KEEPALIVE$", self.header_len)
        disconn_keepalive_header = make_header(b"$DISCONNKEEP$", self.header_len)

        while not self._keepalive_event.is_set():
            self._keepalive_event.wait(30)

            # If statement is required, since if the event is set,
            # wait() will finish itself and move on to the next code
            if not self._keepalive_event.is_set():
                for client in self.clients:
                    self._unresponsive_clients.append(client)
                    client.send(keepalive_header + b"$KEEPALIVE$")

            self._keepalive_event.wait(30)

            # Same story
            if not self._keepalive_event.is_set():
                for client in self._unresponsive_clients:
                    client.send(disconn_keepalive_header + b"$DISCONNKEEP$")
                    client.shutdown(socket.SHUT_WR)
                    client.close()
                self._unresponsive_clients.clear()

    def on(self, command: str, threaded: bool = False) -> Callable:
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
        :param threaded: A boolean, representing if the function should be run in a thread
            in order to not block the run() loop.

            Defaults to False

        :return: The same function (The decorator just appended the function to a stack)
        :rtype: function
        """
        # Passes in outer to _on decorator/class
        return self._on(self, command, threaded)

    def close(self):
        """
        Closes the server; ALL clients will be disconnected, then the
        server socket will be closed.

        Running ``server.run()`` won't do anything now.
        """
        self.closed = True
        self._keepalive_event.set()
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

    def disconnect_all_clients(self, force=False):
        """Disconnect all clients."""
        if not force:
            disconn_header = make_header(b"$DISCONN$", self.header_len)
            for client in self.clients:
                client.send(disconn_header + b"$DISCONN$")
        else:
            for conn in self._sockets_list:
                conn.close()
            self._sockets_list.clear()
            self.clients.clear()
            self.clients_rev.clear()
            self._unresponsive_clients.clear()

    def send_all_clients(
        self,
        command: str,
        content: Union[
            bytes,
            dict[
                Union[str, int, float, bool, None], Union[str, int, float, bool, None]
            ],
        ],
    ):
        """
        Sends the commmand and content to *ALL* clients connected

        :param command: A string, representing the command to send to every client
        :type command: str
        :param content: A bytes-like object, containing the message/content to send
            to each client
        :type content: Union[bytes, dict]
        """
        if isinstance(content, dict):
            content = json.dumps(content).encode()

        content_header = make_header(command.encode() + b" " + content, self.header_len)
        for client in self.clients:
            client.send(content_header + command.encode() + b" " + content)

    def send_group(
        self,
        group: str,
        command: str,
        content: Union[
            bytes,
            dict[
                Union[str, int, float, bool, None], Union[str, int, float, bool, None]
            ],
        ],
    ):
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
        :type content: Union[bytes, dict]
        :raise TypeError: The group does not exist
        """
        # Identifies group
        group_clients = _dict_tupkey_lookup(group, self.clients_rev, idx_to_match=2)
        group_clients = list(group_clients)

        if len(group_clients) == 0:
            raise TypeError(f"Group {group} does not exist")
        else:
            if isinstance(content, dict):
                content = json.dumps(content).encode()

            content_header = make_header(
                command.encode() + b" " + content, self.header_len
            )
            # Send content and header to all clients in group
            for clt_to_send in group_clients:
                clt_to_send.send(content_header + command.encode() + b" " + content)

    def send_client(
        self,
        client: Union[str, tuple[str, int]],
        command: str,
        content: Union[
            bytes,
            dict[
                Union[str, int, float, bool, None], Union[str, int, float, bool, None]
            ],
        ],
    ):
        """
        Sends data to a specific client.
        Different formats of the client is supported. It can be:

        - An IP + Port format, written as "ip:port"

        - A client name, if it exists

        - A tuple with an (IP, Port) format

        :param client: The client to send data to. The format could be either by IP+Port,
            or a client name
        :type client: Union[str, tuple]
        :param command: A string, containing the command to send
        :type command: str
        :param content: A bytes-like object, with the content/message
            to send
        :type content: Union[bytes, dict]
        :raise ValueError: Client format is wrong
        :raise TypeError: Client does not exist
        :raise UserWarning: Using client name, and more than one client with
            the same name is detected
        """
        if isinstance(content, dict):
            content = json.dumps(content).encode()

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

            if isinstance(content, dict):
                content = json.dumps(content).encode()

            content_header = make_header(
                command.encode() + b" " + content, self.header_len
            )

            if len(client_sock) > 1:
                warnings.warn(
                    f'{len(client_sock)} clients with name "{client}" detected; sending data to '
                    f"Client with IP {':'.join(map(str, client_sock[0].getpeername()))}"
                )

            client_sock[0].send(content_header + command.encode() + b" " + content)

    def send_client_raw(
        self, client, content: bytes
    ):  # TODO: Add dict-sending support to this method
        """
        Sends data to a specific client, *without a command*
        Different formats of the client is supported. It can be:

        - An IP + Port format, written as "ip:port"

        - A client name, if it exists

        - A tuple with an (IP, Port) format

        :param client: The client to send data to. The format could be either by IP+Port,
            or a client name
        :type client: Union[str, tuple]
        :param content: A bytes-like object, with the content/message
            to send
        :type content: Union[bytes, dict]
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

            if isinstance(content, dict):
                content = json.dumps(content).encode()

            content_header = make_header(content, self.header_len)

            if len(client_sock) > 1:
                # More than one client with same name
                warnings.warn(
                    f'{len(client_sock)} clients with name "{client}" detected; sending data to '
                    f"Client with IP {':'.join(map(str, client_sock[0].getpeername()))}"
                )

            # Sends to client
            client_sock[0].send(content_header + content)

    def send_group_raw(
        self, group: str, content: bytes
    ):  # TODO: Add dict-sending support to this method
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
            if isinstance(content, dict):
                content = json.dumps(content).encode()

            content_header = make_header(content, self.header_len)
            # Send content and header to all clients in group
            for clt_to_send in group_clients:
                clt_to_send.send(content_header + content)

    def get_cache(
        self,
        idx: Union[int, slice, None] = None,
    ) -> list[MessageCacheMember]:
        """
        Gets the message cache.

        :param idx: An integer or ``slice``, specifying what specific message caches to return.

            Defaults to None (Retrieves the entire cache)
        :type idx: Union[int, slice], optional

        :return: A list of dictionaries, representing the cache
        :rtype: list[dict]
        """
        if idx is None:
            return self.cache
        else:
            return self.cache[idx]

    def run(self):
        """
        Runs the server. This method handles the sending and receiving of data,
        so it should be run once every iteration of a while loop, as to not
        lose valuable information. This is also called underhood in :meth:`start`.
        """
        self.called_run = True

        if not self.closed:
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
                    if notified_sock.fileno() == -1:
                        self._force_remove(notified_sock)
                        continue

                    message = receive_message(notified_sock, self.header_len)

                    if not message or message["data"] == b"$USRCLOSE$":
                        # Most likely client disconnect, sometimes can be client error
                        client_disconnect = self.clients[notified_sock]["ip"]
                        more_client_info = self.clients[notified_sock]

                        # Remove socket from lists and dictionaries
                        self._force_remove(notified_sock)

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
                        if notified_sock in self._unresponsive_clients:
                            self._unresponsive_clients.remove(notified_sock)

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

                        if message["data"] == b"$KEEPACK$":
                            self._unresponsive_clients.remove(notified_sock)
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

                            ####################################################
                            #         Type hinting -> Type casting             #
                            ####################################################
                            if usr_sent_dict:
                                parse_content = json.loads(message["data"])
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
                                raise utils.InvalidTypeCast(
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
                                    raise utils.InvalidTypeCast(
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
                                cache_content = parse_content  # Bruh pycharm it DOES exist if hcf is True
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

    def start(self):
        """
        Starts a while loop that actually runs the server long-term. Exactly equivalent to:

        .. code-block:: python
           while not server.closed:
               server.run()

        """
        while not self.closed:
            self.run()

    def get_group(self, group: str) -> list[dict[str, Union[str, socket.socket]]]:
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

    def get_all_clients(
        self, key: Union[Callable, str] = None
    ) -> list[dict[str, str]]:  # TODO: Add socket output as well
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

    def get_client(
        self, client: Union[str, tuple[str, int]]
    ) -> dict[str, Union[str, socket.socket]]:
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

    def get_addr(self) -> tuple[str, int]:
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
        while not self._stop_event.is_set():
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
        s.send_client(yum_data["ip"], "dicttest", {"Does this": "dict also work?"})

    @s.on("leave")
    def bruh(yum_data):
        print("Hmmm whomst leaved, ah it is", yum_data["name"])

    @s.on("name_change")
    def smth(clt_info, old_name, new_name):
        print(f"Bruh, {old_name} renamed to {new_name}!")
        s.send_client(clt_info["ip"], "shrek", b"")
        s.send_client(clt_info["ip"], "john", b"")
        # s.disconnect_all_clients()

    @s.on("lol")
    def lolol(clt_info, dict_stuff):
        print(
            f"Cool, {clt_info['ip']} sent out: {dict_stuff}. What's cool is that I am {dict_stuff['I am']}"
        )

    # @s.on("message")
    # def why(client_data, message: str):
    #     print("Message reserved function aaa")
    #     print("Client data:", client_data)
    #     print("Message:", message)

    @s.on("Sussus")
    def a(_, msg):  # _ actually is clt_data
        s.send_all_clients("pog", msg)

    while not s.closed:
        s.run()
