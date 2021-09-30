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
with only one method ``.send()``, there are **THREE** methods for a server-to-client
interaction; :meth:`.send_client()`, :meth:`.send_all_clients()`, and
:meth:`.send_client_raw()`. While we have covered the most obvious one (``send_client()``)