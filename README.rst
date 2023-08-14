====
amix
====

.. image:: https://img.shields.io/pypi/v/amix.svg
    :alt: PyPI-Server
    :target: https://pypi.org/project/amix/
.. image:: https://pepy.tech/badge/amix/month
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

------------
Installation
------------

Make sure, to have **ffmpeg** installed.

.. code-block:: bash

    pip install amix


-----
Usage
-----

I also uploaded my first results to SoundCloud_.

.. _SoundCloud: https://soundcloud.com/honeymachine/sets/street-parade


.. code-block:: bash

    amix

.. code-block:: bash

    amix -vv

.. code-block:: bash

    amix --data "full=8" "half=4" "from=7.825" "tempo=0.538" "pitch=1.1" "original_tempo=180"

.. code-block:: bash

    amix --parts_from_clips III.yml

-------------
Configuration
-------------

You can find the JSON schema here_.

.. _here: https://github.com/artificialhoney/amix/blob/main/src/amix/amix.json


A sample configuration looks like:

.. code-block:: yaml

    name: DnB
    original_tempo: 180
    parts:
        backbeat:
            bars: 16
            clips:
            - name: backbeat
    mix:
        - name: intro0
            parts:
            - name: backbeat
