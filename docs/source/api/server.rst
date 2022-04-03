hisock.server
=============

A module containing the main server classes and functions, including
:class:`HiSockServer` and :func:`start_server`

.. note::

   Header lengths shouldn't be too long. By default, the header length is 16 bytes. This is good enough for most applications, as allows for 10**16 bytes to be sent.

.. autoclass:: hisock.server.HiSockServer
   :members:

----

.. autoclass:: hisock.server.ThreadedHiSockServer

   .. automethod:: start
   .. automethod:: close

----

.. autofunction:: hisock.server.start_server

.. autofunction:: hisock.server.start_threaded_server
