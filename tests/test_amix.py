import glob
import hashlib
import io
import logging
import os

import pytest
import yaml

from amix.amix import Amix

__author__ = "Sebastian Krüger"
__copyright__ = "Sebastian Krüger"
__license__ = "MIT"


def _sha1_checksum(data: (str, bytearray, bytes, io.BufferedReader, io.FileIO)) -> str:
    """
    create sha1 checksum
    :param data: input data to check sha1 checksum
    :type data: str, bytearray, bytes, io.BufferedReader, io.FileIO
    :return: sha1 hash
    :rtype: str
    """
    # byte
    if isinstance(data, (bytes, bytearray)):
        return hashlib.sha1(data).hexdigest()

    # file
    elif isinstance(data, str) and os.access(data, os.R_OK):
        return hashlib.sha1(open(data, "rb").read()).hexdigest()

    # file object
    elif isinstance(data, (io.BufferedReader, io.FileIO)):
        return hashlib.sha1(data.read()).hexdigest()

    # string
    elif isinstance(data, str):
        return hashlib.sha1(data.encode()).hexdigest()

    else:
        raise ValueError("invalid input. input must be string, byte or file")


def test_run(snapshot):
    """Test Amix().run"""
    fixtures = glob.glob(os.path.join(os.path.dirname(__file__), "fixtures", "*.yml"))
    for fixture in fixtures:
        test_name = os.path.splitext(os.path.basename(fixture))[0]
        snapshots_dir = os.path.join(os.path.dirname(__file__), "snapshots")

        Amix.create(
            fixture,
            os.path.join(os.path.dirname(__file__), "tmp"),
            True,
            name=test_name,
        ).run()

        snapshot.snapshot_dir = snapshots_dir
        snapshot.assert_match(
            _sha1_checksum(
                os.path.join(
                    os.path.dirname(__file__), "tmp", test_name + " (main).wav"
                )
            ),
            os.path.join(snapshots_dir, test_name + ".wav") + ".snapshot",
        )


def test_create(snapshot):
    """Test Amix.create"""
    fixtures = glob.glob(os.path.join(os.path.dirname(__file__), "fixtures", "*.yml"))
    for fixture in fixtures:
        test_name = os.path.splitext(os.path.basename(fixture))[0]
        snapshots_dir = os.path.join(os.path.dirname(__file__), "snapshots")

        snapshot.snapshot_dir = snapshots_dir
        snapshot.assert_match(
            yaml.dump(
                Amix.create(
                    fixture, os.path.join(os.path.dirname(__file__), "tmp"), True
                ).definition
            ),
            os.path.join(snapshots_dir, test_name + ".yml") + ".snapshot",
        )
