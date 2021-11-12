Changelog
=========

This page keeps track of all the new features that were added to, modified,
or removed in specific versions. This may be useful for selecting which version is
best for you, if the latest version does not work for you.

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
