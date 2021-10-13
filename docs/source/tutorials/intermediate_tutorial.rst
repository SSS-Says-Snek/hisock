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

.. image:: ../imgs/intermed_tut/name.png
   :width: 400

Now, on to groups. Like names, groups are another way of identifying a client, but instead of **one**
client, it can identify multiple! With groups, you can organize clients by what they correspond to. For example,
if you are making a multiplayer game, and you are making some sort of lobby for a limited number of clients,
then a group would be a good way to identify which clients are in which lobby.

.. note::
   I've actually never used groups before, which is pretty... uh... sad. I added groups because
   I thought of some use cases for it, but I never bothered to use it in an example, so... yeah.

Now, let's finally dig into the ``send`` methods!


The other ``send`` methods
--------------------------

In the beginner tutorial, we've covered the :meth:`.send_client()` method that allows the server to
send data to specific clients. But, what if we wanted to send data to all the clients? Well, that
is exactly what :meth:`.send_all_clients()` does. Yes, the name is pretty self-explanatory.

Now, let's move on to :meth:`.send_client_raw()`! Sometimes, while you do want to send data to a client,
you don't necessarily want to send it **with a command**. For example, if a server just sent out information to
a client, and a client sent back some more information, it would be much easier to directly send data to
the client, instead of sending a command, and needing to make another function. So, :meth:`.send_client_raw()`
allows you to send data *without a command*.

Remember when I said that groups can be used to organize clients? Well, how do we communicate and send
data to a group? As you may have guessed by the name, :meth:`.send_group()` sends data to a specific group,
taking a group name and the data as parameters.