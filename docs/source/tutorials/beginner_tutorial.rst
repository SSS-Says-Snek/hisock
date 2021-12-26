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
  - An example of a client sending data that a server writes to a text file and the server broadcasts to all clients connected.

.. note::
   For this tutorial, I will be referring the IP addresses as ``hisock.utils.get_local_ip()``. In reality, you will most likely use a hard-coded IP address from a user input.

.. note::
    When I refer to "a way to identify the client", I am talking about either:
     - a tuple of the IP address and port of the client,
     - a string of the IP address and port of the client, or
     - a string of the client's name (this will cause confusion if two clients share the same name)

Creating our first server
-------------------------

In :mod:`HiSock`, there is a function to create a :class:`HiSockServer` instance which is :meth:``start_server()``. This function is called with one parameter, which is a tuple. The tuple will contain the IP address to start the server on (most likely the local IP address) and the port to start the server on. To find the local IP address, there is a function called :meth:``utils.get_local_ip()``. For the port, a number between 1024 and 65535 *should* be fine.

:class:`HiSockServer` instances have a ``run()`` method to them, which should be called constantly. This allows the server to listen for commands and data being sent.

.. code-block:: python

   import hisock

   server = hisock.start_server((hisock.utils.get_local_ip(), 6969))

   while True:
       server.run()

That's basically it! Of course, this server is useless, but hey, it's a step in the right direction! We'll add on to this later on.

Obviously, without a client, a server is kind of pointless. So, let's spice things up, with some client code!

Creating our first client
-------------------------
In :mod:`HiSock`, there is a function to create a :class:`HiSockClient` instance which is :meth:`hisock.connect`. This needs to be called with two parameters. The first parameter is a tuple of the IP address of the server to connect to and the port is the port that the server is running on. The second parameter is the name of the client. :mod:`HiSock` uses IP addresses and names to identify clients.

Like :class:`HiSockServer`, :class:`HiSockClient` needs to be run constantly to listen to receive data. However, in :class:`HiSockClient`, instead of the :meth:`run()` method, it is called :meth:`update()`. So, our final starter client code is:

.. code-block:: python

   import hisock

   client = hisock.connect(
       (hisock.utils.get_local_ip(), 6969), 
       name=input("What is your name? >"),
    )

   while True:
       client.update()

Like the server, this doesn't do anything at all yet. Next, we will explore sending and receiving data in an example.

Transmitting Data
-----------------

Let's explore transmitting data for :mod:`HiSock`!

:mod:`HiSock` is an event-driven module, and as such, has an ``on`` decorator and a :meth:`send` method for both :class:`HiSockClient` and :class:`HiSockServer`.

==============
Receiving data
==============

When a function is prefaced with the ``on`` decorator, it will run on something. It will "listen" for a command and run when that command is broadcasted.

The ``on`` decorator takes two parameters. One of the parameters is the command to listen on. The second (optional) parameter is whether to run the listener in its own thread or not.

For the server: The ``on`` decorator will send two parameters to the function it is decorating (there are a few exceptions we will touch on). The first parameter is the client data. It is a dictionary that includes the client's name, client IP address, and the group the client is in (we won't cover groups in this tutorial).

For the client: the ``on`` decorator will send a single parameter to the function it is decorating, which will be the message the client sends (in most cases).

Here's an example with the ``on`` decorator in use in a server. Here, the server has a command, ``print_message_name``, and will print the message that it gets and who sent it.

.. code-block:: python

   server = ...

   @server.on("print_message_name")
   def on_print_message_name(client_data: dict, message: str):
       print(f'{client_data["name"]} sent "{message}"')

   while True:
       ...

Here's another example with receiving data, this time on the client-side. The client will receive a command, ``greet``, with a name. It will then print out a greeting with the name.

.. code-block:: python
   
   client = ...

   @client.on("greet")
   def on_greet(name: str):
       print(f"Hello there, {name}!")

   while True:
       ...

If the ``threaded`` parameter for the ``on`` decorator is true, then the function being decorated will run in a separate thread. This allows blocking code to run while still listening for updates.

It is useful if you want to get user input but also want to have the user receive other data.

