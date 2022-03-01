Intermediate-level Tutorial
===========================

.. contents:: Table of Contents
   :depth: 2
   :local:
   :class: this-will-duplicate-information-and-it-is-still-useful-here

Before you start
----------------

It is imperative that you have basic knowledge of :mod:`HiSock`. You should know everything that the beginner tutorial focuses on. If you don't know, :doc:`read that now</tutorials/beginner_tutorial>`!

This tutorial will focus on:

- Overriding reserved events
- How commands and data are sent
- Threading
- The other send methods
- The other receive methods
- Catch-all listeners (wildcard)
- Groups, names, and client info

----
  
Override
--------

In :mod:`HiSock`, there are some reserved events. However, some use-cases may want to use the same name as the reserved events for unreserved events. In order to do this, you can override the reserved events. The ``on`` decorator has an argument for overriding a command. When set to ``True``, the event will be treated like an unreserved event.

.. warning::
   This isn't recommended doing most times. Typically, the reserved events are used for handling clients. For example, if you override the join event, you'll have to have the client send a join event.

Here is an example with a server-side code-block.

.. code-block:: python
   
   server = ...

   @server.on("leave", override=True)
   def on_leave(client_data, reason: str):
       print(f"{client_data.name} left because {reason}")
       server.disconnect_client(client_data.ip, force=True)

   server.run()


Now, the ``leave`` event won't be called when a client leaves. Instead, a client will manually send the ``leave`` event.

----

Threading
---------

In :mod:`HiSock`, there is an option for the client or server to run entirely in a different thread. This can be useful if you want to have a server that doesn't block the main thread, such as in conjunction with Pygame or Tkinter.

This is really simple to use! In place of :class:`HiSockServer` or :class:`HiSockClient`, you can use :class:`ThreadedHiSockServer` or :class:`ThreadedHiSockClient` respectively. You can also use :func:`threaded_connect` in place of :func:`connect` and :func:`start_threaded_server` in place of :func:`start_server`.

----

How commands and data are sent
------------------------------

Commands and data are sent in a special syntax.

.. note::
   In this section, text in ``<>`` is a placeholder for data.

=================
Reserved commands
=================

For reserved commands, the syntax is different for each one.

For the client:

- ``$KEEPALIVE$``

   This command is sent to the client from the server to make sure that the client is still connected.
- ``$DISCONN$``
  
   This command is sent to the client from the server to disconnect the client.
- ``$CLTCONN$<client info as a stringified dict>``

   This command is sent to the client from the server to inform that a new client connected.
- ``$CLTDISCONN$<client info as a stringified dict>``

   This command is sent to the client from the server to inform that a client disconnected.

For the server:

- ``<connecting socket is same as server socket>``

   This happens when a new client connects to server.
- ``<bad client file number>`` OR ``<client data is falsy>`` OR ``$USRCLOSE$``
  
   This happens when the client closes the connection and emits its leave, or it encounters an error when transmitting data. The client will be disconnected.
- ``$KEEPACK$``

   This is sent to the client from the server to acknowledge that the client is still connected.
- ``$GETCLT$<client_identifier, either a name or stringified IP>``

   This is sent to the server from the client to get the client's data.
- ``$CHNAME$<new name>`` OR ``$CHGROUP$<new group>``

   This is sent to the server from the client to change the client's name or group, respectively.

====

===================
Unreserved commands
===================

For reserved commands, the data is sent as follows:

- ``command`` and ``message`` sent

   ``$CMD$<command>$MSG$<message>``
- ``command`` sent

   ``$CMD$<command>``

----

The other send methods
----------------------

In :mod:`HiSock`, there are multiple send methods for the *server*. These methods are:

- ``send_client`` - sends a command and/or message to a singe client
- ``send_all_clients`` - sends a command and/or message to every client connected
- ``send_group`` - sends a command and/or message to every client in a group

There are also a few internal send methods that shouldn't need to be used. They are used for sending *raw* data. These methods are:

- ``_send_client_raw``
- ``_send_all_clients_raw``
- ``_send_group_raw``

----

A new way to receive data
-------------------------

In :mod:`HiSock`, there is also a different way to receive data.

Say you want to send data and wait for a response. Normally, you'd have to do something like this:

.. code-block:: python

   client = ...

   @client.on("start")
   def on_start():
       client.send(input("What would you like to say?"))
       print("Waiting for a response...")

   @client.on("response")
   def on_response(response: str):
       print(f"The server said: {response}")

   client.start()

However, there is a better way! There is a method called :meth:`recv`. This method has two parameters. The parameters (in order) are the command to receive on (optional) and the type to receive as (defaults to bytes).

The :meth:`recv` method works like the ``on`` decorator. If the command to receive on is not specified, :meth:`recv` will receive on any command or data that is sent and not caught by a function. Otherwise, it will only receive on the command. Then, the message received will be type-casted to the type specified and returned.

:meth:`recv` is blocking, so the code in the function will pause until it's done. This is why it's recommended to use it in a threaded function.

Now, let's use the example above, but using the :meth:`recv` method!

.. code-block:: python

   client = ...

   @client.on("start", threaded=True)
   def on_start():
       client.send(input("What would you like to say?"))
       print("Waiting for a response...")
       response = client.recv("response", str)
       print(f"The server said: {response}")

   client.start()

----

Catch-all listeners (wildcard)
------------------------------

In :mod:`HiSock`, there is a way to catch every piece of data sent that hasn't been handled by a listener already. This amazing thing is known as the catch-all or wildcard listener. Despite the name, this is not like the ``message`` reserved listener. It will only be called when there is no other handler for the data.

The function that will be called for the catch-all listener will be passed in the client data if it's a server, the command, and the message. If there is no message, it'll be type-casted into the equivalent of ``None``.

Here is an example with a client-side and server-side code block:

.. code-block:: python

   client = ...

   client.send(
      "hello i am an uncaught command",
      f"Random data: "
      + "".join(
         [
               chr(choice((randint(65, 90), randint(97, 122))))
               for _ in range(100)
         ]
      ),
   )

   @client.on("client_connect")
   def on_connect(client_data):
       ...

   @client.on("client_disconnect")
   def on_disconnect(client_data):
       ...

   @client.on("*")
   def on_wildcard(command: str, data: str):
       print(f"The server sent some uncaught data: {command=}, {data=}")

   client.start()


.. code-block:: python

   server = ...

   @server.on("join")
   def on_join(client_data):
      ...
   
   @server.on("leave")
   def on_leave(client_data):
      ...

   @server.on("*")
   def on_wildcard(client_data, command: str, data: str):
       print(
           f"There was some unhandled data from {client_data.name}. "
           f"{command=}, {data=}"
       )

       server.send_client(client_data, "i am also an uncaught command", data.replace("a", "ඞ"))

   server.start()


----

Groups, name, and client info
-----------------------------

In :mod:`HiSock`, each client has its own client data. Like mentioned in the previous tutorial, this client data can be a dictionary or an instance of :class:`ClientInfo`.

Client info contains the following:

- ``name``

   The name of the client. Will be ``None`` if not entered.
- ``group``

   The group of the client. Will be ``None`` if not entered.
- ``ip``
  
   The IP and port of the client as a string.

:class:`ClientInfo` can also act like a dictionary, so you can access the client's data like this:

.. code-block:: python
   
   server = ...

   @server.on("join")
   def on_join(client_data):
       ip = client_data.ip  # Normal access
       name = client_data["name"]  # Dictionary-like access
       group = client_data.group   #Normal access