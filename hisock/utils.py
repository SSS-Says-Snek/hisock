from __future__ import annotations

import re
import socket
from typing import Union


# __all__ = [
#     'make_header', 'receive_message',
#     'get_local_ip', 'ipstr_to_tup',
#     'iptup_to_str'
# ]


class ClientException(Exception):
    pass


class ServerException(Exception):
    pass


class NoMessageException(Exception):
    pass


class ServerNotRunning(Exception):
    pass


class NoHeaderWarning(Warning):
    pass


def make_header(header_msg, header_len, encode=True):
    len_msg = len(header_msg)
    constructed_header = f"{len_msg}{' ' * (header_len - len(str(len_msg)))}"
    if encode:
        return constructed_header.encode()
    return constructed_header


def receive_message(connection, header_len):
    try:
        header_msg = connection.recv(header_len)

        if header_msg:
            msg_len = int(header_msg)
            data = connection.recv(msg_len)

            return {"header": header_msg, "data": data}
        raise NoMessageException(
            "No header received, aborting..."
        )
    except ConnectionResetError:
        pass


def _removeprefix(string: Union[str, bytes], prefix: Union[str, bytes], /) -> Union[str, bytes]:
    """A backwards-compatible alternative of str.removeprefix"""
    if string.startswith(prefix):
        return string[len(prefix):]
    else:
        return string[:]


def _dict_tupkey_lookup(multikey, _dict, idx_to_match=None):
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


def _dict_tupkey_lookup_key(multikey, _dict, idx_to_match=None):
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


def _type_cast_server(type_cast, content_to_typecast: bytes, func_dict: dict):
    """
    Basis for type casting on the server
    If testing, replace `func_dict` with a dummy one
    Currently NOT guarenteed to return, please remember to change this API
    """
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
    # elif type_cast == list:
    #     try:
    #         _dict = json.loads(content_to_typecast)
    #         typecasted_content = list(_dict.values())
    #         return typecasted_content  # Remember to change this, but I"m lazy rn
    #     except json.decoder.JSONDecodeError as e:
    #         raise TypeError(
    #             f"Type casting from bytes to list"
    #         )


def get_local_ip():
    """
    Gets the local IP of your device, with sockets

    Returns:
      A string containing the IP address, in the
      format "ip:port"
    """
    return socket.gethostbyname(socket.gethostname())


def input_server_config(
        ip_prompt: str = "Enter the IP of where to host the server: ",
        port_prompt: str = "Enter the Port of where to host the server: "
):
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

    ip_range_check = True

    ip = input(ip_prompt)

    if re.search("^((\d?){3}\.){3}(\d\d?\d?)[ ]*$", ip):
        split_ip = list(map(int, ip.split('.')))
        split_ip = [i > 255 for i in split_ip]

        if any(split_ip):
            ip_range_check = True

    while (ip == '' or not re.search(
            "^((\d?){3}\.){3}(\d\d?\d?)[ ]*$",
            ip
    )) or ip_range_check:
        ip = input(f"\033[91mE: Invalid IP\033[0m\n{ip_prompt}")
        if re.search("^((\d?){3}\.){3}(\d\d?\d?)[ ]*$", ip):
            split_ip = list(map(int, ip.split('.')))
            split_ip = [i > 255 for i in split_ip]

            if not any(split_ip):
                ip_range_check = False

    port = input(port_prompt)

    while (
            (port == '' or not port.isdigit()) or
            (port.isdigit() and int(port) > 65535)
    ):
        port = input(f"\033[91mE: Invalid Port\033[0m\n{port_prompt}")
    port = int(port)

    return ip, port


def input_client_config(
        ip_prompt: str = "Enter the IP of the server: ",
        port_prompt: str = "Enter the Port of the server: ",
        name_prompt: Union[str, None] = "Enter name to connect as: ",
        group_prompt: Union[str, None] = "Enter group to connect to: "
):
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
    ip, port = input_server_config(
        ip_prompt, port_prompt
    )

    name = None
    group = None

    if name_prompt is not None:
        name = input(name_prompt)

        while name == '':
            name = input(name_prompt)

    if group_prompt is not None:
        group = input(group_prompt)

        while group == '':
            group = input(group_prompt)

    ret = [ip, port]

    if name is not None:
        ret.append(name)
    if group is not None:
        ret.append(group)

    return ret


def ipstr_to_tup(formatted_ip: str):
    """
    Converts a string IP address into a tuple equivalent

    Args:
      formatted_ip: str
        A string, representing the IP address.
        Must be in the format "ip:port"

    Returns:
      A tuple, with IP address as the first element, and
      an INTEGER port as the second element
    """
    ip_split = formatted_ip.split(':')
    ip_split[1] = str(ip_split[1])  # Formats the port into string
    return tuple(ip_split)


def iptup_to_str(formatted_tuple: tuple[str, int]):
    """
    Converts a tuple IP address into a string equivalent

    Args:
      formatted_tuple: tuple
        A two-element tuple, containing the IP address and the port.
        Must be in the format (ip: str, port: int)

    Returns:
      A string, with the format "ip:port"
    """
    return f"{formatted_tuple[0]}:{formatted_tuple[1]}"
