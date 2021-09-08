from typing import Union


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
        return False
    except ConnectionResetError:
        pass


def removeprefix(string: Union[str, bytes], prefix: Union[str, bytes], /) -> Union[str, bytes]:
    if string.startswith(prefix):
        return string[len(prefix):]
    else:
        return string[:]


def dict_tupkey_lookup(multikey, _dict, idx_to_match=None):
    for key, value in _dict.items():
        if idx_to_match is None:
            if multikey in key:
                yield value
        elif isinstance(idx_to_match, int):
            if multikey == key[idx_to_match]:
                yield value


def dict_tupkey_lookup_key(multikey, _dict, idx_to_match=None):
    for key in _dict.keys():
        if idx_to_match is None:
            if multikey in key:
                yield key
        elif isinstance(idx_to_match, int):
            if multikey == key[idx_to_match]:
                yield key
