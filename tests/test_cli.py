import os
from unittest.mock import MagicMock

import pytest
import yaml

from amix.amix import Amix
from amix.cli import CLI

__author__ = "Sebastian Krüger"
__copyright__ = "Sebastian Krüger"
__license__ = "MIT"


def test_run(snapshot):
    """Test CLI().run"""
    snapshots_dir = os.path.join(os.path.dirname(__file__), "snapshots", "cli")
    snapshot.snapshot_dir = snapshots_dir

    fixtures = [("basic", []), ("debug", ["-vv"])]
    for test_name, fixture in fixtures:
        Amix.create = MagicMock()
        CLI().run([os.path.join("fixtures", "basic.yml")] + fixture)

        snapshot.assert_match(
            yaml.dump(Amix.create.call_args.args),
            os.path.join(snapshots_dir, test_name + ".yml.snapshot"),
        )
