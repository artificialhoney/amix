====
amix
====

.. image:: https://img.shields.io/pypi/v/amix.svg
    :alt: PyPI-Server
    :target: https://pypi.org/project/amix/
.. image:: https://static.pepy.tech/badge/amix/month
    :alt: Monthly Downloads
    :target: https://pepy.tech/project/amix
.. image:: https://github.com/artificialhoney/amix/actions/workflows/test.yml/badge.svg
   :alt: Test
   :target: https://github.com/artificialhoney/amix/actions/workflows/test.yml
.. image:: https://img.shields.io/coveralls/github/artificialhoney/amix/main.svg
    :alt: Coveralls
    :target: https://coveralls.io/r/artificialhoney/amix
.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
    :alt: License MIT
    :target: https://opensource.org/licenses/MIT
.. image:: https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold
    :alt: Project generated with PyScaffold
    :target: https://pyscaffold.org/

Automatic mix of audio clips.

Read more: `https://artificialhoney.github.io/amix <https://artificialhoney.github.io/amix>`_

------------
Installation
------------

Make sure, to have **ffmpeg** installed.

.. code-block:: bash

    pip install amix


-----
Usage
-----

Please check first of all the help function.

.. code-block:: bash

    amix --help

Also make sure to always obtain the latest version.

.. code-block:: bash

    amix --version

Render audio from the definition file ``amix.yml`` in the current working directory to disc.

.. code-block:: bash

    amix

Increase verbosity to also output the ``ffmpeg`` logging.

.. code-block:: bash

    amix -vv

Automatically create parts from clips.

.. code-block:: bash

    amix --parts_from_clips
