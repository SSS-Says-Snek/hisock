"""
This module makes the package importable to users.

====================================
Copyright SSS_Says_Snek, 2022-present
====================================
"""

from __future__ import annotations

from hisock import client, constants, server, utils
from hisock.constants import __version__

from .client import (HiSockClient, ThreadedHiSockClient, connect,
                     threaded_connect)
from .server import (HiSockServer, ThreadedHiSockServer, start_server,
                     start_threaded_server)
from .utils import (ClientInfo, get_local_ip, input_client_config,
                    input_server_config, ipstr_to_tup, iptup_to_str)