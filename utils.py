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


def removeprefix(self: str, prefix: str, /) -> str:
    if self.startswith(prefix):
        return self[len(prefix):]
    else:
        return self[:]


def dict_tupkey_lookup(multikey, _dict):
    for key, value in _dict.items():
        if multikey in key:
            return value


def dict_tupkey_lookup_key(multikey, _dict):
    for key in _dict.keys():
        if multikey in key:
            yield key
