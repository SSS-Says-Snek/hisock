Intermediate-level Tutorial
===========================

In this "tutorial", I'll talk about some more advanced topics that I *may*
have mentioned in the quickstart, but never talked about it. These topics
are extremely important in order to develop a complex :mod:`hisock` application.

Without further adieu, let's start!

Where we left off
-----------------

In the quickstart tutorial, we left off knowing how to send data from server to client,
and client to server. While there is nothing much to the client-to-server interaction,
with only one method ``.send()``, there are **FIVE** methods for a server-to-client
interaction; :meth:`.send_client()`, :meth:`.send_all_clients()`,
:meth:`.send_client_raw()`, :meth:`.send_group()`, and
:meth:`.send_group_raw()`. While we have covered the most obvious one (:meth:`send_client()`),
we have not yet covered the other two.

Names and groups
----------------

Now, I'll clear up some more stuff before we move on. Hisock provides what I like to call
**names** and **groups**. Under-the-hood, ``hisock`` usually identifies clients and servers
by their **IP Address**. This works most of the times, but sometimes, you want to differentiate
between clients, *without* knowing the IP. This is where names come in; On client connection,
you can pass a ``name`` argument into :func:`connect`, as to bind a name to the client. Now,
using some additional functions, we could send and receive data by using the client name!
The other ``send`` methods
--------------------------

