from __future__ import annotations

import pprint
import struct
from typing import Any, Union

FMT_TO_TYPE = {"s": str, "i": int, "f": float, "b": bytes}

TYPE_TO_ENCODE_FUNC = {
    str: lambda s: s.encode("utf-8"),
    int: lambda i: str(i).encode("utf-8"),
    float: lambda f: struct.pack("!f", f),
    bytes: lambda b: b,
}

TYPE_TO_DECODE_FUNC = {
    str: lambda data: data.decode("utf-8"),
    int: lambda data: int(data.decode("utf-8")),
    float: lambda data: struct.unpack("!f", data),
    bytes: lambda data: data,
}

TYPE_TO_FMT = {str: "s", int: "i", float: "f", bytes: "b"}
CONTAINER_TO_FMT = {list: "l", tuple: "t", dict: "d"}

CONTAINER_SYMBOLS = {list: ("[", "]"), tuple: ("(", ")"), dict: ("{", "}")}
SYMBOL_TO_FMT = {"[": "l", "(": "t", "{": "d"}


class TypecastException(Exception):
    pass


def _write_fmt(data: Any, top: bool = True):
    fmt = ""
    encoded_data = b""
    container_len = 0

    if isinstance(data, (list, tuple, dict)):  # Container, recurse through all items
        inner_fmt = ""
        open_punc, close_punc = CONTAINER_SYMBOLS[type(data)]

        data_to_encode = [data]  # Kind of a cool hack for the nested loop
        if isinstance(data, dict):
            data_to_encode = data.items()

        for item in data_to_encode:
            for item_part in item:
                # Recursion to get item info
                inner_item_fmt, encoded_item, item_container_len = _write_fmt(item_part, top=False)
                if item_container_len == 0:  # Primitive
                    item_container_len = int(inner_item_fmt[:-1])

                container_len += item_container_len
                inner_fmt += inner_item_fmt
                encoded_data += encoded_item

        if top:  # Include beginning fmt to tell what type the result should be
            fmt += CONTAINER_TO_FMT.get(type(data), "") + inner_fmt
        else:  # Container: add container len with symbols surrounding the inner fmt
            fmt += f"{container_len}{open_punc}{inner_fmt}{close_punc}"
    else:  # Primitive
        try:
            encode_func = TYPE_TO_ENCODE_FUNC[type(data)]
        except KeyError:
            raise TypecastException(
                f'Failed to find default encoding function for "{data}" of type "{type(data)}". If you want to send this, convert it manually to and from bytes.'
            ) from None

        fmt_letter = TYPE_TO_FMT[type(data)]
        encoded_data = encode_func(data)

        fmt += f"{len(encoded_data)}{fmt_letter}"

    return fmt, encoded_data, container_len


def write_fmt(data: Any) -> tuple[str, bytes]:  # hide top param and container len
    fmt, encoded_data, _ = _write_fmt(data)
    return fmt, encoded_data


def _read_fmt_dict(
    fmt_list: list, pair_info: dict, pair_counter: int, len_: int, flag: str, type_: Union[type, tuple]
):
    # Write info to appropriate pair (from pair_counter)
    pair_info["len"][pair_counter % 2] = len_
    pair_info["flag"][pair_counter % 2] = flag
    pair_info["type"][pair_counter % 2] = type_

    pair_counter += 1  # Doesn't actually modify it
    if pair_counter % 2 == 0 and pair_counter > 0:
        # Creates two tuples with len, flag, and type
        fmt_list.append(tuple(zip(pair_info["len"], pair_info["flag"], pair_info["type"])))


