Changelog
=========

This page keeps track of all the new features that were added to, modified,
or removed in specific versions. This may be useful for selecting which version is
best for you, if the latest version does not work for you.

.. _v1p1:

v1.1
----

New features
~~~~~~~~~~~~

- A message cache for HiSockClient! The message cache allows you to view the last x messages sent by the client. Configuration of the message cache is available on creation of the instance.
- ``.disconnect_client()``, ``.disconnect_all_clients()``, and ``.close()`` methods for HiSockServer, as well as the ``force_disconnect`` reserved function for HiSockClient! It's now easier to force disconnect of a client from a server with these functions. The ``force_disconnect`` reserved function will be triggered when the client has been disconnected from the server with these functions.
- Add list and dict type casts for HiSockClient.

Improved features
~~~~~~~~~~~~~~~~~

- Documentation improvements, yay!
- Handle hisock errors better (not crashes!). New exceptions have been created for specific causes of server/client errors.
- cleancode.py can now clean up the code, with the help of black! So, the code has been PEP8-ified, for our (my) avid PEP8 fans.
- Move HiSockClient and HiSockServer to be available on import of hisock.
- Move __version__ to be available on import of hisock.
- Separate requirements.txt into that and requirements_contrib.txt. Some of the requirements are actually just requirements for the tests to run.

Bug fixes
~~~~~~~~~

- (Maybe) fix bug for the .close() method of HiSockClient.
- Fixed a fatal import error of hisock.

Other
~~~~~

Hisock now has a new logo, created by sheepy0125!
Hisock also has a discord server! However, we're (I'm) still setting it up, so the invite isn't public yet.

.. _v1p0:

v1.0
----

New features
~~~~~~~~~~~~

- New examples have been added to hisock! Now, you can play a Tic-Tac-Toe game made in hisock! There is also the addition of the example shown in the README
- HiSockClient, HiSockServer, and their threaded counterparts now support some dunder methods!
- More type casts have been added
- Ability to change name and group after client initialization has been added (change_name() and change_group())
- A built-in way to obtain server and client configuration through inputs has been added (input_server_config() and input_client_config())

Improved features
~~~~~~~~~~~~~~~~~

- Of course, we have some documentation improvements!
- Pictures are starting to appear in the documentation
- I added a beginner's tutorial to get started on hisock
- I am currently working on another intermediate hisock tutorial, which covers the more advanced topics
- A new changelog page has been added
- Python docstrings have been improved
- Hisock error handling has been improved again
- Added classifiers in PyPI

Bug fixes
~~~~~~~~~

- The regular expression used in 0.1 and earlier has been replaced with a newer one, in order to respond against certain edge cases
- Bumped cryptography module from 3.4.8 to 35.0.0 (security patches)

.. _v0p1:

v0.1
----

This version is the first minor version of ``hisock``! It contains several major code
accessibility things added, though not a lot of in-usage code has been added in this version.

New features
~~~~~~~~~~~~

- PyPI installation of hisock (``python -m pip install hisock`` or ``pip3 install hisock``)
- Documentation for ``hisock``, hosted here! (ReadTheDocs)
- New support for threaded ``HiSockServer`` and ``HiSockClient``

Improved features
~~~~~~~~~~~~~~~~~

- Better traceback handling

.. _v0p0p1:

**v0.0.1 (GRAND RELEASE)**
--------------------------

The first version of hisock! Contains all the basics of what hisock can do, including:

- Name/Group feature to identify specific clients
- Decorators to handle message receiving
- Under-the-hood code that handles headers
- Type-casting receiving function arguments
