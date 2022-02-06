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

import json
import pathlib
import socket
from typing import Union, Any, Optional, Type
from ipaddress import IPv4Address
from re import search
import builtins
import sys

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


class ClientInfo:
    def __init__(self, ip, name, group):
        self.ip: tuple[str, int] = tuple(
            ip
        )  # _type_cast converts tuple to list to be JSON-serializable
        self.name: Union[str, None] = name
        self.group: Union[str, None] = group

        self.client_dict: dict = {"ip": self.ip, "name": self.name, "group": self.group}
        self.ip_as_str: str = f"{self.ip[0]}:{self.ip[1]}"

    def __getitem__(self, item):
        return self.client_dict[item]

    def __str__(self):
        return f"<ClientInfo: IP: {self.ip_as_str}, Name: {self.name}, Group: {self.group}>"

    def __eq__(self, other: ClientInfo):
        return self.client_dict == other.client_dict


class File:
    def __init__(self, file_path: Union[str, pathlib.Path]):
        # TODO: implement this!
        self.file_path = file_path


# Custom type hints
Sendable = Union[
    bytes,
    str,
    int,
    float,
    None,
    ClientInfo,
    list[Union[str, int, float, bool, None, dict, list]],
    dict[
        Union[str, int, float, bool, None, dict, list],
        Union[str, int, float, bool, None, dict, list],
    ],
]

SendableTypes = Type[Sendable]

Client = Union[
    str,  # Name
    tuple[str, int],  # Port
    ClientInfo,  # Returned by function, etc
]


def make_header(
    header_message: Union[str, bytes], header_len: int, encode=True
) -> Union[str, bytes]:
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


def receive_message(
    connection: socket.socket, header_len: int
) -> Union[dict[str, bytes], bool]:
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
        header_message = connection.recv(header_len)
        if header_message:
            message_len = int(header_message)
            data = connection.recv(message_len)
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


def _dict_tupkey_lookup(
    multikey: Any, _dict: dict, idx_to_match: Union[int, None] = None
) -> Any:
    """
    Returns the value of the dict looked up,
    given a key that is part of a key-tuple
    """

    for key, value in _dict.items():
        if idx_to_match is None:
            if multikey in key:
                yield value
        elif isinstance(idx_to_match, int) and multikey == key[idx_to_match]:
            yield value


def _dict_tupkey_lookup_key(
    multikey: Any, _dict: dict, idx_to_match: Union[int, None] = None
) -> Any:
    """
    Returns the key of the dict looked up,
    given a key that is part of a key-tuple
    """

    for key in _dict.keys():
        if idx_to_match is None:
            if multikey in key:
                yield key
        elif isinstance(idx_to_match, int) and multikey == key[idx_to_match]:
            yield key


def _str_type_to_type_annotations_dict(annotations_dict: dict):
    """
    When getting the annotations, they return as a string representation of the type.
    However, we need the actual type.
    This function will take the annotations dict with the string type and turn it to
    the type.

    .. note::
        If the type hint is the type already (no conversion needed), this won't
        break anything.

    :param annotations_dict: The annotations dict to convert.
    :type annotations_dict: dict
    :return: The converted dict.
    :rtype: dict
    """

    fixed_annotations = {}
    for argument, annotation in annotations_dict.items():
        # This won't affect anything if the type is already the type
        # Also, `isinstance(str, str)` == False
        if not isinstance(annotation, str):
            fixed_annotations[argument] = annotation
            continue
        try:
            fixed_annotations[argument] = getattr(builtins, annotation)
        except AttributeError:
            fixed_annotations[argument] = getattr(sys.modules[__name__], annotation)
    return fixed_annotations


