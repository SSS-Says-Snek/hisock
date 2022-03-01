Beginner Tutorial
=================

.. contents:: Table of Contents
   :depth: 2
   :local:
   :class: this-will-duplicate-information-and-it-is-still-useful-here

Before you start
----------------

It is highly encouraged that you read the :doc:`/quickstart/understanding_hisock` section before reading the tutorial.

This tutorial also relies on you having basic networking knowledge (client/server, IP addresses, ports, etc.) and at least basic Python knowledge.

Lastly, if you don't have :mod:`HiSock` installed, do that now! Read :doc:`/quickstart/installation`.

This tutorial will focus on:

- Creating a server
- Creating a client
- Sending and receiving data
- Acting upon the data

.. note::
   For this tutorial, I will be referring the IP addresses as ``hisock.utils.get_local_ip()``. In reality, you will most likely use a hard-coded IP address from a user input.

.. note::
   When I refer to "a way to identify the client", I am talking about either:

   - a tuple of the IP address and port of the client or
   - a string of the client's name (this will have ambiguity if multiple clients share the same name)

.. note::
   There are a few terms that are used interchangeably here.

   - Message, content, and data mean the same thing.
   - Command and event mean the same thing.

Now, without further ado, let's begin!

----

Creating our first server
-------------------------

In :mod:`HiSock`, there exists a class, :class:`HiSockServer`, in the ``server`` module. To create a server, you will need to create an instance of this class. The ``__init__`` function of the :class:`HiSockServer` class takes a required tuple parameter, which is the IP address as a string and port as an integer to start the server on. To find the local IP address, there is a function called :func:`utils.get_local_ip`. For the port, a number between 1024 and 65535 *should* be fine.

:class:`HiSockServer` instances have a :meth:`start` method to them, which will allow the server to listen for commands and data being sent.

.. code-block:: python

   import hisock

   server = hisock.server.HiSockServer((hisock.utils.get_local_ip(), 6969))

   server.start()

That's basically it! Of course, this server is useless, but hey, it's a step in the right direction! We'll add on to this later on.

Obviously, without a client, a server is kind of pointless. So, let's spice things up with some client code!

----

Creating our first client
-------------------------
In :mod:`HiSock`, there is a class, :class:`HiSockClient`, in the ``client`` module. To create a client, you will need to create an instance of this class. The ``__init__`` function of the :class:`HiSockClient` class takes two required parameters. The first parameter is a tuple with the IP address and port that the server is running on. The second (optional) parameter is for the name of the client, which is used for identification. The third (optional) parameter is the group of the client, which won't be talked about in this tutorial.

Like :class:`HiSockServer`, :class:`HiSockClient` needs to have its :meth:`start` method called to start the client.

.. code-block:: python

   import hisock

   client = hisock.client.HiSockClient(
       (hisock.utils.get_local_ip(), 6969),
       name=input("What is your name? >")
   )

   client.start()

Like the server, this doesn't do anything at all yet. Next, we will explore sending and receiving data in an example.

----

Transmitting Data
-----------------

Let's explore transmitting data for :mod:`HiSock`!

:mod:`HiSock` is an event-driven module, and as such, has an ``on`` decorator and :meth:`send` methods for both :class:`HiSockClient` and :class:`HiSockServer`.

----

==============
Receiving data
==============

.. note::
   There is another way of receiving data, which is the :meth:`recv` method. This is not covered in this tutorial, but it is covered in the :doc:`/tutorials/intermediate_tutorial`.

When a function is prefaced with the ``on`` decorator, it will run on something. It will listen for a command and run when that command is received.

The ``on`` decorator takes a maximum of three parameters. One of the parameters is the command to listen on. The second (optional) parameter is whether to run the listener in its own thread or not. The third (optional) parameter is whether to override a reserved command, and this tutorial won't be covering it.

For the server: The ``on`` decorator will send a maximum of two parameters to the function it is decorating (there are a few exceptions we will touch on). The first parameter is the client data. It is an instance of :class:`ClientInfo` that includes the client's name, client IP address, and the group the client is in (can be type-casted to a dict). The second parameter is the data that is being received.

For the client: the ``on`` decorator will send a maximum of one parameter to the function it is decorating, which will be the message or content the client receives (in most cases).

Here's an example with the ``on`` decorator in use in a server. Here, the server has a command, ``print_message_name``, and will print the message that it gets and who sent it.

.. code-block:: python

   server = ...

   @server.on("print_message_name")
   def on_print_message_name(client_data, message: str):
       print(f'{client_data.name} sent "{message}"')

   server.start()

Here's another example with receiving data, this time on the client-side. The client will receive a command, ``greet``, with a name. It will then print out a greeting with the name.

.. code-block:: python

   client = ...

   @client.on("greet")
   def on_greet(name: str):
       print(f"Hello there, {name}!")

   client.start()

If the ``threaded`` parameter for the ``on`` decorator is True, then the function being decorated will run in a separate thread. This allows blocking code to run while still listening for updates.

It is useful if you want to get user input but also want to have the user receive other data.

.. code-block:: python

   client = ...

   @client.on("ask_question", threaded=True)
   def on_ask_question(question: str):
       """Contains blocking code with ``input()``."""
       answer = input(f"Please answer this question: {question}\n>")
       # ... send answer to server ...

   @client.on("important")
   def on_important(message: str):
       """This is important and cannot be missed!"""
       ...

   client.start()


----

============
Sending data
============

:mod:`HiSock` has multiple send methods. For now, we will be talking about sending to the server from one client or to one client from the server.

For the server: Sending data from the server to one client in :mod:`HiSock` uses the :meth:`send_client` method. This method takes in a maximum of three parameters. The three parameters (in order) are a way to identify the client, the command to send, and the message being sent (optional). Although we won't be talking about it here, :meth:`send_all_clients` does exactly what it says. It will do :meth:`send_client` to all the clients that are connected, and only takes in the command and optional message

