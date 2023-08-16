import glob
import hashlib
import io
import logging
import os

import pytest
import yaml
from jsonschema import ValidationError

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
    snapshots_dir = os.path.join(os.path.dirname(__file__), "snapshots", "amix", "run")
    snapshot.snapshot_dir = snapshots_dir
    for fixture in fixtures:
        test_name = os.path.splitext(os.path.basename(fixture))[0]

        Amix.create(
            fixture,
            os.path.join(os.path.dirname(__file__), "tmp"),
            True,
            name=test_name,
        ).run()

        snapshot.assert_match(
            _sha1_checksum(
                os.path.join(os.path.dirname(__file__), "tmp", test_name + ".wav")
            ),
            os.path.join(snapshots_dir, test_name + ".wav.snapshot"),
        )


def test_run_cleanup():
    """Test Amix().run cleanup"""
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "basic.yml")
    output = os.path.join(os.path.dirname(__file__), "tmp")
    test_name = "cleanup"
    tmp_dir = os.path.join(output, test_name, "tmp")

    Amix.create(fixture, output, True, name=test_name, keep_tempfiles=False).run()
    assert os.path.exists(tmp_dir) == False

    Amix.create(fixture, output, True, name=test_name, keep_tempfiles=True).run()
    assert os.path.exists(tmp_dir) == True


def test_run_wrong_filter():
    """Test Amix().run wrong filter"""
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "fade_filter.yml")
    output = os.path.join(os.path.dirname(__file__), "tmp")
    test_name = "wrong_filter"

    a = Amix.create(fixture, output, True, name=test_name)
    a.definition["filters"][0]["type"] = test_name

    with pytest.raises(Exception):
        a.run()


def test_create(snapshot):
    """Test Amix.create"""
    definition = os.path.join(os.path.dirname(__file__), "fixtures", "basic.yml")
    output = os.path.join(os.path.dirname(__file__), "tmp")
    fixtures = [
        ("basic", {}),
        ("parts_from_clips", {"parts_from_clips": True}),
        ("clip_empty", {"clip": [], "alias": []}),
        (
            "clip_dir",
            {"clip": [os.path.join(os.path.dirname(__file__), "fixtures", "clips")]},
        ),
        (
            "clip_file",
            {
                "clip": [
                    os.path.join(
                        os.path.dirname(__file__), "fixtures", "clips", "bass.wav"
                    )
                ]
            },
        ),
        (
            "clip_no_dir",
            {"clip": [os.path.join(os.path.dirname(__file__), "fixtures", "test")]},
        ),
        (
            "clip_no_file",
            {
                "clip": [
                    os.path.join(
                        os.path.dirname(__file__), "fixtures", "clips", "test.wav"
                    )
                ]
            },
        ),
    ]
    snapshots_dir = os.path.join(
        os.path.dirname(__file__), "snapshots", "amix", "create"
    )
    snapshot.snapshot_dir = snapshots_dir
    for test_name, fixture in fixtures:
        snapshot.assert_match(
            yaml.dump(Amix.create(definition, output, **fixture).definition),
            os.path.join(snapshots_dir, test_name + ".yml.snapshot"),
        )


def test_create_with_template(snapshot):
    definition = os.path.join(
        os.path.dirname(__file__), "fixtures", "templates", "data.yml.j2"
    )
    output = os.path.join(os.path.dirname(__file__), "tmp")
    fixtures = [
        ("basic", {"data": ["tempo=1.2", "pitch=0.9", "bars=8"]}),
    ]
    snapshots_dir = os.path.join(
        os.path.dirname(__file__), "snapshots", "amix", "create_with_template"
    )
    snapshot.snapshot_dir = snapshots_dir
    for test_name, fixture in fixtures:
        snapshot.assert_match(
            yaml.dump(Amix.create(definition, output, **fixture).definition),
            os.path.join(snapshots_dir, test_name + ".yml.snapshot"),
        )


def test_create_with_loglevel():
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "basic.yml")
    output = os.path.join(os.path.dirname(__file__), "tmp")
    a = Amix.create(fixture, output, True)
    assert a.loglevel == "error"

    a = Amix.create(fixture, output, True, loglevel=logging.DEBUG)
    assert a.loglevel == "debug"

    a = Amix.create(fixture, output, True, loglevel=logging.INFO)
    assert a.loglevel == "info"


def test_create_with_validation_error(snapshot):
    definition = os.path.join(
        os.path.dirname(__file__), "fixtures", "templates", "data.yml.j2"
    )
    output = os.path.join(os.path.dirname(__file__), "tmp")
    with pytest.raises(ValidationError):
        Amix.create(
            definition,
            output,
            **{
                "clip": [os.path.join(os.path.dirname(__file__), "fixtures", "clips")],
                "data": ["tempo=1.2", "pitch=0.9", "bars='8'"],
            }
        )
