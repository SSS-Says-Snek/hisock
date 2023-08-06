"""
This module contains several function to either:
1. Help server.py and client.py under-the-hood
2. Help the user by providing them with some built-in functions

Generally, functions starting with an underscore (_) will be
under-the-hood, while the rest are user functions

====================================
Copyright SSS_Says_Snek, 2021-present
====================================
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from ipaddress import IPv4Address
from re import search
from typing import List, Dict, Optional, Type, Union  # Must use these for bare annots


# Custom exceptions
class ClientException(Exception):
    pass


class ServerException(Exception):
    pass


class NoMessageException(Exception):
    pass


class InvalidTypeCast(Exception):
    pass


class ServerNotRunning(Exception):
    pass


class ClientDisconnected(Exception):
    pass


class FunctionNotFoundException(Exception):
    pass


class ClientNotFound(Exception):
    pass


class GroupNotFound(Exception):
    pass


# Custom warnings
class NoHeaderWarning(UserWarning):
    pass


class FunctionNotFoundWarning(UserWarning):
    pass


# Custom classes
class _Sentinel:
    pass


class MessageCacheMember:
    _available_attrs = ["header", "content", "called", "command"]

    def __init__(self, message_dict: dict):
        self.header = message_dict.get("header", _Sentinel)
        self.content = message_dict.get("content", _Sentinel)
        self.called = message_dict.get("called", _Sentinel)
        self.command = message_dict.get("command", _Sentinel)

        for key, values in dict(self.__dict__).items():
            if values is _Sentinel:
                del self.__dict__[key]

    def __str__(self):
        return f"<MessageCacheMember: {self.content}>"

    def __repr__(self):
        return self.__str__()


@dataclass(frozen=True)
class ClientInfo:
    """
    The dataclass used to represent a client.
    """

    ip: Optional[tuple[str, int]]
    name: Optional[str] = None
    group: Optional[str] = None

    @classmethod
    def from_dict(cls, dict_: dict) -> "ClientInfo":
        """
        Creates a new ``ClientInfo`` instance given a dictionary. The dictionary should have the keys
        ``ip``, ``name``, and ``group``.

        :param dict_: Dictionary that represents a new ``ClientInfo`` to be created from.
        :type dict_: dict

        :return: a new instance of ``ClientInfo``.
        :rtype: ClientInfo
        """

        return cls(dict_["ip"], dict_["name"], dict_["group"])

    @property
    def ipstr(self) -> str:
        """A stringified version of ``self.ip``. Is equivalent to ``f"{self.ip[0]}:{self.ip[1]}``."""
        return f"{self.ip[0]}:{self.ip[1]}"

    def as_dict(self) -> dict:
        """
        Returns a dictionary represented by the ``ClientInfo``. The dictionary will have the keys
        ``ip``, ``name``, ``group``, and ``ipstr``.

        :return: A dictionary representing ``ClientInfo``.
        :rtype: dict
        """
        return {"ip": self.ip, "name": self.name, "group": self.group, "ipstr": self.ipstr}

    def copy(self):
        """
        Returns a copy of the current ``ClientInfo``.

        :return: A copy of the current ``ClientInfo``.
        :rtype: ClientInfo
        """

        return type(self)(self.ip, self.name, self.group)

    def __str__(self):
        return f"<ClientInfo: IP: {self.ipstr}, Name: {self.name}, Group: {self.group}>"

    def __eq__(self, other: ClientInfo):
        return (self.ip, self.name, self.group) == (other.ip, other.name, other.group)


# Custom type hints
Sendable = Union[
    bytes,
    str,
    int,
    float,
    None,
    ClientInfo,
    List["Sendable"],
    Dict[
        Union[bytes, str, int, float, None, ClientInfo],
        "Sendable",
    ],
]
SendableTypes = Type[Sendable]


def make_header(header_message: Union[str, bytes], header_len: int, encode=True) -> Union[str, bytes]:
    """
    Makes a header of ``header_message``, with a maximum
    header length of ``header_len``

    :param header_message: A string OR bytes-like object, representing
        the data to make a header from
    :type header_message: Union[str, bytes]
    :param header_len: An integer, specifying
        the actual header length (will be padded)
    :type header_len: int
    :param encode: A boolean, specifying the
    :return: The constructed header, padded to ``header_len``
        bytes
    :rtype: Union[str, bytes]
    """

    message_len = len(header_message)
    constructed_header = f"{message_len}{' ' * (header_len - len(str(message_len)))}"
    if encode:
        return constructed_header.encode()
    return constructed_header


