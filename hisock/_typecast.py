from __future__ import annotations

import pprint
import struct

FMT_TO_TYPE = {"s": str, "i": int, "f": float, "b": bytes}

TYPE_TO_ENCODE_FUNC = {
    str: lambda s: s.encode("utf-8"),
    int: lambda i: str(i).encode("utf-8"),
    float: lambda f: struct.pack("!f", f),
    bytes: lambda b: b,
}

TYPE_TO_FMT = {str: "s", int: "i", float: "f", bytes: "b"}

TYPE_TO_DECODE_FUNC = {
    str: lambda data: data.decode("utf-8"),
    int: lambda data: int(data.decode("utf-8")),
    float: lambda data: struct.unpack("!f", data),
    bytes: lambda data: data,
}

CONTAINER_TO_FMT = {list: "l", tuple: "t", dict: "d"}


def _write_fmt_container(item):
    inner_fmt_part, encoded_data_part, part_container_len = _write_fmt(item, top=False)
    container_len = part_container_len if part_container_len > 0 else int(inner_fmt_part[:-1])
    return inner_fmt_part, encoded_data_part, container_len


def _write_fmt(data, top=True):
    fmt = ""
    encoded_data = b""
    container_len = 0

    if isinstance(data, (list, tuple, dict)):
        inner_fmt = ""
        open_punc = "[" if isinstance(data, list) else "(" if isinstance(data, tuple) else "{"
        close_punc = "]" if isinstance(data, list) else ")" if isinstance(data, tuple) else "}"

        if isinstance(data, dict):
            for key, value in data.items():
                inner_fmt_key, encoded_data_key, key_container_len = _write_fmt_container(key)
                inner_fmt_value, encoded_data_value, value_container_len = _write_fmt_container(value)

                container_len += key_container_len + value_container_len
                inner_fmt += inner_fmt_key + inner_fmt_value
                encoded_data += encoded_data_key + encoded_data_value
        else:
            for item in data:
                inner_fmt_part, encoded_data_part, part_container_len = _write_fmt_container(item)
                container_len += part_container_len
                inner_fmt += inner_fmt_part
                encoded_data += encoded_data_part

        if top:
            fmt += CONTAINER_TO_FMT.get(type(data), "") + inner_fmt
        else:
            fmt += f"{container_len}{open_punc}{inner_fmt}{close_punc}"
    else:
        encode_func = TYPE_TO_ENCODE_FUNC[type(data)]
        fmt_letter = TYPE_TO_FMT[type(data)]
        encoded_data = encode_func(data)

        fmt += f"{len(encoded_data)}{fmt_letter}"

    return fmt, encoded_data, container_len


def write_fmt(data):  # hide top param
    fmt, encoded_data, _ = _write_fmt(data)
    return fmt, encoded_data


data = (273, b"amoguss", "hi")
# g, h, i = write_fmt({(1, 2): "2", "8888": b"sdgoisdhga"})
# g, h, i = write_fmt([[[[[[[[[[1, 2]]]]]]]]]])
fmt, encoded_data = write_fmt(data)
# g, h, i = write_fmt({"hi": "amogus"})
# g, h, i = write_fmt([1, 2, {"hi": "amogus"}])
# g, h, i = write_fmt([1, 2, {((1, 2),): 358568568}])
# g, h, i = write_fmt([1, "32362", b"sdgs", 326236236, (1, 2)])
print(f'Wrote str fmt "{fmt}" from "{data}" for encoded data {encoded_data}')


def _read_fmt_dict(fmt_list, pair_info, pair_counter, len_, flag, type_):
    pair_info["len"][pair_counter % 2] = len_
    pair_info["flag"][pair_counter % 2] = flag
    pair_info["type"][pair_counter % 2] = type_

    pair_counter += 1

    if pair_counter % 2 == 0 and pair_counter > 0:
        fmt_list.append(tuple(zip(pair_info["len"], pair_info["flag"], pair_info["type"])))


