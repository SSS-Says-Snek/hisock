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
from typing import Union, Optional, Any


# __all__ = [
#     'make_header', 'receive_message',
#     'get_local_ip', 'ipstr_to_tup',
#     'iptup_to_str'
# ]


# Some custom exceptions
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


class MessageCacheMember:
    _available_attrs = [
        'header', 'content', 'called', 'command'
    ]

    def __init__(
            self, message_dict
    ):
        # I mean... that's it
        self.header = message_dict.get('header', None)
        self.content = message_dict.get('content', None)
        self.called = message_dict.get('called', None)
        self.command = message_dict.get('command', None)

        for key, values in dict(self.__dict__).items():
            if values is None:
                del self.__dict__[key]

    def __str__(self):
        return f"<MessageCacheMember: {self.__dict__['content']}>"


class File:
    def __init__(self, file: Union[str, pathlib.Path]):
        if isinstance(file, str):
            pass


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
    len_msg = len(header_msg)
    constructed_header = f"{len_msg}{' ' * (header_len - len(str(len_msg)))}"
    if encode:
        return constructed_header.encode()
    return constructed_header


def receive_message(connection: socket.socket, header_len: int) -> Union[dict[str, bytes], bool]:
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
        return string[len(prefix):]
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
        elif isinstance(idx_to_match, int):
            if multikey == key[idx_to_match]:
                yield key


def _type_cast(
        type_cast: Any, content_to_typecast: bytes, func_dict: dict
) -> Any:
    """
    Basis for type casting on the server
    If testing, replace `func_dict` with a dummy one
    Currently NOT guarenteed to return, please remember to change this API
    """
    if type_cast == bytes:
        return content_to_typecast
    if type_cast == str:
        try:
            typecasted_content = content_to_typecast.decode()
            return typecasted_content  # Remember to change this, but I"m lazy rn
        except UnicodeDecodeError as e:
            raise TypeError(
                f"Type casting from bytes to string failed for function "
                f"\"{func_dict['name']}\"\n{str(e)}"
            )
    elif type_cast == int:
        try:
            typecasted_content = int(content_to_typecast)
            return typecasted_content  # Remember to change this, but I"m lazy rn
        except ValueError as e:
            raise TypeError(
                f"Type casting from bytes to int failed for function "
                f"\"{func_dict['name']}\":\n           {e}"
            ) from ValueError
    elif type_cast == float:
        try:
            typecasted_content = float(content_to_typecast)
            return typecasted_content  # Remember to change this, but I"m lazy rn
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


def _parse_client_arg(client: Union[str, tuple]):
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
                f"Client tuple format should be ('ip.ip.ip.ip', port), not " f"{client}"
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
            raise ValueError("Port is not numerical (only IPv4 currently supported)")

        for subip in reconstructed_client[0]:
            if not 0 <= subip < 255:
                raise ValueError(f"{client} is not a valid IP address")
        if not 0 < reconstructed_client[1] < 65535:
            raise ValueError(f"{split_client[1]} is not a valid port (1-65535)")


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


def input_server_config(
        ip_prompt: str = "Enter the IP of where to host the server: ",
        port_prompt: str = "Enter the Port of where to host the server: ",
) -> tuple[str, int]:
    """
    Provides a built-in way to obtain the IP and port of where the server
    should be hosted, through :func:`input()`

    :param ip_prompt: A string, specifying the prompt to show when
        asking for IP.

        Default is "Enter the IP of where to host the server: "
    :type ip_prompt: str, optional
    :param port_prompt: A string, specifying the prompt to show when
        asking for Port

        Default is "Enter the Port of where to host the server: "
    :type port_prompt: str, optional
    :return: A two-element tuple, consisting of IP and Port
    :rtype: tuple[str, int]
    """

    # Flags
    ip_range_check = True

    ip = input(ip_prompt)

    if re.search(r"^((\d?){3}\.){3}(\d\d?\d?)[ ]*$", ip):
        # IP conformity regex
        split_ip = list(map(int, ip.split(".")))
        split_ip = [i > 255 for i in split_ip]

        if any(split_ip):
            ip_range_check = True

    while (
            ip == "" or not re.search(r"^((\d?){3}\.){3}(\d\d?\d?)[ ]*$", ip)
    ) or ip_range_check:
        # If IP not conform to regex, accept input until it
        # is compliant
        ip = input(f"\033[91mE: Invalid IP\033[0m\n{ip_prompt}")
        if re.search(r"^((\d?){3}\.){3}(\d\d?\d?)[ ]*$", ip):
            split_ip = list(map(int, ip.split(".")))
            split_ip = [i > 255 for i in split_ip]

            if not any(split_ip):
                ip_range_check = False

    port = input(port_prompt)

    while (port == "" or not port.isdigit()) or (port.isdigit() and int(port) > 65535):
        # If port is > 65535, or not numerical, repeat until it is
        port = input(f"\033[91mE: Invalid Port\033[0m\n{port_prompt}")
    port = int(port)

    # Returns
    return ip, port


def input_client_config(
        ip_prompt: str = "Enter the IP of the server: ",
        port_prompt: str = "Enter the Port of the server: ",
        name_prompt: Union[str, None] = "Enter name to connect as: ",
        group_prompt: Union[str, None] = "Enter group to connect to: ",
) -> tuple[Union[str, int], ...]:
    """
    Provides a built-in way to obtain the IP and port of the configuration
    of the server to connect to

    :param ip_prompt: A string, specifying the prompt to show when
        asking for IP.

        Default is "Enter the IP of the server: "
    :type ip_prompt: str, optional
    :param port_prompt: A string, specifying the prompt to show when
        asking for Port

        Default is "Enter the Port of the server: "
    :type port_prompt: str, optional
    :param name_prompt: A string, specifying the prompt to show when
        asking for Client Name

        Default is "Enter name to connect as: " (Pass in None for no input)
    :type name_prompt: Union[str, None], optional
    :param group_prompt: A string, specifying the prompt to show when
        askign for Client Group

        Default is "Enter group to connect to: " (Pass in None for no input)
    :type group_prompt: Union[str, None], optional
    :return: A tuple containing the config options of the server
    :rtype: tuple[str, int, Optional[str], Optional[int]]
    """
    # Grabs IP and Port from previously defined function
    ip, port = input_server_config(ip_prompt, port_prompt)

    # Flags
    name = None
    group = None

    # If names are enabled
    if name_prompt is not None:
        name = input(name_prompt)

        # Repeat until name has an input
        while name == "":
            name = input(name_prompt)

    # If groups are enabled
    if group_prompt is not None:
        group = input(group_prompt)

        # Repeat until group has an input
        while group == "":
            group = input(group_prompt)

    # Return list
    ret = [ip, port]

    if name is not None:
        ret.append(name)
    if group is not None:
        ret.append(group)

    # Return
    return tuple(ret)


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
