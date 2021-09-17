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

.. autoclass:: server.HiSockServer

   .. automethod:: get_addr
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

hisock.client
-------------
A module containing the main client classes and functions, including
:class:`HiSockClient` and :func:`connect`

.. autoclass:: client.HiSockClient

   .. automethod:: close
   .. automethod:: on
   .. automethod:: raw_send
   .. automethod:: recv_raw
   .. automethod:: update
   .. note::

      This is the main method to run HiSockClient. This **MUST** be called
      every iteration in a while loop, as to keep waiting time as short as possible
      between client and server. It is also recommended to put this in a thread.