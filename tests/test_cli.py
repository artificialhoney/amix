import os
import sys
from unittest.mock import MagicMock

import pytest
import yaml

from amix.amix import Amix
from amix.cli import run

__author__ = "Sebastian Krüger"
__copyright__ = "Sebastian Krüger"
__license__ = "MIT"


def test_run(snapshot):
    """Test CLI().run"""
    snapshots_dir = os.path.join(os.path.dirname(__file__), "snapshots", "cli")
    snapshot.snapshot_dir = snapshots_dir
    basic_fixture_path = os.path.join("fixtures", "basic.yml")
    output = "tmp"

    fixtures = [("basic", []), ("debug", ["-vv"])]
    for test_name, fixture in fixtures:
        Amix.create = MagicMock()
        sys.argv = ["test", basic_fixture_path, "-o", output] + fixture
        run()

        snapshot.assert_match(
            yaml.dump(Amix.create.call_args.args),
            os.path.join(snapshots_dir, test_name + ".yml.snapshot"),
        )