def _type_cast(
    type_cast: SendableTypes, content_to_type_cast: Sendable, func_name: str
) -> Sendable:
    """
    Type casts data to be sent.

    :param type_cast: The type to type cast to.
    :type type_cast: Sendable
    :param content_to_type_cast: The content to type cast. If it is not
        bytes, this function will attempt to convert it to bytes.
    :type content_to_type_cast: Sendable
    :param func_name: The name of the function that is calling this function.
        Used for exception messages.
    :type func_name: str
    :return: The type casted content (will be the same type as :param:`type_cast`).
    :rtype: Sendable

    :raises InvalidTypeCast: If the type cast is invalid.
    """

    if type_cast is None:
        return content_to_type_cast

    try:
        # Convert content_to_type_cast to bytes
        if not isinstance(content_to_type_cast, bytes):
            if isinstance(content_to_type_cast, str):
                content_to_type_cast = content_to_type_cast.encode()
            elif content_to_type_cast is None:
                content_to_type_cast = b""
            elif type(content_to_type_cast) in (int, float):
                content_to_type_cast = str(content_to_type_cast).encode()
            elif type(content_to_type_cast) in (list, dict):
                content_to_type_cast = json.dumps(content_to_type_cast).encode()
            else:
                raise TypeError(
                    f"Cannot type cast {type(content_to_type_cast)} to bytes"
                )

        # Type cast content_to_type_cast to type_cast
        if type_cast is bytes:
            return content_to_type_cast
        if type_cast is None:
            return None
        if type_cast in (str, int, float):
            # Handle no data
            if not content_to_type_cast:
                if type_cast is str:
                    return ""
                return type_cast(0)  # int or float

            try:
                ret = type_cast(content_to_type_cast.decode())
            except Exception as e:
                raise InvalidTypeCast(
                    f"Type casting from {type(content_to_type_cast).__name__} "
                    f"to {type_cast.__name__} failed for function "
                    f'"{func_name}:\n{e}"'
                ) from e

            return ret
        elif type_cast in (list, dict):
            # Handle no data
            if not content_to_type_cast:
                return {} if type_cast is dict else []

            result = json.loads(content_to_type_cast.decode())

            if not isinstance(result, type_cast):
                # json.loads works with dicts and lists, so the result could be ambiguous
                raise InvalidTypeCast()

            return result

        raise InvalidTypeCast(
            f"Cannot type cast bytes to {type(type_cast).__name__}."
            " See `HiSockServer.on` for available type hints."
        )

    except Exception as e:
        raise InvalidTypeCast(
            f"Type casting from {type(content_to_type_cast).__name__} "
            f"to {type_cast.__name__} failed for function "
            f'"{func_name}":\n{e}'
        ) from e


def validate_command_not_reserved(command: str):
    """
    Checks for illegal $cmd$ notation (used for reserved functions).

    :param command: The command to check.
    :type command: str

    :raises ValueError: If the command is reserved.
    """

    if search(r"\$.+\$", command):
        raise ValueError(
            'The format "$command$" is used for reserved functions - '
            "consider using a different format."
        )


def validate_ipv4(  # NOSONAR (always will return True, but will raise exceptions)
    ip: Union[str, tuple], require_ip: bool = True, require_port: bool = True
) -> bool:
    """
    Validates an IPv4 address.
    If the address isn't valid, it will raise an exception.
    Otherwise, it'll return True
    :param ip: The IPv4 address to validate.
    :param
    :param require_ip: Whether or not to require an IP address.
        If True, it will raise an exception if no IP address is given.
        If False, this will only check the port.
    :type require_ip: bool
    :param require_port: Whether or not to require a port to be specified.
        If True, it will raise an exception if no port is specified.
        If False, it will return the address as a tuple without a port.
    :type require_port: bool
    :return: If the address is valid
    :rtype: bool

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
        ip = IPv4Address(ip)
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

    :param question: The question to ask the user
    :type question: str
    :return: A valid IPv4 address
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

    :param question: The question to ask the user
    :type question: str
    :return: A valid port
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
    should be hosted, through :func:`input()`

    :param ip_prompt: A string, specifying the prompt to show when
        asking for IP.
    :type ip_prompt: str, optional
    :param port_prompt: A string, specifying the prompt to show when
        asking for Port
    :type port_prompt: str, optional
    :return: A two-element tuple, consisting of IP and Port
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
    of the server to connect to

    :param ip_prompt: A string, specifying the prompt to show when
        asking for IP.
    :type ip_prompt: str, optional
    :param port_prompt: A string, specifying the prompt to show when
        asking for port
    :type port_prompt: str, optional
    :param name_prompt: A string, specifying the prompt to show when
        asking for client name
    :type name_prompt: Union[str, None], optional
    :param group_prompt: A string, specifying the prompt to show when
        asking for client group
    :type group_prompt: Union[str, None], optional
    :return: A tuple containing the config options of the server
    :rtype: tuple[str, int, Optional[str], Optional[int]]
    """

    ip, port = _input_ip_address(ip_prompt), _input_port(port_prompt)
    name, group = None, None

    if name_prompt:
        name = input(name_prompt)
    if group_prompt:
        group = input(group_prompt)

    return (ip, port), name, group


def ipstr_to_tup(formatted_ip: str) -> tuple[str, int]:
    """
    Converts a string IP address into a tuple equivalent

    :param formatted_ip: A string, representing the IP address.
        Must be in the format "ip:port"
    :type formatted_ip: str
    :return: A tuple, with IP address as the first element, and
        an INTEGER port as the second element
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
    Converts a tuple IP address into a string equivalent

    This function is like the opposite of :func:`ipstr_to_tup`

    :param formatted_tuple: A two-element tuple, containing the IP address and the port.
        Must be in the format (ip: str, port: int)
    :type formatted_tuple: tuple[str, int]
    :return: A string, with the format "ip:port"
    :rtype: str

    :raises ValueError: If the IP address isn't in the "ip:port" format.
    """

    try:
        return f"{formatted_tuple[0]}:{formatted_tuple[1]}"
    except IndexError:
        raise ValueError(f"{formatted_tuple} is not a valid IP address") from None
