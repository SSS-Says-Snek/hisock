hisock.utils
============

A module containing some utilities to either:

1. Help :mod:`hisock.client` and :mod:`hisock.server` run (denoted with leading underscore)
1. Provide functions to use alongside :mod:`HiSock`

.. autoclass:: hisock.utils.ClientInfo
   :members:

.. autofunction:: hisock.utils.make_header
.. autofunction:: hisock.utils.receive_message
.. autofunction:: hisock.utils.validate_command_not_reserved
.. autofunction:: hisock.utils.validate_ipv4
.. autofunction:: hisock.utils.get_local_ip
.. autofunction:: hisock.utils.input_server_config
.. autofunction:: hisock.utils.input_client_config
.. autofunction:: hisock.utils.ipstr_to_tup
.. autofunction:: hisock.utils.tup_to_ipstr