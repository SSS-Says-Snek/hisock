Understanding hisock
====================

First of all, what... **IS** hisock? Well, it's
a higher-level extension of the :mod:`socket` module, with simpler and more efficient usages, sure,
but for beginners, it may be a bit confusing.

What is the socket module?
--------------------------

I've mentioned a lot about a :mod:`socket` module in Python a lot, but some of y'all may not know
*what* socket is. Basically, it's a pretty low-level networking interface that
uses "sockets" to communicate between computers over a network. The problem is,
it's a bit overwhelming when you start learning sockets.

So, I developed :mod:`hisock`, which basically simplifies :mod:`socket` down, and provides additional features.

What are the advantages of using hisock over socket?
----------------------------------------------------

That's a good question. While :mod:`hisock` is still under development, it aims
to simplify or eliminate some complex parts of the standard :mod:`socket`. For example,
hisock uses decorators to simplify code structure, and eliminates the hassle
of worrying about headers.

.. note::
   Again, some of you may not know what a header is. When you send data, it is not interpreted
   as a "message"; instead of messages, there is a "stream" of data, and the client/server decides
   how many bytes to read from the stream. This creates a problem; how do we know how much of a message
   to read? This is where headers come in. They are basically data the specifies the length of a "message".
   In order for this to work, headers **MUST** be fixed-length, so it is usually padded with spaces.

   Let's say that I decided that my header length would be 16 bytes long. When a client sends me
   some data, it will have that header in front, then the actual content. I would first receive
   the first 16 bytes, and see that it is the number "12", followed by 14 spaces. At this point,
   I know that the "message" is 12 bytes long. So, I receive another 12 bytes, to get the message
   "Hello World!"