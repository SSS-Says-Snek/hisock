Installation
============

To install :mod:`HiSock`, you will need to make sure you have PIP and Python3.7 or later installed and added to your PATH (ensure ``pip`` and ``python`` works).
There are two main ways to install :mod:`HiSock`. You can install it through `PyPi <https://pypi.org/project/hisock/>`_ (recommended) or you can install it from the GitHub.

.. warning::
    :mod:`HiSock` is the first project I ever published to PyPI, so there might be some
    quirks on PyPI here and there, like the sudden burst of version post-releases.
    However, I will try to keep this at the bare minimum, and hopefully figure out
    PyPI good enough.

Installing via PyPI
-------------------

The recommended way to install a stable version of :mod:`HiSock` is through PyPI. To install hisock, open a terminal/command prompt and type:

.. code-block:: console
   
    $ python -m pip install hisock (Windows)
        OR
    $ pip install hisock (Windows)
        OR
    $ python3 -m pip install hisock (Mac/Linux)
        OR
    $ pip3 install hisock (Mac/Linux)

You've now successfully installed a stable version of :mod:`HiSock`!

Installing via GitHub
---------------------

Sometimes, however, you might want to install the *latest* version of :mod:`HiSock`, not just the *stable* version. To do this, you can either download the repository from GitHub `here <https://github.com/SSS-Says-Snek/hisock/>`_ or you can clone the repository (recommended) via Git.

To install from Git, open a terminal/command prompt and type:

.. code-block:: console

    $ git clone https://github.com/SSS-Says-Snek/hisock.git (Git)
        OR
    $ gh repo clone SSS-Says-Snek/hisock (GitHub CLI)

Or, you can go onto GitHub and download the ZIP file by pressing the green "Code" button, then clicking "Download ZIP". You can then unzip the file into a folder with your favorite unzip tool.

Then, go back to the terminal or command prompt and type:

.. code-block:: console

    $ cd hisock

After you're now in the working directory of the repo, install it in editable mode with:

.. code-block:: console

    $ pip install -e .

You should now have successfully installed the latest version of :mod:`HiSock`! 
If this doesn't work, then try one of the alternatives in Method 1, but replace ``hisock`` with ``-e .`` (E.g ``python3 -m pip install -e .``)

.. note::
   
   If you want to check if :mod:`HiSock` is *actually* installed, run this command in your terminal or command prompt:

   .. code-block:: console
       
       $ python -c $'try:\n\timport hisock;print(f"Hisock {hisock.constants.__version__} successfully installed")\nexcept Exception as e:print(f"Failed to install hisock for {e} reason")'

