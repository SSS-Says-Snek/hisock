Understanding :mod:`HiSock`
===========================

What is :mod:`HiSock`? What is it not?
--------------------------------------

The TL;DR of this all is:

:mod:`HiSock` is a higher-level extension of the socket Python module with simpler and more efficient uses.

:mod:`HiSock` is not a replacement for sockets nor a new network protocol. It doesn't work through a "request/response" method.

Now, if you're new to this, most likely you will have no idea what any of this means. But, that's okay! The goal of this section is to help you understand.

What is the :mod:`socket` module? How does it relate to :mod:`HiSock`?
----------------------------------------------------------------------

Let's focus on what :mod:`HiSock` is built on, :mod:`socket`.

:mod:`socket` is a low-level networking interface that uses "sockets" to communicate between computers over a network. In sockets, when you send data, you need to send a "header" first. Before you even send your data, you need to send some other data telling how long that data is. Along with that, :mod:`socket` is pretty barebone.
So, I developed :mod:`HiSock`, which simplifies :mod:`socket` down and provides additional features.

:mod:`HiSock` focuses on abstracting the complex parts of sockets so you can focus on what you actually want to do. It does this through managing headers on its own, "type-casting" everything so you don't have to convert data to bytes and back, event-driven architecture with decorators, threading, data streams, and more. Basically, it's everything :mod:`socket` can do, minus the boilerplate code you have to write every time.

How do you send and receive data with :mod:`HiSock`?
----------------------------------------------------

Data sent with :mod:`HiSock` usually has a *command* before the data. Once the command is sent, it can be received using decorators ``HiSock.server.on`` and ``HiSock.client.on``. An argument will be passed in those decorators, which will be the data.

But what data can be sent? Sockets work with bytes, but most times, you don't just want bytes. As touched on earlier, :mod:`HiSock` comes with a type-cast system