def _recv_exactly(connection: socket.socket, length: int, buffer_size: int) -> Optional[bytes]:
    data = b""
    bytes_left = length

    while bytes_left > 0:
        bytes_to_recv = min(bytes_left, buffer_size)
        data_part = connection.recv(bytes_to_recv)
        if not data_part:
            data = None
            break

        data += data_part
        bytes_left -= len(data_part)

    return data


def receive_message(connection: socket.socket, header_len: int, buffer_size: int) -> Union[dict[str, bytes], bool]:
    """
    Receives a message from a server or client.

    :param connection: The socket to listen to for messages.
        **MUST BE A SOCKET**
    :type connection: socket.socket
    :param header_len: The length of the header, so that
        it can successfully retrieve data without loss/gain of data
    :type header_len: int
    :return: A dictionary, with two key-value pairs;
        The first key-value pair refers to the header,
        while the second one refers to the actual data
    :rtype: Union[dict["header": bytes, "data": bytes], False
    """

    try:
        header_message = _recv_exactly(connection, header_len, 16)  # Header's super tiny
        if header_message is not None:
            message_len = int(header_message)

            data = _recv_exactly(connection, message_len, buffer_size)

            return {"header": header_message, "data": data}
    except ConnectionResetError:
        # This is most likely where clients will disconnect
        pass
    return False


def _removeprefix(
    string: Union[str, bytes],
    prefix: Union[str, bytes],
) -> Union[str, bytes]:
    """A backwards-compatible alternative of str.removeprefix"""

    if string.startswith(prefix):
        return string[len(prefix) :]
    return string[:]


def validate_command_not_reserved(command: str):
    """
    Checks for illegal $cmd$ notation (used for reserved functions).

    :param command: The command to check.
    :type command: str

    :raises ValueError: If the command is reserved.
    """

    if search(r"\$.+\$", command):
        raise ValueError(
            'The format "$command$" is used for reserved functions - ' "consider using a different format."
        )


def validate_ipv4(  # NOSONAR (always will return True, but will raise exceptions)
    ip: Union[str, tuple], require_ip: bool = True, require_port: bool = True
) -> bool:
    """
    Validates an IPv4 address.
    If the address isn't valid, it will raise an exception.
    Otherwise, it'll return True

    :param ip: The IPv4 address to validate.
    :type ip: Union[str, tuple]
    :param require_ip: Whether or not to require an IP address.
        If True, it will raise an exception if no IP address is given.
        If False, this will only check the port.
    :type require_ip: bool
    :param require_port: Whether or not to require a port to be specified.
        If True, it will raise an exception if no port is specified.
        If False, it will return the address as a tuple without a port.
    :type require_port: bool
    :return: True if there were no exceptions.
    :rtype: Literal["True"]

    :raises ValueError: IP address is not valid
    """

    if not (require_ip or require_port):
        return True  # There's nothing to check!

    deconstructed_ip = None
    if isinstance(ip, str):
        if not require_ip or not require_port:
            deconstructed_ip = (ip,)
        else:
            deconstructed_ip = ipstr_to_tup(ip)
    elif isinstance(ip, tuple):
        deconstructed_ip = ip

    if deconstructed_ip is None or len(deconstructed_ip) == 0:
        raise ValueError("IP address is empty")

    # Port checking
    if require_port:
        port = deconstructed_ip[-1]
        if isinstance(port, str) and not port.isdigit():
            raise ValueError(f"Port must be a number, not {port}")
        if int(port) < 0 or int(port) > 65535:
            raise ValueError(f"{port} is not a valid port (0-65535)")
        if not require_ip:
            return True

    # IP checking
    ip = deconstructed_ip[0]
    try:
        IPv4Address(ip)
    except ValueError:
        raise ValueError(f"{ip} is not a valid IPv4 address") from None

    return True


def get_local_ip(all_ips: bool = False) -> str:
    """
    Gets the local IP of your device, with sockets

    :param all_ips: A boolean, specifying to return all the
        local IPs or not. If set to False (the default), it will return
        the local IP first found by ``socket.gethostbyname()``

        Default: False
    :type all_ips: bool, optional
    :return: A string containing the IP address, in the
        format "ip:port"
    :rtype: str
    """

    if not all_ips:
        return socket.gethostbyname(socket.gethostname())

    return socket.gethostbyname_ex(socket.gethostname())[-1]