For the client: Sending data to the server in :mod:`HiSock` uses the :meth:`send` method. This method takes a maximum of two parameters. The first parameter is the command to send, and the second parameter is the message being sent (optional).

Here is an example of sending data with a server-side code block:

.. code-block:: python

   server = ...

   @server.on("join")
   def on_client_join(client_data):
       server.send_client(client_data.ip, "ask_question", "Do you like sheep?")

   @server.on("question_response")
   def on_question_response(client_data, response: str):
       server.send_client(client_data.ip, "grade", 100)

   server.start()

And here is an example on the client-side:

.. code-block:: python

   client = ...

   @client.on("ask_question")
   def on_ask_question(question: str):
       answer = input(f"Please answer this question: {question}\n>")
       client.send("question_response", answer)

   @client.on("grade")
   def on_grade(grade: int):
       print(f"You got a {grade:>3}%.")

   client.start()


----

===============
Reserved events
===============

As I stated before, not every receiver has a maximum of two parameters passed to it. Here are the cases where that is the case.

:mod:`HiSock` has reserved events. These events shouldn't be sent by the client or server explicitly as it is currently unsupported.

.. note::
   Besides for ``string`` and ``bytes`` for ``message``, these reserved events do not have type casting.

Here is a list of the reserved events:

Server:

- ``join``

   The client sends the event ``join`` when they connect to the server. The only parameter sent to the function being decorated is the client data.
- ``leave``

   The client sends the event ``leave`` when they disconnect from the server. The only parameter sent to the function being decorated is the client data.
- ``name_change``

   The client sends the event ``name_change`` when they change their name. The parameters sent to the listening function are (in order) the client data, the old name, and the new name.
- ``group_change``

   The client sends the event ``group_change`` when they change their group. The parameters sent to the listening function are (in order) the client data, the old group, and the new group.
- ``message``

   When the server receives a command, it'll send an event to itself called ``message`` which will have two parameters. The two parameters are the client data who sent it and the raw data which was received.

- ``*``

   This will be called when there is no listener for an incoming command and data. The three parameters are the client data, the command, and the content.

Client:

- ``client_connect``

   When a client connects to the server, all the clients will have this event called. The only parameter for this is the client data for the client which joined.
- ``client_disconnect``

   When a client disconnects from the server, all the clients will have this event called. The only parameter for this is the client data for the client which left.
- ``force_disconnect``

   The server sends the event ``force_disconnect`` to a client when they kick the client. There are *no* parameters sent with the function that is being decorated with this.
- ``*``

   This will be called when there is no listener for an incoming command and data. The two parameters are the command and the content.

----

============
Type-casting
============
:mod:`HiSock` has a system called "type-casting" when transmitting data.

Data sent and received can be one of the following types:

- ``bytes``
- ``str``
- ``int``
- ``float``
- ``bool``
- ``None``
- ``list`` (with the types listed here)
- ``dict`` (with the types listed here)

.. note::
   There is a type hint in ``hisock.utils`` called ``Sendable`` which has these.

The type that the data gets type-casted to depends on the type hint for the message argument for the function for the event receiving the data. If there is no type hint for the argument, the data received will be bytes.

Here are a few examples this server-side code block:

.. code-block:: python

   @server.on("string_sent")
   def on_string_sent(client_data, message: str):
       """``message`` will be of type ``string``"""
       ...

   @server.on("integer_sent")
   def on_integer_sent(client_data, integer: int):
      """``integer`` will be of type ``int``"""
      ...

   @server.on("dictionary_sent")
   def on_dictionary_sent(client_data, dictionary: dict):
      """``dictionary`` will be of type ``dict``"""
      ...

.. note::
   Although these examples are on the server-side, they work the exact same for the client-side.

Of course, you need to be careful that the type-casting will work. Turning ``b"hello there"`` to ``int`` will fail.

----

=================
Dynamic arguments
=================
Remember where I said the ``on`` decorator will call the function with a *maximum* number of parameters?

In :mod:`HiSock` with an _unreserved_ event, the function to handle it can be called with the maximum number of parameters *or less*. Note that in a reserved event, dynamic arguments doesn't apply.

As an example, for the server: If an event has 1 argument, it will only be called with the client data. If it has 2 arguments, it will be called with the client data and the message. If it has 0 arguments, it'll be called as a void (no arguments).

Data can be sent similarly. If there is no data sent, the server will receive the equivalent of ``None`` for the type-casted data.

Here are a few examples of this with a server-side code block.

.. code-block:: python

   @server.on("event1")
   def on_event1(client_data, message: str):
       print(f"I have {client_data=} and {message=} as a string!")

   @server.on("event2")
   def on_event2(client_data, message: int):
       print(f"I have {client_data=} and {message=} as an integer! {message+1=}")

   @server.on("event3")
   def on_event3(client_data):
       print(f"I only have {client_data=}!")

   @server.on("event4")
   def on_event4():
       print("I have nothing.")

Here is an example with a client-side code block that ties into the server-side code block above:

.. code-block:: python

   client.send("event1", "Hello")  # Server will receive "Hello"
   client.send("event1")  # Server will receive an empty string
   client.send("event2", b"123")  # Server will receive 123 and output 124
   client.send("event2")  # Server will receive 0 and output 1
   client.send("event3", "there")  # Server won't receive "there"
   client.send("event4", "Hi")  # Server won't receive anything


----

Conclusion
----------

Now, you know how to:

- Create a server
- Create a client
- Transmit data
- Work with dynamic arguments
- Handle datatypes transmitted
- Do stuff with the data

Have fun HiSock-ing!