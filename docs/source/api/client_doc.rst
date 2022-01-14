hisock.client
=============

A module containing the main client classes and functions, including
:class:`HiSockClient` and :func:`connect`

.. autoclass:: hisock.client.HiSockClient

   .. automethod:: change_group
   .. automethod:: change_name
   .. automethod:: close
   .. automethod:: on
   .. automethod:: send_raw
   .. automethod:: recv_raw
   .. automethod:: send
   .. automethod:: start
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
