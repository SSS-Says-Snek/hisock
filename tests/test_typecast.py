"""
Tests if the typecast (for the typecasting between bytes and other vals) works
This is essential to see if the typecasting works. If it doesn't, then
type casting for hisock will crash. We don't want that!
"""

import pytest

from utils import _type_cast_server


class TestServerTypeCast:
    dummy_func = {
        "name": "random_function"
    }

    def test_type_cast_str(self):
        _str = _type_cast_server(
            str, b"Why hello there, fello human!",
            self.__class__.dummy_func
        )

        assert _str == "Why hello there, fello human!"

    def test_type_cast_str_raise(self):
        with pytest.raises(TypeError):
            _str2 = _type_cast_server(
                str, b"\xff\xfea\x00",  # Encoded in utf-16, so...
                self.__class__.dummy_func
            )

    def test_type_cast_int(self):
        _int = _type_cast_server(
            int, b"6969696969696969",
            self.__class__.dummy_func
        )

        assert _int == 6969696969696969

    def test_type_cast_int_raise(self):
        with pytest.raises(TypeError):
            _int2 = _type_cast_server(
                int, b"This is not int, why???",
                self.__class__.dummy_func
            )

    def test_type_cast_float(self):
        _float = _type_cast_server(
            float, b"696969.696969",
            self.__class__.dummy_func
        )

        assert _float == 696969.696969

    def test_type_cast_float_raise(self):
        with pytest.raises(TypeError):
            _float2 = _type_cast_server(
                float, b"This is not float, why???",
                self.__class__.dummy_func
            )

    def test_type_cast_invalid_cast(self):
        invalid = _type_cast_server(
            bytearray, b"haha this will not do anything",
            self.__class__.dummy_func
        )

        # WARNING: This API part is scheduled to be changed;
        # It will soon raise an exception, rather than returning None
        # Be careful of the API change, coming in a few months

        assert invalid is None