def read_fmt(fmts: str):
    print(f'NEW read_fmt CALL w/ str format "{fmts}"')
    i = 0  # Starting char determines tuple, list, or dict
    start = 0
    container_type = fmts[0]
    fmt_list = []

    # Vars to store dict key/value pairs
    pair_counter = 0
    pair_info = {"len": [0, 0], "flag": ["", ""], "type": [None, None]}

    while i < len(fmts):
        char = fmts[i]
        # print(i, char)

        if char in "tld":
            i = 1
            start = 1
            continue

        if char.isalpha():
            if container_type == "d":
                _read_fmt_dict(fmt_list, pair_info, pair_counter, int(fmts[start:i]), "single", FMT_TO_TYPE[char])
                pair_counter += 1
            else:
                # print(fmts[start:i])
                fmt_len, fmt_type = int(fmts[start:i]), fmts[i]
                fmt_list.append((fmt_len, "single", FMT_TO_TYPE[fmt_type]))

            start = i + 1
        elif char in "[({":
            subfmt_container_len = int(fmts[start:i])

            # This is pretty cool. It chops off the already read stream, and if its supposed to read a dict, it
            # FORCES it to read by adding the dict container type to the stream
            skip_amt, subfmt_container = read_fmt(("d" if char == "{" else "") + fmts[i + 1 :])

            if char == "[":
                subfmt_container_type = "list"
            elif char == "(":
                subfmt_container_type = "tuple"
            else:
                subfmt_container_type = "dict"

            if container_type == "d":
                _read_fmt_dict(
                    fmt_list,
                    pair_info,
                    pair_counter,
                    subfmt_container_len,
                    subfmt_container_type,
                    tuple(subfmt_container),
                )
                pair_counter += 1
            else:
                fmt_list.append((subfmt_container_len, subfmt_container_type, subfmt_container))

            i += (
                skip_amt + 1 - (1 if char == "{" else 0)
            )  # Skip over container (recursion will handle that). -1 if char signals dict for the extra "d" added
            start = i + 1  # Reset start to char after
        elif char in "])}":
            print("JUMP UP", i)
            return i, fmt_list  # Specify index to jump to

        i += 1

    if container_type in "tld":
        return container_type, fmt_list
    elif len(fmt_list) == 1:
        return "s", fmt_list  # s for SINGLE
    else:
        return "l", fmt_list  # Default to list (for whatever reason)


fmt = read_fmt(fmt)
print("READ FORMAT")
pprint.pprint(fmt)


def typecast_data_container(data, start, fmt):
    print(f"NEW CALL OF typecast_data_container with format {fmt}, encoded data {data}, and start {start}")
    data_len, data_flag, data_type = fmt
    data_part = data[start : start + data_len]
    if data_flag in ("list", "tuple", "dict"):
        typecasted_data_part = typecast_data(data_type, data_part, data_flag, top=False)
        if data_flag == "tuple":
            typecasted_data_part = tuple(typecasted_data_part)
    else:
        decode_func = TYPE_TO_DECODE_FUNC[data_type]
        typecasted_data_part = decode_func(data_part)

    return data_len, typecasted_data_part


def typecast_data(fmts, data, data_flag="", top=True):
    typecasted_data = []
    start = 0

    container_type = ""
    if top:
        container_type, fmts = fmts
    print(f'NEW CALL OF typecast_data with container type "{container_type}, format {fmts}, and encoded data {data}')

    if container_type == "d" or data_flag == "dict":
        typecasted_data = {}
        for key, value in fmts:
            data_len, typecasted_key = typecast_data_container(data, start, key)
            start += data_len

            data_len, typecasted_value = typecast_data_container(data, start, value)
            start += data_len
            typecasted_data[typecasted_key] = typecasted_value
    else:
        for fmt in fmts:
            data_len, typecasted_data_part = typecast_data_container(data, start, fmt)
            start += data_len

            typecasted_data.append(typecasted_data_part)

    return (
        tuple(typecasted_data)
        if container_type == "t"
        else typecasted_data[0]
        if container_type == "s"
        else typecasted_data
    )


print(typecast_data(fmt, encoded_data))
