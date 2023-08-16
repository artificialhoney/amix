import glob
import json
import logging
import math
import os
import random
import shutil
from pathlib import Path

import ffmpeg
import jsonschema
import yaml
from jinja2 import Template

_logger = logging.getLogger(__name__)


class _Clip:
    def __init__(self, name, path):
        self.name = name
        self.path = path

    def load(self):
        file = os.path.realpath(self.path)
        _logger.info('Loading clip "{0}" from "{1}"'.format(self.name, self.path))
        self.input = ffmpeg.input(file)
        self.probe = ffmpeg.probe(file)["streams"][0]
        _logger.debug('Probe for clip "{0}" is "{1}"'.format(self.name, self.probe))


class Amix:
    """
    Amix itself.
    """

    def create(
        config,
        output,
        yes=False,
        loglevel=logging.CRITICAL,
        keep_tempfiles=False,
        clip=None,
        data=None,
        alias=None,
        name=None,
        parts_from_clips=False,
    ):
        if clip == None:
            clip = [os.path.dirname(config) + "/clips"]
        if alias == None:
            alias = []
        with open(config) as f:
            if data != None:
                new_data = {}
                for d in data:
                    split = d.split("=")
                    key = split[0]
                    val = split[1]
                    new_data[key] = val
                definition = yaml.safe_load(Template(f.read()).render(new_data))
            else:
                definition = yaml.safe_load(f)

        clips = []
        types = ("*.mp3", "*.wav", "*.aif")
        index = 0

        if clip and len(clip) > 0:
            for file in clip:
                file = os.path.relpath(file)
                if os.path.isdir(file):
                    files_grabbed = []
                    for t in types:
                        files_grabbed.extend(
                            sorted(
                                glob.glob(os.path.join(file, t)), key=os.path.getmtime
                            )
                        )
                    for f in files_grabbed:
                        path = f
                        title = (
                            os.path.splitext(os.path.basename(f))[0]
                            if index not in alias
                            else alias[index]
                        )
                        index += 1
                        clips.append({"name": title, "path": path})
                elif os.path.isfile(file):
                    path = file
                    title = (
                        os.path.splitext(os.path.basename(file))[0]
                        if index not in alias
                        else alias[index]
                    )
                    index += 1
                    clips.append({"name": title, "path": path})

        if not "clips" in definition:
            if len(clips) > 0:
                definition["clips"] = clips
            else:
                definition["clips"] = []
        elif len(clips) > 0:
            definition["clips"] = definition["clips"] + clips

        if parts_from_clips:
            parts = []
            for clip in definition["clips"]:
                parts.append({"name": clip["name"], "clips": [{"name": clip["name"]}]})
            definition["parts"] = (
                definition["parts"] + parts if "parts" in definition else parts
            )

        if name:
            definition["name"] = name

        try:
            with open(os.path.join(os.path.dirname(__file__), "amix.json")) as f:
                schema = json.load(f)
            jsonschema.validate(definition, schema)
            return Amix(definition, output, yes, loglevel, keep_tempfiles)
        except jsonschema.exceptions.ValidationError as e:
            _logger.exception("Error while parsing amix definition file")
            raise e

    def __init__(
        self,
        definition,
        output,
        overwrite_output=False,
        loglevel=None,
        keep_tempfiles=False,
    ):
        """
        Creates a Amix instance for a definition.
        """

        self.definition = definition
        self.name = self.definition["name"]
        self.bar_time = (60 / self.definition["original_tempo"]) * 4
        self.output = output
        self.overwrite_output = overwrite_output
        self.parts_dir = os.path.join(self.output, self.name, "parts")
        self.mix_dir = os.path.join(self.output, self.name, "mix")
        self.tmp_dir = os.path.join(self.output, self.name, "tmp")
        if loglevel == logging.DEBUG:
            self.loglevel = "debug"
        elif loglevel == logging.INFO:
            self.loglevel = "info"
        else:
            self.loglevel = "error"
        self.keep_tempfiles = keep_tempfiles

    def _load_clips(self):
        """
        Loads clips.
        """

        _logger.info("Loading clips")
        self.clips = {}
        for c in self.definition["clips"]:
            clip = _Clip(c["name"], c["path"])
            clip.load()
            self.clips[clip.name] = clip

    def _parse_filter(self, filter, bar_time):
        """
        Parses filter definitions.
        """

        if "from" in filter:
            enable_from = float(filter["from"])
            enable_to = float(filter["to"]) if "to" in filter else None

            if enable_to:
                enable = "between(t,{0},{1})".format(
                    enable_from * bar_time, enable_to * bar_time
                )
            else:
                enable = "gte(t,{0})".format(enable_from * bar_time)
        else:
            enable = None

        kwargs = dict(enable=enable)
        filter_type = filter["type"]

        if filter_type == "fade":
            kwargs["start_time"] = float(filter.get("start_time", 0)) * bar_time
            kwargs["duration"] = (
                float(filter.get("duration", self.definition.get("bars", 16)))
                * bar_time
            )
            kwargs["curve"] = filter["curve"] if "curve" in filter else "tri"
            kwargs["type"] = filter["direction"]
            filter_type = "afade"
        elif filter_type == "volume":
            kwargs["volume"] = float(filter["volume"])
        elif filter_type == "pitch":
            kwargs["tempo"] = float(filter.get("tempo", 1))
            kwargs["pitch"] = float(filter.get("pitch", 1))
            kwargs["transients"] = filter.get("transients", "crisp")
            kwargs["detector"] = filter.get("detector", "compound")
            kwargs["phase"] = filter.get("phase", "laminar")
            kwargs["window"] = filter.get("window", "standard")
            kwargs["smoothing"] = filter.get("smoothing", "off")
            kwargs["formant"] = filter.get("formant", "shifted")
            kwargs["pitchq"] = filter.get("pitchq", "quality")
            kwargs["channels"] = filter.get("channels", "apart")
            filter_type = "rubberband"
        else:
            raise Exception('Filter "{0}" does not exist'.format(filter_type))

        return filter_type, kwargs

    def _apply_filters(self, clip, list):
        """
        Applys filters to a clip.
        """
        for filter in list:
            filter_type, kwargs = self._parse_filter(
                [x for x in self.definition["filters"] if x["name"] == filter["name"]][
                    0
                ],
                self.bar_time,
            )
            clip = ffmpeg.filter(
                clip, filter_type, **{k: v for k, v in kwargs.items() if v is not None}
            )
        return clip

    def _create_mix_part(self, part, bars_global=None):
        """
        Creates relevant mix parts.
        """
        _logger.info("Creating mix parts")
        name = part["name"]
        _logger.info('Creating mix part "{0}"'.format(name))
        clips = []
        for definition in part["clips"]:
            c = self.clips[definition["name"]]
            bars_original = math.ceil(float(c.probe["duration"]) / self.bar_time)
            bars_part = definition.get("bars", part.get("bars", bars_global))
            diff = bars_part - bars_original
            if diff >= 0:
                bars = bars_original
                while bars == bars_original and bars > 1 or (bars_part % bars) != 0:
                    bars = bars - 1

            else:
                bars = bars_part % bars_original

            offset = int(definition.get("offset", 0))
            if "loop" in definition:
                loop = int(definition["loop"])
            elif bars_part == bars:
                loop = 0
            elif offset > 0:
                loop = bars_part / (bars + offset) - 1
            else:
                loop = bars_part / (bars) - 1
            clip_time = bars * self.bar_time

            sample_rate = int(c.probe["sample_rate"])
            hash = random.getrandbits(128)

            tmp_filename = os.path.join(self.tmp_dir, "%032x.wav" % hash)
            c.input.output(tmp_filename, loglevel=self.loglevel).run()
            clip = ffmpeg.input(tmp_filename)
            if offset > 0:
                clip = ffmpeg.filter(clip, "apad", pad_dur=offset * self.bar_time)
                clip_time += offset * self.bar_time
            clip = ffmpeg.filter(clip, "atrim", start=0, end=clip_time)
            clip = ffmpeg.filter(clip, "aloop", loop=loop, size=sample_rate * clip_time)

            if "filters" in definition:
                clip = self._apply_filters(clip, definition["filters"])

            clips.append({"definition": definition, "clip": clip})

        weights = " ".join(
            [
                str(x["definition"]["weight"] if "weight" in x["definition"] else "1")
                for x in clips
            ]
        )
        _logger.debug(
            'Using {0} clips "{1}" with weights "{2}"'.format(
                len(clips), [x["definition"]["name"] for x in clips], weights
            )
        )

        filename = os.path.join(self.parts_dir, "{0}.wav".format(name))
        _logger.info(
            'Creating temporary file "{0}" for part "{1}"'.format(name, filename)
        )
        clip = ffmpeg.filter(
            [x["clip"] for x in clips],
            "amix",
            weights=weights,
            inputs=len(clips),
            normalize=False,
        )

        if "filters" in part:
            clip = self._apply_filters(clip, part["filters"])

        clip.output(filename, loglevel=self.loglevel).run(
            overwrite_output=self.overwrite_output
        )
        self.mix_parts[name] = ffmpeg.input(filename)

    def _setup(self):
        """
        Sets up amix.
        """
        _logger.info("Setting up amix")
        self._load_clips()
        Path(self.parts_dir).mkdir(parents=True, exist_ok=True)
        Path(self.mix_dir).mkdir(parents=True, exist_ok=True)
        Path(self.tmp_dir).mkdir(parents=True, exist_ok=True)

        self.mix_parts = {}
        for part in self.definition["parts"]:
            self._create_mix_part(
                part,
                self.definition.get("bars", 16),
            )

    def _create_mix(self):
        """
        Creates the mix data.
        """
        _logger.info("Creating mix")
        definition = self.definition["mix"]
        mix = []
        mix_dir = os.path.join(self.mix_dir, self.definition["name"])
        Path(mix_dir).mkdir(parents=True, exist_ok=True)
        for track in definition:
            weights = " ".join(
                [str(x["weight"] if "weight" in x else "1") for x in track["parts"]]
            )
            parts = [self.mix_parts[x["name"]] for x in track["parts"]]
            _logger.debug(
                'Using {0} parts "{1}" with weights "{2}"'.format(
                    len(parts), [x["name"] for x in parts], weights
                )
            )
            filename = os.path.join(mix_dir, "{0}.wav".format(track["name"]))
            _logger.info(
                'Creating temporary file "{0}" for part "{1}"'.format(
                    track["name"], filename
                )
            )
            clip = ffmpeg.filter(
                [x for x in parts],
                "amix",
                weights=weights,
                inputs=len(parts),
                normalize=False,
            )

            if "filters" in track:
                clip = self._apply_filters(clip, track["filters"])

            clip.output(filename, loglevel=self.loglevel).run(
                overwrite_output=self.overwrite_output
            )
            mix.append(ffmpeg.input(filename))
        self.mix = ffmpeg.filter(mix, "concat", n=len(mix), v=0, a=1)

    def _render_mix(self):
        """
        Renders the mix to disc.
        """
        _logger.info("Rendering mix")
        filename = os.path.join(self.output, "{0}.wav".format(self.definition["name"]))
        _logger.info('Rendering mix to "{0}"'.format(filename))
        self.mix.output(filename, loglevel=self.loglevel).run(
            overwrite_output=self.overwrite_output
        )

    def _cleanup(self):
        """
        Cleans up temporary files.
        """
        _logger.info("Cleaning up")
        if self.keep_tempfiles == False:
            shutil.rmtree(self.tmp_dir, ignore_errors=False)

    def run(self):
        """
        The generator method, sets up everything, creates temporary files, parts and renders the mixes.
        """

        self._setup()
        self._create_mix()
        self._render_mix()
        self._cleanup()
