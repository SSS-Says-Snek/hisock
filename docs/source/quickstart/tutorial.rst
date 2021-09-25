Tutorial
========

In this "tutorial", I'm going to be explaining the basic parts of ``hisock``,
and how to use them to create working programs.

.. caution::
   I might explain some things wrong, so if you see something wrong with my
   explanation, I encourage you to try to submit a pull request on Github to
   fix it!

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

No category yet
---------------

When you look at the hisock examples, you may see an @ sign before
a function. If you don't know what it is, it's a *decorator*. In simple terms,
a decorator takes in a function, and outputs a modified function. However,
the ``hisock`` decorators don't modify any function; inste