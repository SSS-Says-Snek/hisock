API Reference
=============

hisock.server
-------------
A module containing the main server classes and functions, including
:class:`HiSockServer` and :func:`start_server`

.. note::

   Header lengths usually should not be that long;
   on average, header lengths are about 64 bytes long, which is more than
   enough for most cases (10 vigintillion, 10**64). Plus, a release is planned
   for hisock that utilizes ints to bump the header utilization from
   `10**x` to `2**(7x)` (where x is the header length)

.. autoclass:: hisock.server.HiSockServer

   .. automethod:: close
   .. automethod:: disconnect_all_clients
   .. automethod:: disconnect_client
   .. automethod:: get_addr
   .. automethod:: get_all_clients
   .. automethod:: get_client
   .. automethod:: get_group
   .. automethod:: on
   .. automethod:: run
   .. note::

      This is the main method to run HiSockServer. This **MUST** be called
      every iteration in a while loop, as to keep waiting time as short as possible
      between client and server. It is also recommended to put this in a thread.
   .. automethod:: send_all_clients
   .. automethod:: send_client
   .. automethod:: send_client_raw
   .. automethod:: send_group
   .. automethod:: send_group_raw

.. autoclass:: hisock.server.ThreadedHiSockServer

   .. automethod:: join
   .. automethod:: run
   .. automethod:: start_server
   .. automethod:: stop_server


.. autofunction:: hisock.server.start_server

.. autofunction:: hisock.server.start_threaded_server

hisock.client
-------------
A module containing the main client classes and functions, including
:class:`HiSockClient` and :func:`connect`

.. autoclass:: hisock.client.HiSockClient

   .. automethod:: change_group
   .. automethod:: change_name
   .. automethod:: close
   .. automethod:: on
   .. automethod:: raw_send
   .. automethod:: recv_raw
   .. automethod:: send
   .. automethod:: update
   .. note::

      This is the main method to run HiSockClient. This **MUST** be called
      every iteration in a while loop, as to keep waiting time as short as possible
      between client and server. It is also recommended to put this in a thread.

.. autoclass:: hisock.client.ThreadedHiSockClient

   .. automethod:: join
   .. automethod:: run
   .. automethod:: start_client
   .. automethod:: stop_client

.. autofunction:: hisock.client.connect

.. autofunction:: hisock.client.threaded_connect

hisock.utils
------------
A module containing some utilities to either:

1. Help :mod:`hisock.client` and :mod:`hisock.server` run (denoted with leading underscore)

2. Provide functions to use alongside hisock

.. autofunction:: hisock.utils.get_local_ip
.. autofunction:: hisock.utils.input_client_config
.. autofunction:: hisock.utils.input_server_config
.. autofunction:: hisock.utils.ipstr_to_tup
.. autofunction:: hisock.utils.iptup_to_str