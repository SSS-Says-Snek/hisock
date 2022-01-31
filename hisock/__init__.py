"""
This module makes the package importable to users.

====================================
Copyright SSS_Says_Snek, 2022-present
====================================
"""

from hisock import constants  # lgtm [py/unused-import]
from hisock import utils  # lgtm [py/unused-import] lgtm [py/import-and-import-from]

from hisock import client  # lgtm [py/unused-import]
from hisock import server  # lgtm [py/unused-import]

from hisock.constants import __version__  # lgtm [py/unused-import]

from .server import (
    start_server,
    start_threaded_server,
    HiSockServer,
)  # lgtm [py/unused-import]
from .client import (
    connect,
    threaded_connect,
    HiSockClient
)  # lgtm [py/unused-import]
from .utils import (  # lgtm [py/unused-import]
    get_local_ip,  # lgtm [py/unused-import]
    input_client_config,
    input_server_config,  # lgtm [py/unused-import]
    ipstr_to_tup,
    iptup_to_str,  # lgtm [py/unused-import]
)

import examples  # lgtm [py/unused-import]
