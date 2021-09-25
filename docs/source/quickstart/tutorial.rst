Tutorial
========

In this "tutorial", I'm going to be explaining the basic parts of ``hisock``,
and how to use them to create working programs.

It is also highly encouraged that you read the :doc:`Understanding Hisock <understanding_hisock>`
before reading the tutorial.

.. caution::
   I might explain some things wrong, so if you see something wrong with my
   explanation, I encourage you to try to submit a pull request on Github to
   fix it!

.. note::
   Due to certain reasons, for the client part, I will be referring
   the server's IP as ``utils.get_local_ip()``, the same IP address
   as where the server is hosted at. Of course, in real
   applications, there will either be input for the server IP,
   or a hardcoded server IP

First of all, we need to install hisock. Assuming you have ``pip``,
you can install hisock with either ``python -m pip install hisock`` for
Windows, or ``pip3 install hisock`` for Mac/Linux.
Refer to :doc:`the installation guide <installation>` for more details.

First of all, network structures are divided into *servers* and
*clients*. Servers basically *serve* data, and can also be a mean of
communicating between clients. Clients are just the users that give and receive
the server data.

.. note::
   For example, if you are creating a multiplayer game,
   you can create a *server* that *clients* need to join; once they do, client ``A``
   can ask the server to share some info to client ``B``, and so on and so forth.

Creating our first server
-------------------------

There is a function to create a server in ``hisock``, it is ``hisock.start_server()``.
To host a server, we'd need a tuple with two arguments; the first argument is the IP address
of the server. Hisock provides a way to find your local IP address, with
``hisock.utils.get_local_ip()``. The second argument is the *port* of the server.
I won't go into ports, but usually a number between 1024 and 65535 would suffice.

Hisock servers and clients have a ``run()`` and ``update()`` method respectively,
in order to run correctly. However, you need to run them in a while loop, as to
minimize lag time. So, our final server script looks like:

.. code-block:: python

   from hisock import start_server, utils

   server = start_server((utils.get_local_ip(), 36969))  # Haha funny

   while True:
       server.run()

That's basically it! Of course, this server is useless, but hey, it's a step
in the right direction! We'll add on to this later on.

Creating our first client
-------------------------

Obviously, without a client, a server's kind of pointless. So, let's spice things up,
with some boilerplate client code!

Now, the first thing we need to do, is to connect to the server. We can do that with
hisock's ``connect()`` function. Like ``start_server()``, it takes one tuple as an
argument, with two elements; The first one is the IP of the server, and the second one
is the port of the server.

Also like ``HiSockServer``, ``HiSockClient`` needs to be ran in a while loop. However,
in ``HiSockClient``, instead of the ``run()`` method, it is called ``update()``. So,
our final boilerplate client code is:

.. code-block:: python

   from hisock import connect, utils

   # This is a bit tricky - This will only work on the same computer
   # running the server, as it gets the same IP (unless you port forward)
   client = connect((utils.get_local_ip()), 36969)

   while True:
       client.update()

Like the server, this doesn't do anything at all yet, but soon, we'll
finally add some functionality to the server and client!

Clearing some things up
-----------------------

Let me clear some stuff up first;
data sent with :mod:`hisock` usually has a *command* before the data.
Once the command is sent,
it can be received using decorators ``hisock.server.on`` and ``hisock.client.on``.
An argument will be passed in those decorators that specifies the command to listen data
with those commands. When data with the command attached is found, ``hisock`` will
call that function, and pass in a few arguments regarding message content
(``hisock.server`` will also have an argument about the client data).

Let's start with a decorator example for the server

.. code-block:: python

   server = ...

   @server.on("random_command")
   def random_cmd_handler(clt_data, message):
       # clt_data is a dict of client information
       # message is the data content, in bytes

       print(message)

And an example for the client

.. code-block:: python

   client = ...

   @client.on("another_random_command")
   def handler_thing(message):
       # No clt_data, as server always sends message
       print(message)

Now that we've done that, let's add functionality to our bland server and client!

Adding (some) functionality to our server
---------------------------------------------

So far, we have made a server and client, but it doesn't really *do* anything.
So, it's time to add some functionality, starting with the server!

Now, let's say that we want to print the client's IP on the server side,
whenever the server connects to a client. ``hisock`` provides something I like to call
"reserved functions", where there are certain commands that get attached to data that
occur on very special events. For server, there are 3:

1. ``join`` occurs whenever a client connects

2. ``leave`` occurs whenever a client disconnects

3. ``message`` occurs whever a client sends a "message"

(I mean, they're pretty self-explanatory)

Anyways, we can use the ``join`` reserved function to print the client's IP, like so:

.. code-block:: python

   from hisock import iptup_to_str
   ...
   server = ...

   @server.on("join")
   def clt_join(clt_data):  # Of course, no message on join
       print(
           f"Cool, {iptup_to_str(clt_data['ip'])} joined!
       )  # the IP is stored in a tuple, with a (str IP, int Port) format

   while True:
       server.run()

*Now*, if we run the client on this updated server, we will see the IP address of
the client!