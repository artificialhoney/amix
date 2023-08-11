.. These are examples of badges you might want to add to your README:
   please update the URLs accordingly

    .. image:: https://api.cirrus-ci.com/github/<USER>/amix.svg?branch=main
        :alt: Built Status
        :target: https://cirrus-ci.com/github/<USER>/amix
    .. image:: https://readthedocs.org/projects/amix/badge/?version=latest
        :alt: ReadTheDocs
        :target: https://amix.readthedocs.io/en/stable/
    .. image:: https://img.shields.io/coveralls/github/<USER>/amix/main.svg
        :alt: Coveralls
        :target: https://coveralls.io/r/<USER>/amix
    .. image:: https://img.shields.io/pypi/v/amix.svg
        :alt: PyPI-Server
        :target: https://pypi.org/project/amix/
    .. image:: https://img.shields.io/conda/vn/conda-forge/amix.svg
        :alt: Conda-Forge
        :target: https://anaconda.org/conda-forge/amix
    .. image:: https://pepy.tech/badge/amix/month
        :alt: Monthly Downloads
        :target: https://pepy.tech/project/amix
    .. image:: https://img.shields.io/twitter/url/http/shields.io.svg?style=social&label=Twitter
        :alt: Twitter
        :target: https://twitter.com/amix

.. image:: https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold
    :alt: Project generated with PyScaffold
    :target: https://pyscaffold.org/

|

=======
amix
=======

Automatic mix of audio clips.

------------
Installation
------------

Make sure, to have **ffmpeg** installed.

.. code-block::

    pip install amix


-----
Usage
-----

Check out the `examples` folder. I also uploaded my result to SoundCloud_.

.. _SoundCloud: https://soundcloud.com/honeymachine/sets/street-parade


.. code-block::

    cd examples/mannheim && amix

.. code-block::

    cd examples/milano && amix -vv

.. code-block::

    cd examples/heidelberg && amix --data "full=8" "half=4" "from=7.825" "tempo=0.538" "pitch=1.1" "original_tempo=180"
