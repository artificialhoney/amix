import argparse
import logging
import os
import sys

from amix import __version__

from .amix import Amix

__author__ = "Sebastian Krüger"
__copyright__ = "Sebastian Krüger"
__license__ = "MIT"

_logger = logging.getLogger(__name__)

# ---- CLI ----
# The functions defined in this section are wrappers around the main Python
# API allowing them to be called directly from the terminal as a CLI
# executable/script.


class CLI:
    def parse_args(self, args):
        """
        Parse command line parameters
        """
        parser = argparse.ArgumentParser(description="Automcatic mix of audio clips")
        parser.add_argument(
            "--version",
            action="version",
            version=f"amix {__version__}",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            dest="loglevel",
            help="set loglevel to INFO",
            action="store_const",
            const=logging.INFO,
        )
        parser.add_argument(
            "-vv",
            "--very-verbose",
            dest="loglevel",
            help="set loglevel to DEBUG",
            action="store_const",
            const=logging.DEBUG,
        )

        parser.add_argument(
            "definition",
            help="Amix definition file",
            nargs="?",
            default=os.path.join(os.getcwd(), "amix.yml"),
        )

        parser.add_argument(
            "-c",
            "--clip",
            help='Amix input audio clip file or folder ("*.mp3", "*.wav", "*.aif")',
            nargs="*",
            default=["clips"],
        )
        parser.add_argument(
            "-a",
            "--alias",
            help="Alias name for audio clip file",
            nargs="*",
            default=[],
        )
        parser.add_argument(
            "-o", "--output", help="Amix output audio file", default=os.getcwd()
        )
        parser.add_argument(
            "-d", "--data", help="Variables set to fill definition", nargs="*"
        )
        parser.add_argument(
            "-k",
            "--keep_tempfiles",
            help="Don't clean up keep temp files",
            action="store_true",
        )
        parser.add_argument("-n", "--name", help="Overwrite name in config")
        parser.add_argument(
            "-p",
            "--parts_from_clips",
            help="Create parts from clips",
            action="store_true",
        )
        parser.add_argument(
            "-y",
            "--yes",
            help="Overwrite output files without asking.",
            action="store_true",
        )

        return parser.parse_args(args)

    def setup_logging(self, loglevel):
        """
        Setup basic logging

        Args:
        loglevel (int): minimum loglevel for emitting messages
        """
        logformat = "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
        logging.basicConfig(
            level=loglevel,
            stream=sys.stdout,
            format=logformat,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def run(self, args):
        """
        Wrapper allowing :func:`amix` to be called with string arguments in a CLI fashion
        """
        args = self.parse_args(args)
        self.setup_logging(args.loglevel)
        _logger.info("Starting amix")

        Amix.create(
            args.definition,
            args.output,
            args.yes,
            args.loglevel,
            args.keep_tempfiles,
            args.clip,
            args.data,
            args.alias,
            args.name,
            args.parts_from_clips,
        ).run()

        _logger.info("Done amix")


def run():
    """
    Calls :func:`main` passing the CLI arguments extracted from :obj:`sys.argv`
    """
    CLI().run(sys.argv[1:])


if __name__ == "__main__":
    run()
