hisock.server
=============

A module containing the main server classes and functions, including
:class:`HiSockServer` and :func:`start_server`

.. note::

   Header lengths usually should not be that long;
   on average, header lengths are about 64 bytes long, which is more than
   enough for most cases (10 vigintillion, 10**64). Plus, a release is planned
   for hisock that utilizes ints to bump the header utilization from
   `10**x` to `2**(7x)` (where x is the header length)

.. autoclass:: hisock.server.HiSockServer
   :members:

----

.. autoclass:: hisock.server.ThreadedHiSockServer

   .. automethod:: join
   .. automethod:: start
   .. automethod:: stop

----

.. autofunction:: hisock.server.start_server

.. autofunction:: hisock.server.start_threaded_server
