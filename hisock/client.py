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

import builtins  # Builtins, to convert string methods into builtins
import inspect  # Inspect, for type-hinting detection
import re  # regex, to make sure that arguments are correct
import socket  # socket, because.... bruh
import json  # json, to communicate to server (without 10000 commands)
import errno  # errno, to communicate to server
import sys  # sys
import threading  # threading, for ThreadedHiSockClient
import traceback  # traceback, for... tracebacks
from ipaddress import IPv4Address  # ipaddress, for comparisons between IPs

from typing import Union, Callable, Any

# Utilities
try:
    # use relative import for pip builds (required)
    from .utils import (
        make_header,
        _removeprefix,
        ServerNotRunning,
        ClientDisconnected,
        iptup_to_str,
    )
except ImportError:
    # relative import doesn't work for non-pip builds
    from utils import (
        make_header,
        _removeprefix,
        ServerNotRunning,
        ClientDisconnected,
        iptup_to_str,
    )


# ░█████╗░░█████╗░██╗░░░██╗████████╗██╗░█████╗░███╗░░██╗██╗
# ██╔══██╗██╔══██╗██║░░░██║╚══██╔══╝██║██╔══██╗████╗░██║██║
# ██║░░╚═╝███████║██║░░░██║░░░██║░░░██║██║░░██║██╔██╗██║██║
# ██║░░██╗██╔══██║██║░░░██║░░░██║░░░██║██║░░██║██║╚████║╚═╝
# ╚█████╔╝██║░░██║╚██████╔╝░░░██║░░░██║╚█████╔╝██║░╚███║██╗
# ░╚════╝░╚═╝░░╚═╝░╚═════╝░░░░╚═╝░░░╚═╝░╚════╝░╚═╝░░╚══╝╚═╝
#      Change the above code IF and only IF you know
#                  what you are doing!


