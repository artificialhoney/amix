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


def _setup(_clips):
    clips = {}
    types = ("*.mp3", "*.wav", "*.aif")
    index = 0
    for file in _clips:
        file = os.path.realpath(file)
        if os.path.isdir(file):
            files_grabbed = []
            for t in types:
                files_grabbed.extend(glob.glob(os.path.join(file, t)))
            for f in files_grabbed:
                if os.path.isfile(f):
                    path = f
                    name = os.path.splitext(os.path.basename(f))[0]
                    index += 1
                    clips[name] = path
        elif os.path.isfile(file):
            path = file
            name = os.path.splitext(os.path.basename(file))[0]
            index += 1
            clips[name] = path
        return clips


def test_run(snapshot):
    """Test Amix().run"""
    for name, version in [
        ("mannheim", "amix"),
        ("milano", "amix"),
        ("selectrrronic", "I"),
        ("selectrrronic", "II"),
    ]:
        path = os.path.join(os.path.dirname(__file__), "..", "examples", name)
        test_name = "test_" + name + "_" + version
        with open(os.path.join(path, version + ".yml")) as f:
            definition = yaml.safe_load(f)
            definition["name"] = test_name
            definition["clips"] = _setup([os.path.join(path, "clips")])
        snapshots_dir = os.path.join(os.path.dirname(__file__), "snapshots")

        Amix(
            definition,
            os.path.join(os.path.dirname(__file__), "tmp"),
            False,
            logging.DEBUG,
        ).run()

        snapshot.snapshot_dir = snapshots_dir
        snapshot.assert_match(
            _sha1_checksum(
                os.path.join(
                    os.path.dirname(__file__), "tmp", test_name + " (main).wav"
                )
            ),
            os.path.join(snapshots_dir, test_name + " (main).wav") + ".snapshot",
        )