.. code-block:: python
     
   client = ...

   @client.on("ask_question", threaded=True)
   def on_ask_question(question: str):
       answer = input(f"Please answer this question: {question}\n>")
       answer_bytes = answer.encode()
       # ... send answer to server ...
    
   @client.on("important")
   def on_important(message: str):
       """ This is important and cannot be missed! """
       ...
    
   while True:
       ...

============
Sending data
============
.. note::
    This is likely going to be updated soon. Due to complications with having different :meth:`send` methods, it is likely to be put in one big ``send`` class. However, for now, this is correct.

:mod:`HiSock` has multiple send functions. For now, we will be talking about sending to the server from the client or to one client from the server.

For the server:

Sending data from the server to a client in :mod:`HiSock` uses the :meth:`send_client` method. This method takes in three parameters. The three parameters (in order) are a way to identify the client, the command to send, and the message being sent.

Although we won't be talking about it here, :meth:`send_all_clients` does exactly what it says. It will do :meth:`send_client` to all the clients that are connected.

.. _sending-data-data-must-be:
As touched on a little in :doc:`/quickstart/understanding_hisock`, the message being sent **must** be either:
 - a dictionary or
 - a bytes-like object

We will learn more about how datatypes work in :mod:`HiSock` later on.

===============
Reserved events
===============

As I stated before, not every receiver has two parameters passed to it. Here are the cases where that is the case. Wow, I said case twice in a row. I'm so original.

:mod:`HiSock` has reserved events. These events shouldn't be sent by the client or server explicitly as it is currently unsupported.

.. note::
    All of these events work like normal events with type-casting.

Here is a list of the reserved events:
 - ``join``
  
    The client sends the event ``join`` when they connect to the server. The only parameter sent to the function being decorated is the client data.
 - ``leave``

    The client sends the event ``leave`` when they disconnect from the server. The only parameter sent to the function being decorated is the client data.
 - ``force_disconnect``

    The server sends the event ``force_disconnect`` to a client when they kick the client. There are *no* parameters sent with the function that is being decorated with this.
 - ``message``

    When the *server* receives a command with data, it'll send an event to itself called ``message`` which will have three parameters. The three parameters (in order) are the client data who sent it, the command that was received, and the message.

============
Type-casting
============
:mod:`HiSock` has a system called "type-casting" when transmitting data.

Data sent must be the types listed in :ref:`Sending Data <sending-data-data-must-be>`, however, when it is received, it can be a different type.

The type that the data gets received as depends on the type hint of the message argument for the function being decorated for the decorator for the event.

Here are a few examples this server-side code block:

.. code-block:: python
    
   @server.on("string_sent")
   def on_string_sent(client_data, message: str):
       """ `message` will be of type `string` """
       ... 

   @server.on("integer_sent")
   def on_integer_sent(client_data, integer: int):
      """ `integer` will be of type `int` """
      ...

   @server.on("dictionary_sent")
   def on_dictionary_sent(client_data, dictionary: dict):
      """ `dictionary` will be of type `dict` """
      ...

.. note::
   Although these examples are on the server-side, they work the exact same for the client-side.

Here are a list of the currently supported type-casts.
 - ``bytes`` -> ``bytes``
 - ``bytes`` -> ``str``
 - ``bytes`` -> ``int``
 - ``bytes`` -> ``dict``
 - ``dict`` -> ``dict``
 - ``dict`` -> ``bytes``

This means that if the first type is sent and the second type is type-hinted, the second type will be what it receives.

Of course, you need to be careful that the type-casting will work. Turning ``b"hello"`` to ``int`` will fail.

Conclusion
----------

Now, you know how to:
 - Create a server
 - Create a client
 - Transmit data
 - Handle datatypes transmitted
 - Doing stuff with the data

========
Exercise
========

Here is an exercise for you, the reader!

Create a :mod:`HiSock` client and server. Three clients can connect to the server. Once three clients have connected, the server will allow each client to transmit user input to it, which it will write in a text file. Each client can talk to the server one after another. The server will broadcast the message to every other client and they will display it.

:doc:`Here</examples/beginner-tutorial-exercise>` is how I completed the exercise.
