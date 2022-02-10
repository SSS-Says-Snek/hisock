"""
Tests if the type-cast works.
"""

import pytest

from hisock.utils import _type_cast, InvalidTypeCast, ClientInfo, SendableTypes
from typing import Any


class Error:
    """Sentinel class for expecting to raise an error"""


tests = {
    "bytes": [
        {"original": "hello", "expected": b"hello"},
        {"original": 1, "expected": b"1"},
        {"original": 1.0, "expected": b"1.0"},
        {"original": True, "expected": b"\x00"},
        {"original": False, "expected": b""},
        {"original": None, "expected": b""},
    ],
    "str": [
        {"original": b"hello", "expected": "hello"},
        {"original": 1, "expected": "1"},
        {"original": 1.0, "expected": "1.0"},
        {"original": True, "expected": "True"},
        {"original": False, "expected": "False"},
        {"original": None, "expected": ""},
        {"original": ["a", "b"], "expected": '["a", "b"]'},
        {"original": {"a": "b"}, "expected": '{"a": "b"}'},
    ],
    "int": [
        {"original": "", "expected": 0},
        {"original": "1", "expected": 1},
        {"original": b"", "expected": 0},
        {"original": b"1", "expected": 1},
        {"original": 1.6, "expected": 1},
        {"original": True, "expected": 1},
        {"original": None, "expected": 0},
        {"original": False, "expected": 0},
        {"original": ["a", "b"], "expected": Error},
        {"original": {"a": "b"}, "expected": Error},
        {"original": "hello", "expected": Error},
    ],
    "float": [
        {"original": "", "expected": 0.0},
        {"original": "1", "expected": 1.0},
        {"original": b"", "expected": 0.0},
        {"original": b"1", "expected": 1.0},
        {"original": 1, "expected": 1.0},
        {"original": 1.6, "expected": 1.6},
        {"original": True, "expected": 1.0},
        {"original": None, "expected": 0.0},
        {"original": False, "expected": 0.0},
        {"original": ["a", "b"], "expected": Error},
        {"original": {"a": "b"}, "expected": Error},
        {"original": "hello", "expected": Error},
    ],
    "dict": [
        {"original": '{"a": "b"}', "expected": {"a": "b"}},
        {"original": b'{"a": "b"}', "expected": {"a": "b"}},
        {"original": "", "expected": {}},
        {"original": "hello", "expected": Error},
        {"original": ["a", "b"], "expected": Error},
    ],
    "list": [
        {"original": '["a", "b"]', "expected": ["a", "b"]},
        {"original": b'["a", "b"]', "expected": ["a", "b"]},
        {"original": "", "expected": []},
        {"original": {"a": "b"}, "expected": Error},
        {"original": "hello", "expected": Error},
    ],
    "client_info": [
        {
            "original": {"ip": ("127.0.0.1", "5000"), "name": "a", "group": None},
            "expected": ClientInfo(
                **{"ip": ("127.0.0.1", "5000"), "name": "a", "group": None}
            ),
        },
        {
            "original": '{"ip": ["127.0.0.1", "5000"], "name": "a", "group": None}"',
            "expected": Error,
        },
        {"original": {"name": "a"}, "expected": Error},  # Missing ip
    ],
    "random": [
        {"original": "hello", "expected": Error},
    ],
}


class TestServerTypeCast:
    @staticmethod
    def _test_type_cast(
        type_cast: SendableTypes, test: Any, expected: Any, func_name: str
    ):
        """
        Tests a single type-cast.

        :param type: The type to test.
        :param test: The test-case to test.
        :param expected: The expected result. If it is an Error, it is expected
            to raise an InvalidTypeCast error.
        """

        func_name = f"<test {func_name} {test=} to {type_cast.__name__=}>"

        if expected is Error:
            with pytest.raises(InvalidTypeCast):
                _type_cast(
                    type_cast=type_cast, content_to_type_cast=test, func_name=func_name
                )
        else:
            assert (
                _type_cast(
                    type_cast=type_cast, content_to_type_cast=test, func_name=func_name
                )
                == expected
            )

    @pytest.mark.parametrize("test", tests["bytes"])
    def test_bytes(self, test):
        self._test_type_cast(
            bytes, test["original"], test["expected"], func_name="bytes"
        )

    @pytest.mark.parametrize("test", tests["str"])
    def test_str(self, test):
        self._test_type_cast(str, test["original"], test["expected"], func_name="str")

    @pytest.mark.parametrize("test", tests["int"])
    def test_int(self, test):
        self._test_type_cast(int, test["original"], test["expected"], func_name="int")

    @pytest.mark.parametrize("test", tests["float"])
    def test_float(self, test):
        self._test_type_cast(
            float, test["original"], test["expected"], func_name="float"
        )

    @pytest.mark.parametrize("test", tests["dict"])
    def test_dict(self, test):
        self._test_type_cast(dict, test["original"], test["expected"], func_name="dict")

    @pytest.mark.parametrize("test", tests["list"])
    def test_list(self, test):
        self._test_type_cast(list, test["original"], test["expected"], func_name="list")

    @pytest.mark.parametrize("test", tests["client_info"])
    def test_client_info(self, test):
        self._test_type_cast(
            ClientInfo, test["original"], test["expected"], func_name="client info"
        )

    @pytest.mark.parametrize("test", tests["random"])
    def test_random(self, test):
        self._test_type_cast(
            Any, test["original"], test["expected"], func_name="random"
        )