class HiSockClient:
    """
    The client class for hisock.
    HiSockClient offers a higher-level version of sockets. No need to worry about headers now, yay!
    HiSockClient also utilizes decorators to receive messages, as an easy way of organizing your
    code structure (methods are provided, like :func:`recv_raw`, of course)

    :param addr: A two-element tuple, containing the IP address and the
        port number of the server wishing to connect to
        Only IPv4 currently supported
    :type addr: tuple
    :param name: Either a string or NoneType, representing the name the client
        goes by. Having a name provides an easy interface of sending
        data to a specific client and identifying clients. It is therefore
        highly recommended to pass in a name

        Pass in NoneType for no name (`connect` should handle that)
    :type name: str, optional
    :param group: Either a string or NoneType, representing the group the client
        is in. Being in a group provides an easy interface of sending
        data to multiple specific clients, and identifying multiple clients.
        It is highly recommended to provide a group for complex servers

        Pass in NoneType for no group (`connect` should handle that)
    :type group: str, optional
    :param blocking: A boolean, set to whether the client should block the loop
        while waiting for message or not.
        Default sets to True
    :type blocking: bool, optional
    :param header_len: An integer, defining the header length of every message.
        A smaller header length would mean a smaller maximum message
        length (about 10**header_len).
        The header length MUST be the same as the server connecting, or it will
        crash (hard to debug though).
        Default sets to 16 (maximum length of content: 10 quadrillion bytes)
    :type header_len: int, optional

    :ivar tuple addr: A two-element tuple, containing the IP address and the
        port number
    :ivar int header_len: An integer, storing the header length of each "message"
    :ivar str name: A string, representing the name of the client to identify by.
        Defaults to None
    :ivar str group: A string, representing the group of the client to identify by.
        Defaults to None
    :ivar dict funcs: A list of functions registered with decorator :meth:`on`.

        .. warning::

           This is mainly used for under-the-hood-code, so it is **NOT** recommended
           to be used in production-ready code
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
        # Function and cache storage
        self.funcs = {}
        self.cache_size = cache_size
        if cache_size >= 0:
            # cache_size <= -1: No cache
            self.cache = []

        # TLS arguments
        self.tls_arguments = {"tls": False}  # If TLS is false, then no TLS

        # Info for socket
        self.addr = addr
        self.name = name
        self.group = group
        self.header_len = header_len

        # Flags
        self._closed = False

        # Remember to update them as more rev funcs are added
        self.reserved_functions = ["client_connect", "client_disconnect"]

        # TLS stuff (soon to be added)
        self.tls = self._TLS(self)
        self.tls_arguments = {"tls": False}
        self.called_update = False

        # Socket intialization
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect(self.addr)
        except ConnectionRefusedError:
            # Server not running
            raise ServerNotRunning(
                "Server is not running! Aborting..."
            ) from ConnectionRefusedError

        self.sock.setblocking(blocking)

        # Send client hello
        hello_dict = {"name": self.name, "group": self.group}
        conn_header = make_header(
            f"$CLTHELLO$ {json.dumps(hello_dict)}", self.header_len
        )

        self.sock.send(conn_header + f"$CLTHELLO$ {json.dumps(hello_dict)}".encode())

    def __str__(self):
        """Example: <HiSockClient connected to 192.168.1.133:33333"""
        return f"<HiSockClient connected to {iptup_to_str(self.addr)}>"

    def __gt__(self, other: Union[HiSockClient, str]):
        """Example: HiSockClient(...) > '192.168.1.131'"""
        if type(other) not in [HiSockClient, str]:
            raise TypeError("Type not supported for > comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) > IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of ports

        return IPv4Address(self.addr[0]) > IPv4Address(ip[0])

    def __ge__(self, other: Union[HiSockClient, str]):
        """Example: HiSockClient(...) >= '192.168.1.131'"""
        if type(other) not in [HiSockClient, str]:
            raise TypeError("Type not supported for >= comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) >= IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of ports

        return IPv4Address(self.addr[0]) >= IPv4Address(ip[0])

    def __lt__(self, other: Union[HiSockClient, str]):
        """Example: HiSockClient(...) < '192.168.1.131'"""
        if type(other) not in [HiSockClient, str]:
            raise TypeError("Type not supported for < comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) < IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of ports

        return IPv4Address(self.addr[0]) < IPv4Address(ip[0])

    def __le__(self, other: Union[HiSockClient, str]):
        """Example: HiSockClient(...) <= '192.168.1.131'"""
        if type(other) not in [HiSockClient, str]:
            raise TypeError("Type not supported for <= comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) <= IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of ports

        return IPv4Address(self.addr[0]) <= IPv4Address(ip[0])

    def __eq__(self, other: Union[HiSockClient, str]):
        """Example: HiSockClient(...) == '192.168.1.131'"""
        if type(other) not in [HiSockClient, str]:
            raise TypeError("Type not supported for == comparison")
        if isinstance(other, HiSockClient):
            return IPv4Address(self.addr[0]) == IPv4Address(other.addr[0])
        ip = other.split(":")  # Gets rid of ports

        return IPv4Address(self.addr[0]) == IPv4Address(ip[0])

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

        def enable(self, rsa_privkey_filepath=".privkey", suite="default"):
            # TLS NOT ADDED CURRENTLY; NOT PRIORITY
            if not self.outer.called_update:
                self.outer.tls_arguments = {
                    "tls": True,
                    "rsa_privkey_filepath": rsa_privkey_filepath,
                    "suite": suite,
                }

                dh_num_header = make_header("$DH_NUMS$", self.outer.header_len)
                self.outer.sock.send(dh_num_header + b"$DH_NUMS$")
                dh_info = self.outer.recv_raw()
                print("E", dh_info)

                if dh_info == b"$NOTLS$":
                    raise TypeError("Server has not enabled TLS")
            else:
                raise TypeError("TLS attempted to enable after `update` called")

    def update(self):
        """
        Handles newly received messages, excluding the received messages for `wait_recv`
        This method must be called every iteration of a while loop, as to not lose valuable info.
        In some cases, it is recommended to run this in a thread, as to not block the
        program
        """
        self.called_update = True  # I forgot what this does

        if not self._closed:  # Checks if client hasn't been closed with `close`
            try:
                while True:
                    # Receives header - If doesn't exist, server error
                    try:
                        content_header = self.sock.recv(self.header_len)
                    except ConnectionResetError:
                        # Raise ServerNotRunning exception FROM ConnectionResetError
                        raise ServerNotRunning(
                            "Server has stopped running, aborting..."
                        ) from ConnectionResetError

                    if not content_header:
                        # Most likely server error; aborts
                        print(
                            "[SERVER] Connection forcibly closed by server, exiting..."
                        )
                        raise SystemExit
                    content = self.sock.recv(int(content_header.decode()))

                    for matching in self.funcs.keys():
                        if re.search(r"\$.+\$", matching):
                            raise ValueError(
                                'The format "$command$" is used for reserved functions - '
                                "Consider using a different format\n"
                                f'(Found with function "{matching}"'
                            )

                    # Handle "reserved functions"
                    if content == b"$DISCONN$":
                        self.close()

                        if "force_disconnect" in self.funcs:
                            self.funcs["force_disconnect"]["func"]()
                    if (
                        content.startswith(b"$CLTCONN$")
                        and "client_connect" in self.funcs
                    ):
                        # Client connected to server; parse and call function
                        clt_content = json.loads(_removeprefix(content, b"$CLTCONN$ "))
                        self.funcs["client_connect"]["func"](clt_content)
                    elif (
                        content.startswith(b"$CLTDISCONN$")
                        and "client_disconnect" in self.funcs
                    ):
                        # Client disconnected from server; parse and call function
                        clt_content = json.loads(
                            _removeprefix(content, b"$CLTDISCONN$ ")
                        )
                        self.funcs["client_disconnect"]["func"](clt_content)

                    for matching_cmd, func in self.funcs.items():
                        # Loop through functions and binded commands
                        if (
                            content.startswith(matching_cmd.encode())
                            and matching_cmd not in self.reserved_functions
                        ):
                            parse_content = content[len(matching_cmd) + 1 :]

                            # Type Hint -> Type Cast
                            # (Exceptions need to have "From ValueError")
                            if func["type_hint"] == str:
                                # bytes -> str
                                try:
                                    parse_content = parse_content.decode()
                                except UnicodeDecodeError as e:
                                    raise TypeError(
                                        f"Type casting from bytes to string failed "
                                        f"for function \"{func['name']}\":\n           {e}"
                                    ) from ValueError
                            elif func["type_hint"] == int:
                                # bytes -> int
                                try:
                                    parse_content = int(parse_content)
                                except ValueError as e:
                                    raise TypeError(
                                        f"Type casting from bytes to int "
                                        f"failed for function \"{func['name']}\":\n           {e}"
                                    ) from ValueError
                            elif func["type_hint"] == float:
                                # bytes -> float
                                try:
                                    parse_content = float(parse_content)
                                except ValueError as e:
                                    raise TypeError(
                                        f"Type casting from bytes to float "
                                        f"failed for function \"{func['name']}\":\n           {e}"
                                    ) from ValueError

                            for _type in [list, dict]:
                                if func["type_hint"] == _type:
                                    try:
                                        parse_content = json.loads(parse_content)
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

                            # Call function
                            func["func"](parse_content)

                    # Caching
                    if self.cache_size >= 0:
                        self.cache.append(
                            {"header": content_header, "content": content}
                        )

                        if 0 < self.cache_size < len(self.cache):
                            self.cache.pop(0)

            except IOError as e:
                # Normal, means message has ended
                if (
                    e.errno != errno.EAGAIN
                    and e.errno != errno.EWOULDBLOCK
                    and not self._closed
                ):
                    # Fatal Error, abort client (print exception, print log, exit python)
                    traceback.print_exception(
                        type(e), e, e.__traceback__, file=sys.stderr
                    )
                    print(
                        "\nServer Error encountered, aborting client...",
                        file=sys.stderr,
                    )
                    self.close()

                    raise SystemExit

    class _on:
        """Decorator used to handle something when receiving command"""

        def __init__(self, outer: Any, command: str):
            # `outer` arg is for the HiSockClient instance
            # `cmd_activation` is the command... on activation (WOW)
            self.outer = outer
            self.command = command

        def __call__(self, func: Callable):
            """Adds a function that gets called when the client receives a matching command"""

            # Checks for illegal $cmd$ notation (used for reserved functions)
            if re.search(r"\$.+\$", self.command):
                raise ValueError(
                    'The format "$command$" is used for reserved functions - '
                    "Consider using a different format"
                )
            # Gets annotations of function
            annots = inspect.getfullargspec(func).annotations
            func_args = inspect.getfullargspec(func).args

            try:
                # Try to map first arg (client data)
                # Into type hint compliant one
                msg_annotation = annots[func_args[0]]
                if isinstance(msg_annotation, str):
                    msg_annotation = builtins.__dict__[annots[func_args[0]]]
            except KeyError:
                # builtins is not what we thought; I dunno why I did this
                msg_annotation = None
            except IndexError:
                msg_annotation = None

            # Creates function dictionary to add to `outer.funcs`
            func_dict = {
                "func": func,  # Function
                "name": func.__name__,  # Function name
                "type_hint": msg_annotation,  # All function type hints
            }
            self.outer.funcs[self.command] = func_dict

            # Returns the inner function, like a decorator
            return func

    def on(self, command: str):
        """
        A decorator that adds a function that gets called when the client
        receives a matching command

        Reserved functions are functions that get activated on
        specific events. Currently, there are 2 for HiSockClient:

        1. client_connect - Activated when a client connects to the server

        2. client_disconnect - Activated when a client disconnects from the server

        The parameters of the function depend on the command to listen.
        For example, reserved functions `client_connect` and
        `client_disconnect` gets the client's data passed in as an argument.
        All other nonreserved functions get the message passed in.

        In addition, certain type casting is available to nonreserved functions.
        That means, that, using type hints, you can automatically convert
        between needed instances. The type casting currently supports:

        1. bytes -> int (Will raise exception if bytes is not numerical)

        2. bytes -> float (Will raise exception if bytes is not numerical)

        3. bytes -> str (Will raise exception if there's a unicode error)

        Type casting for reserved commands is scheduled to be
        implemented, and is currently being worked on.

        :param command: A string, representing the command the function should activate
            when receiving it
        :type command: str

        :return: The same function
            (The decorator just appended the function to a stack
        :rtype: function
        """
        # Passes in outer to _on decorator/class
        return self._on(self, command)

    def send(self, command: str, content: bytes):
        """
        Sends a command & content to the server, where it will be interpreted

        :param command: A string, containing the command to send
        :type command: str
        :param content: A bytes-like object, with the content/message
            to send
        :type content: bytes
        """
        # Creates header and sends to server
        if re.search(r"\$.+\$", command):
            raise TypeError(
                'Command format "$command$" is used for reserved functions - '
                "consider using a different command"
            )
        content_header = make_header(command.encode() + b" " + content, self.header_len)

        # Sends to server
        self.sock.send(content_header + command.encode() + b" " + content)

    def raw_send(self, content: bytes):
        """
        Sends a message to the server: NO COMMAND REQUIRED.
        This is preferable in some situations, where clients need to send
        multiple data over the server, without overcomplicating it with commands

        :param content: A bytes-like object, with the content/message
            to send
        :type content: bytes
        """
        # Creates header and send content to server, but no command
        if re.search(b"^\$.+\$", content):
            raise TypeError(
                'Command format "$command$" is used for reserved functions - '
                "consider not sending a message starting with $command$"
            )

        # Send to server
        header = make_header(content, self.header_len)
        self.sock.send(header + content)

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
        :type new_name: Union[str, None]
        """
        if new_name is not None:
            new_name_header = make_header(
                b"$CHNAME$ " + new_name.encode(), self.header_len
            )
        else:
            new_name_header = make_header(b"$CHNAME$", self.header_len)

        # Send name change to server
        self.sock.send(
            new_name_header + (b"$CHNAME$ " + new_name.encode())
            if new_name is not None
            else b"$CHNAME$"
        )

    def change_group(self, new_group: Union[str, None]):
        """
        Changes the client's group

        :param new_group: The new graup name of the client
        :type new_group: Union[str, None]
        """
        if new_group is not None:
            new_group_header = make_header(
                b"$CHGROUP$ " + new_group.encode(), self.header_len
            )
        else:
            new_group_header = make_header(b"$CHGROUP$", self.header_len)

        self.sock.send(
            new_group_header + (b"$CHGROUP$ " + new_group.encode())
            if new_group is not None
            else b"$CHGROUP$"
        )

    def get_cache(self, idx: Union[int, slice, None] = None):
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

    def get_server_addr(self):
        """
        Gets the address of where the hisock client is connected
        at.

        :return: A tuple, with the format (str IP, int port)
        :rtype: tuple[str, int]
        """
        return self.addr

    def get_client_addr(self):
        """
        Gets the address of the hisock client that is connected
        to the server.

        :return: A tuple, with the format (str IP, int port)
        :rtype: tuple[str, int]
        """
        return self.sock.getsockname()

    def close(self):
        """Closes the client; running `client.update()` won't do anything now"""
        # Changes _closed flag to True to prevent
        # `update` being crazy
        self._closed = True
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

    def run(self):
        """
        The main while loop to run the thread

        Refer to :class:`HiSockClient` for more details

        .. warning::
           This method is **NOT** recommended to be used in an actual
           production enviroment. This is used internally for the thread, and should
           not be interacted with the user
        """
        while self._stop_event:
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

    :param addr: A two-element tuple, containing the IP address and
        the port number
    :type addr: tuple
    :param name: A string, containing the name of what the client should go by.
        This argument is optional
    :type name: str, optional
    :param group: A string, containing the "group" the client is in.
        Groups can be utilized to send specific messages to them only.
        This argument is optional
    :type group: str, optional
    :param blocking: A boolean, specifying if the client should block or not
        in the socket.

        Defaults to True
    :type blocking: bool, optional
    :param header_len: An integer, defining the header length of every message.

        Defaults to True
    :type header_len: int, optional

    :return: A :class:`HiSockClient` instance
    :rtype: instance
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
    s = threaded_connect(
        ("192.168.1.131", 33333), name="Sussus", group="Amogus", cache_size=5
    )
    s.change_name("Burp")

    @s.on("Joe")
    def hehe(_):
        print(
            "This message was sent from server after client connection\n"
            "(Sent to every client)"
        )
        s.send("Sussus", b"Some random msg I guess")

    @s.on("pog")
    def eee(msg):
        print("Follow up message sent by server\n" "(Also sent to every client)")
        print("Message:", msg)

    @s.on("client_connect")
    def please(data):
        print(f"Client {':'.join(map(str, data['ip']))} connected :)")

    @s.on("client_disconnect")
    def haha_bois(disconn_data):
        print(f"Aww man, {':'.join(map(str, disconn_data['ip']))} disconnected :(")

    @s.on("Test")
    def test(data):
        print("Group message received:", data)
        print(s.get_cache(slice(1, 3)))

    @s.on("force_disconnect")
    def susmogus():
        print("AAAAAAAAA DISCONNECTED :(((((((")

    s.start_client()