def _input_ip_address(question: str) -> str:
    """
    Asks the user to input an IP address. Returns the address as a string
    when it is valid.

    :param question: The question to ask the user.
    :type question: str
    :return: A valid IPv4 address.
    :rtype: str
    """

    ip_address = input(question)
    try:
        validate_ipv4(ip_address, require_port=False)
    except ValueError as e:
        print(f"\033[91mInvalid IP: {e}\033[0m\n")
        return _input_ip_address(question)
    return ip_address


def _input_port(question: str) -> int:
    """
    Asks the user to enter a port. Returns the port as an integer when it
    is valid.

    :param question: The question to ask the user.
    :type question: str
    :return: A valid port.
    :rtype: int
    """

    port = input(question)
    try:
        validate_ipv4(port, require_ip=False)
    except (TypeError, ValueError) as e:
        print(f"\033[91mInvalid port: {e}\033[0m\n")
        return _input_port(question)
    return int(port)


def input_server_config(
    ip_prompt: str = "Enter the IP for the server: ",
    port_prompt: str = "Enter the port for the server: ",
) -> tuple[str, int]:
    """
    Provides a built-in way to obtain the IP and port of where the server
    should be hosted, through :func:`input`.

    :param ip_prompt: A string, specifying the prompt to show when
        asking for IP.
    :type ip_prompt: str, optional
    :param port_prompt: A string, specifying the prompt to show when
        asking for port
    :type port_prompt: str, optional
    :return: A two-element tuple, consisting of IP and port.
    :rtype: tuple[str, int]
    """

    return _input_ip_address(ip_prompt), _input_port(port_prompt)


def input_client_config(
    ip_prompt: str = "Enter the IP of the server: ",
    port_prompt: str = "Enter the port of the server: ",
    name_prompt: Union[str, None] = "Enter name: ",
    group_prompt: Union[str, None] = "Enter group to connect to: ",
) -> tuple[tuple[str, int], Optional[str], Optional[str]]:
    """
    Provides a built-in way to obtain the IP and port of the configuration
    of the server to connect to.

    :param ip_prompt: A string, specifying the prompt to show when
        asking for IP.
    :type ip_prompt: str, optional
    :param port_prompt: A string, specifying the prompt to show when
        asking for port.
    :type port_prompt: str, optional
    :param name_prompt: A string, specifying the prompt to show when
        asking for client name.
    :type name_prompt: Union[str, None], optional
    :param group_prompt: A string, specifying the prompt to show when
        asking for client group.
    :type group_prompt: Union[str, None], optional
    :return: A tuple containing the config options of the server. Will
        filter out the unused options.
    :rtype: tuple[str, int, Optional[str], Optional[int]]
    """

    ip, port = _input_ip_address(ip_prompt), _input_port(port_prompt)
    name, group = None, None

    if name_prompt:
        name = input(name_prompt)
    if group_prompt:
        group = input(group_prompt)

    return tuple(filter(None, ((ip, port), name, group)))


def ipstr_to_tup(formatted_ip: str) -> tuple[str, int]:
    """
    Converts a string IP address into a tuple equivalent.

    :param formatted_ip: A string, representing the IP address.
        Must be in the format "ip:port".
    :type formatted_ip: str
    :return: A tuple, with a string IP address as the first element and
        an integer port as the second element.
    :rtype: tuple[str, int]

    :raises ValueError: If the IP address isn't in the "ip:port" format.
    """

    try:
        ip_split = formatted_ip.split(":")
        if len(ip_split) != 2:
            raise IndexError
        if len(ip_split[0].split(".")) != 4:
            raise IndexError
        if int(ip_split[1]) <= 0 or int(ip_split[1]) > 65535:
            raise IndexError

        recon_ip_split = (str(ip_split[0]), int(ip_split[1]))
        return recon_ip_split
    except IndexError:
        raise ValueError(f"{formatted_ip} is not a valid IP address") from None


def iptup_to_str(formatted_tuple: tuple[str, int]) -> str:
    """
    Converts a tuple IP address into a string equivalent.
    This function is the opposite of :func:`ipstr_to_tup`.

    :param formatted_tuple: A two-element tuple, containing the IP address and the port.
        Must be in the format (ip: str, port: int).
    :type formatted_tuple: tuple[str, int]
    :return: A string, with the format "ip:port".
    :rtype: str

    :raises ValueError: If the IP address isn't in the "ip:port" format.
    """

    try:
        return f"{formatted_tuple[0]}:{formatted_tuple[1]}"
    except IndexError:
        raise ValueError(f"{formatted_tuple} is not a valid IP address") from None
