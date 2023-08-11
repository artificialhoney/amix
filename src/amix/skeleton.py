import argparse
import glob
import json
import logging
import os
import sys

import jsonschema
import yaml
from jinja2 import Template

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


def parse_args(args):
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
        default=[os.path.join(os.getcwd(), "clips")],
    )
    parser.add_argument(
        "-a", "--alias", help="Alias name for audio clip file", nargs="*", default=[]
    )
    parser.add_argument("-o", "--output", help="Amix output audio file")
    parser.add_argument(
        "-d", "--data", help="Variables set to fill definition", nargs="*"
    )
    parser.add_argument(
        "-y",
        "--yes",
        help="Overwrite output files without asking.",
        action="store_true",
    )

    return parser.parse_args(args)


def setup_logging(loglevel):
    """
    Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
    logging.basicConfig(
        level=loglevel, stream=sys.stdout, format=logformat, datefmt="%Y-%m-%d %H:%M:%S"
    )


def main(args):
    """
    Wrapper allowing :func:`amix` to be called with string arguments in a CLI fashion

    """
    args = parse_args(args)
    setup_logging(args.loglevel)
    _logger.info("Starting amix")

    with open(args.definition) as f:
        definition = yaml.safe_load(f)
        if args.data != None:
            data = {}
            for d in args.data:
                split = d.split("=")
                key = split[0]
                val = split[1]
                data[key] = val

            if "original_tempo" in definition:
                template = Template(definition["original_tempo"])
                definition["original_tempo"] = float(template.render(data))

            if "bars" in definition:
                template = Template(definition["bars"])
                definition["bars"] = float(template.render(data))

            if "tempo" in definition:
                template = Template(definition["tempo"])
                definition["tempo"] = float(template.render(data))

            if "pitch" in definition:
                template = Template(definition["pitch"])
                definition["pitch"] = float(template.render(data))

            for part in definition["parts"].values():
                if "bars" in part:
                    template = Template(part["bars"])
                    part["bars"] = float(template.render(data))

                for clip in part["clips"]:
                    if "bars" in clip:
                        template = Template(clip["bars"])
                        clip["bars"] = float(template.render(data))

            for filter in definition["filters"]:
                for field in ["duration", "from", "to"]:
                    if field in filter:
                        template = Template(filter[field])
                        filter[field] = float(template.render(data))

        clips = {}
        types = ("*.mp3", "*.wav", "*.aif")
        index = 0

        if args.clip and len(args.clip) > 0:
            for file in args.clip:
                file = os.path.realpath(file)
                if os.path.isdir(file):
                    files_grabbed = []
                    for t in types:
                        files_grabbed.extend(glob.glob(os.path.join(file, t)))
                    for f in files_grabbed:
                        if os.path.isfile(f):
                            path = f
                            name = (
                                os.path.splitext(os.path.basename(f))[0]
                                if index not in args.alias
                                else args.alias[index]
                            )
                            index += 1
                            clips[name] = path
                elif os.path.isfile(file):
                    path = file
                    name = (
                        os.path.splitext(os.path.basename(file))[0]
                        if index not in args.alias
                        else args.alias[index]
                    )
                    index += 1
                    clips[name] = path

        if not "clips" in definition:
            if len(clips.values()) > 0:
                definition["clips"] = clips
            else:
                definition["clips"] = {}
        elif len(clips.values()) > 0:
            definition["clips"] = definition["clips"] | clips

    try:
        with open(os.path.join(os.path.dirname(__file__), "amix.json")) as f:
            schema = json.load(f)
        jsonschema.validate(definition, schema)
        Amix(definition, args.output, args.yes, args.loglevel).run()
        _logger.info("Done amix")
    except jsonschema.exceptions.ValidationError:
        _logger.exception("Error while parsing amix definition file")


def run():
    """
    Calls :func:`main` passing the CLI arguments extracted from :obj:`sys.argv`
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
