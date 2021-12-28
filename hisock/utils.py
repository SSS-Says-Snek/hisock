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
import re
import socket
from typing import Union, Any
from ipaddress import IPv4Address

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


# Custom warnings
class NoHeaderWarning(Warning):
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


class File:
    def __init__(self, file_path: Union[str, pathlib.Path]):
        # TODO: implement this!
        self.file_path = file_path


def make_header(
    header_msg: Union[str, bytes], header_len: int, encode=True
) -> Union[str, bytes]:
    """
    Makes a header of ``header_msg``, with a maximum
    header length of ``header_len``

    :param header_msg: A string OR bytes-like object, representing
        the data to make a header from
    :type header_msg: Union[str, bytes]
    :param header_len: An integer, specifying
        the actual header length (will be padded)
    :type header_len: int
    :param encode: A boolean, specifying the
    :return: The constructed header, padded to ``header_len``
        bytes
    :rtype: Union[str, bytes]
    """

    msg_len = len(header_msg)
    constructed_header = f"{msg_len}{' ' * (header_len - len(str(msg_len)))}"
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
    :rtype: dict["header": bytes, "data": bytes]
    """
    try:
        header_msg = connection.recv(header_len)

        if header_msg:
            msg_len = int(header_msg)
            data = connection.recv(msg_len)

            return {"header": header_msg, "data": data}
        return False
    except ConnectionResetError:
        # This is most likely where clients will disconnect
        pass


def _removeprefix(
    string: Union[str, bytes],
    prefix: Union[str, bytes],
) -> Union[str, bytes]:
    """A backwards-compatible alternative of str.removeprefix"""
    if string.startswith(prefix):
        return string[len(prefix) :]
    else:
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
        elif isinstance(idx_to_match, int):
            if multikey == key[idx_to_match]:
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


def _type_cast(type_cast: Any, content_to_typecast: bytes, func_dict: dict) -> Any:
    """
    Basis for type casting on the server
    If testing, replace `func_dict` with a dummy one
    Currently NOT guranteed to return, please remember to change this API
    """
    # TODO: refactor
    if type_cast == bytes:
        return content_to_typecast
    if type_cast == str:
        try:
            typecasted_content = content_to_typecast.decode()
            return typecasted_content  # Remember to change this, but I'm lazy!
        except UnicodeDecodeError as e:
            raise TypeError(
                f"Type casting from bytes to string failed for function "
                f"\"{func_dict['name']}\"\n{str(e)}"
            )
    elif type_cast == int:
        try:
            typecasted_content = int(content_to_typecast)
            return typecasted_content  # Remember to change this, but I'm lazy!
        except ValueError as e:
            raise TypeError(
                f"Type casting from bytes to int failed for function "
                f"\"{func_dict['name']}\":\n           {e}"
            ) from ValueError
    elif type_cast == float:
        try:
            typecasted_content = float(content_to_typecast)
            return typecasted_content  # Remember to change this, but I'm lazy!
        except ValueError as e:
            raise TypeError(
                f"Type casting from bytes to float failed for function "
                f"\"{func_dict['name']}\":\n           {e}"
            ) from ValueError
    elif type_cast is None:
        return content_to_typecast
    for _type in [list, dict]:
        if type_cast == _type:
            try:
                typecasted_content = json.loads(content_to_typecast)
                return typecasted_content
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
                    f"failed for function \"{func_dict['name']}\""
                    f":\n           Message is not a {_type.__name__}"
                ) from ValueError
            except Exception as e:
                raise TypeError(
                    f"Type casting from bytes to {_type.__name__} "
                    f"failed for function \"{func_dict['name']}\""
                    f":\n           {e}"
                ) from type(e)


def validate_ipv4(
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
    :return: If the address is valid
    :rtype: bool
    :raise ValueError: IP address is not valid
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

    if len(deconstructed_ip) == 0:
        raise ValueError("IP address is empty")

    # Port checking
    if require_port:
        port = deconstructed_ip[-1]
        if not port.isdigit():
            raise ValueError(f"Port must be a number, not {port}")

        elif int(port) < 0 or int(port) > 65535:
            raise ValueError(f"{port} is not a valid port (0-65535)")
        else:
            if not require_ip:
                return True

    # IP checking
    ip = deconstructed_ip[0]
    try:
        ip = IPv4Address(ip)
    except ValueError:
        raise ValueError(f"{ip} is not a valid IPv4 address")


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
    else:
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
    except Exception as error:
        print(f"\033[91mInvalid IP: {error}\033[0m\n")
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
    except ValueError as error:
        print(f"\033[91mInvalid port: {error}\033[0m\n")
        return _input_port(question)
    return port


def input_server_config(
    ip_prompt: str = "Enter the IP of for the server: ",
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

    return (_input_ip_address(ip_prompt), _input_port(port_prompt))


def input_client_config(
    ip_prompt: str = "Enter the IP of the server: ",
    port_prompt: str = "Enter the port of the server: ",
    name_prompt: Union[str, None] = "Enter name: ",
    group_prompt: Union[str, None] = "Enter group to connect to: ",
) -> tuple[Union[str, int], ...]:
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

    return tuple(filter(None, (ip, port, name, group)))


def ipstr_to_tup(formatted_ip: str) -> tuple[str, int]:
    """
    Converts a string IP address into a tuple equivalent

    :param formatted_ip: A string, representing the IP address.

        Must be in the format "ip:port"
    :type formatted_ip: str

    :return: A tuple, with IP address as the first element, and
        an INTEGER port as the second element
    :rtype: tuple[str, int]
    """
    ip_split = formatted_ip.split(":")
    recon_ip_split = [str(ip_split[0]), int(ip_split[1])]
    return tuple(recon_ip_split)  # Convert list to tuple


def iptup_to_str(formatted_tuple: tuple[str, int]) -> str:
    """
    Converts a tuple IP address into a string equivalent

    This function is like the opposite of ``ipstr_to_tup``

    :param formatted_tuple: A two-element tuple, containing the IP address and the port.
        Must be in the format (ip: str, port: int)
    :type formatted_tuple: tuple[str, int]

    :return: A string, with the format "ip:port"
    :rtype: str
    """
    return f"{formatted_tuple[0]}:{formatted_tuple[1]}"
