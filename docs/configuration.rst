.. _configuration:

=============
Configuration
=============

A sample configuration looks like:

.. code-block:: yaml

    name: DnB
    original_tempo: 180
    parts:
      - name: backbeat_part
        bars: 16
        clips:
          - name: backbeat
    mix:
      - name: intro
        parts:
          - name: backbeat_part

The configuration will be validated against the following schema.

.. jsonschema:: ../src/amix/amix.json#/definitions/amix

.. jsonschema:: ../src/amix/amix.json#/definitions/clip

.. jsonschema:: ../src/amix/amix.json#/definitions/filter

.. jsonschema:: ../src/amix/amix.json#/definitions/part

.. jsonschema:: ../src/amix/amix.json#/definitions/segment

.. jsonschema:: ../src/amix/amix.json#/definitions/reference