def read_fmt(fmts: str):
    if fmts == "":
        return []

    # print(f'NEW read_fmt CALL w/ str format "{fmts}"')
    i = 0  # Starting char determines tuple, list, or dict
    start = 0
    container_type = fmts[0]
    fmt_list = []

    # Vars to store dict key/value pairs
    pair_counter = 0
    pair_info = {"len": [0, 0], "flag": ["", ""], "type": [None, None]}

    while i < len(fmts):
        char = fmts[i]
        if char in "tld":  # Skip beginning fmt
            i = 1
            start = 1
            continue

        if char.isalpha():  # End of primitive
            if container_type == "d":
                _read_fmt_dict(fmt_list, pair_info, pair_counter, int(fmts[start:i]), "p", FMT_TO_TYPE[char])
                pair_counter += 1
            else:
                # print(fmts[start:i])
                fmt_len, fmt_type = int(fmts[start:i]), fmts[i]
                fmt_list.append((fmt_len, "primitive", FMT_TO_TYPE[fmt_type]))

            start = i + 1
        elif char in "[({":  # Start of container
            subfmt_container_len = int(fmts[start:i])

            # Recurses through container fmt until end detected
            # This is pretty cool. It chops off the already read stream, and if it's supposed to read a dict, it
            # FORCES it to read by adding the dict container type to the stream
            skip_amt, subfmt_container = read_fmt(("d" if char == "{" else "") + fmts[i + 1 :])

            # Determines flag for `typecast_data` to use
            subfmt_container_flag = SYMBOL_TO_FMT[char]
            if container_type == "d":
                _read_fmt_dict(
                    fmt_list,
                    pair_info,
                    pair_counter,
                    subfmt_container_len,
                    subfmt_container_flag,
                    tuple(subfmt_container),
                )
                pair_counter += 1
            else:
                fmt_list.append((subfmt_container_len, subfmt_container_flag, subfmt_container))

            i += (
                skip_amt + 1 - (1 if char == "{" else 0)
            )  # Skip over container (recursion will handle that). Sub 1 if char signals dict for the extra "d" added
            start = i + 1  # Reset start to char after
        elif char in "])}":  # End of container
            # print("JUMP UP", i)
            return i, fmt_list  # Specify index to jump to

        i += 1

    if container_type in "tld":
        return container_type, fmt_list
    elif len(fmt_list) == 1:
        return "p", fmt_list  # p for PRIMITIVE
    else:
        return "l", fmt_list  # Default to list


def _typecast_data_container(fmt, data: bytes, start):
    # print(f"NEW CALL OF typecast_data_container with format {fmt}, encoded data {data}, and start {start}")
    data_len, data_flag, data_type = fmt
    data_part = data[start : start + data_len]

    if data_flag in "tld":
        typecasted_data_part = typecast_data(data_type, data_part, data_flag, top=False)
        if data_flag == "t":
            typecasted_data_part = tuple(typecasted_data_part)
    else:
        decode_func = TYPE_TO_DECODE_FUNC[data_type]
        typecasted_data_part = decode_func(data_part)

    return data_len, typecasted_data_part


def typecast_data(fmts: list, data: bytes, data_flag: str = "", top: bool = True):
    typecasted_data = []
    start = 0

    container_type = ""
    if top:
        if len(fmts) == 0:
            return None
        container_type, fmts = fmts
    # print(f'NEW CALL OF typecast_data with container type "{container_type}, format {fmts}, and encoded data {data}')

    if container_type == "d" or data_flag == "d":
        typecasted_data = {}
        for key, value in fmts:
            data_len, typecasted_key = _typecast_data_container(key, data, start)
            start += data_len

            data_len, typecasted_value = _typecast_data_container(value, data, start)
            start += data_len
            typecasted_data[typecasted_key] = typecasted_value
    else:
        for fmt in fmts:
            data_len, typecasted_data_part = _typecast_data_container(fmt, data, start)
            start += data_len

            typecasted_data.append(typecasted_data_part)

    return (
        tuple(typecasted_data)
        if container_type == "t"
        else typecasted_data[0]
        if container_type == "p"
        else typecasted_data
    )


if __name__ == "__main__":
    data = 3
    # g, h, i = write_fmt({(1, 2): "2", "8888": b"sdgoisdhga"})
    # g, h, i = write_fmt([[[[[[[[[[1, 2]]]]]]]]]])
    fmt, encoded_data = write_fmt(data)
    # g, h, i = write_fmt({"hi": "amogus"})
    # g, h, i = write_fmt([1, 2, {"hi": "amogus"}])
    # g, h, i = write_fmt([1, 2, {((1, 2),): 358568568}])
    # g, h, i = write_fmt([1, "32362", b"sdgs", 326236236, (1, 2)])
    print(f'Wrote str fmt "{fmt}" from "{data}" for encoded data {encoded_data}')

    fmt = read_fmt(fmt)
    print("READ FORMAT")
    pprint.pprint(fmt)

    print(typecast_data(fmt, encoded_data))
