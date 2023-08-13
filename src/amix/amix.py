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
from mergedeep import merge

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
        cleanup=True,
        clip=None,
        data=None,
        alias=None,
        name=None,
        parts_from_clips=False,
    ):
        if not clip:
            clip = [os.path.dirname(config) + "/clips"]
        if not alias:
            alias = []
        with open(config) as f:
            definition = yaml.safe_load(f)
        if data != None:
            new_data = {}
            for d in data:
                split = d.split("=")
                key = split[0]
                val = split[1]
                new_data[key] = val

            if "original_tempo" in definition:
                template = Template(definition["original_tempo"])
                definition["original_tempo"] = float(template.render(new_data))

            if "bars" in definition:
                template = Template(definition["bars"])
                definition["bars"] = float(template.render(new_data))

            if "tempo" in definition:
                template = Template(definition["tempo"])
                definition["tempo"] = float(template.render(new_data))

            if "pitch" in definition:
                template = Template(definition["pitch"])
                definition["pitch"] = float(template.render(new_data))

            if "parts" in definition:
                for part in definition["parts"].values():
                    if "bars" in part:
                        template = Template(part["bars"])
                        part["bars"] = float(template.render(new_data))

                    for clip in part["clips"]:
                        if "bars" in clip:
                            template = Template(clip["bars"])
                            clip["bars"] = float(template.render(new_data))

            if "filters" in definition:
                for filter in definition["filters"]:
                    for field in ["duration", "from", "to"]:
                        if field in filter:
                            template = Template(filter[field])
                            filter[field] = float(template.render(new_data))

        clips = {}
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
                        if os.path.isfile(f):
                            path = f
                            title = (
                                os.path.splitext(os.path.basename(f))[0]
                                if index not in alias
                                else alias[index]
                            )
                            index += 1
                            clips[title] = path
                elif os.path.isfile(file):
                    path = file
                    title = (
                        os.path.splitext(os.path.basename(file))[0]
                        if index not in alias
                        else alias[index]
                    )
                    index += 1
                    clips[title] = path

        if not "clips" in definition:
            if len(clips.values()) > 0:
                definition["clips"] = clips
            else:
                definition["clips"] = {}
        elif len(clips.values()) > 0:
            definition["clips"] = merge(definition["clips"], clips)

        if parts_from_clips:
            parts = {}
            for clip in definition["clips"].keys():
                parts[clip] = {"clips": [{"name": clip}]}
            definition["parts"] = (
                merge(definition["parts"], parts) if "parts" in definition else parts
            )

        if name:
            definition["name"] = name

        try:
            with open(os.path.join(os.path.dirname(__file__), "amix.json")) as f:
                schema = json.load(f)
            jsonschema.validate(definition, schema)
            return Amix(definition, output, yes, loglevel, cleanup)
        except jsonschema.exceptions.ValidationError as e:
            _logger.exception("Error while parsing amix definition file")
            raise e

    def __init__(
        self,
        definition,
        output=None,
        overwrite_output=False,
        loglevel=None,
        keep_tempfiles=False,
    ):
        """
        Creates a Amix instance for a definition.
        """

        self.definition = definition
        self.name = self.definition["name"]
        if output == None:
            self.output = os.getcwd()
        else:
            self.output = os.path.realpath(output)
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
        for name, path in self.definition["clips"].items():
            clip = _Clip(name, path)
            clip.load()
            self.clips[clip.name] = clip

    def _parse_filter(self, filter, bar_time):
        """
        Parses filter definitions.

        Filters
        -------

        fade
        ~~~~

        Apply fade-in/out effect to input audio.

        A description of the accepted parameters follows.

        ``type, t``
        Specify the effect type, can be either ``in`` for fade-in, or ``out``
        for a fade-out effect. Default is ``in``.

        ``start_time, st``
        Specify the start time of the fade effect. Default is 0. The value
        must be specified as a time duration; see `(ffmpeg-utils)the Time
        duration section in the ffmpeg-utils(1)
        manual <ffmpeg-utils.html#time-duration-syntax>`__ for the accepted
        syntax. If set this option is used instead of ``start_sample``.

        ``duration, d``
        Specify the duration of the fade effect. See `(ffmpeg-utils)the Time
        duration section in the ffmpeg-utils(1)
        manual <ffmpeg-utils.html#time-duration-syntax>`__ for the accepted
        syntax. At the end of the fade-in effect the output audio will have
        the same volume as the input audio, at the end of the fade-out
        transition the output audio will be silence. By default the duration
        is determined by ``nb_samples``. If set this option is used instead
        of ``nb_samples``.

        ``curve``
        Set curve for fade transition.

        It accepts the following values:

        ``tri``
            select triangular, linear slope (default)

        ``qsin``
            select quarter of sine wave

        ``hsin``
            select half of sine wave

        ``esin``
            select exponential sine wave

        ``log``
            select logarithmic

        ``ipar``
            select inverted parabola

        ``qua``
            select quadratic

        ``cub``
            select cubic

        ``squ``
            select square root

        ``cbr``
            select cubic root

        ``par``
            select parabola

        ``exp``
            select exponential

        ``iqsin``
            select inverted quarter of sine wave

        ``ihsin``
            select inverted half of sine wave

        ``dese``
            select double-exponential seat

        ``desi``
            select double-exponential sigmoid

        ``losi``
            select logistic sigmoid

        ``sinc``
            select sine cardinal function

        ``isinc``
            select inverted sine cardinal function

        ``nofade``
            no fade applied

        volume
        ~~~~~~

        Adjust the input audio volume.

        It accepts the following parameters:

        ``volume``
            Set audio volume expression.

            Output values are clipped to the maximum value.

            The output audio volume is given by the relation:

            .. container:: example

                ::

                    output_volume = volume * input_volume

            The default value for ``volume`` is "1.0".


        pitch
        ~~~~~

        Adjust the pitch without changing the tempo.

        It accepts the following parameters:

        ``pitch``

        Set pitch scale factor.

        tempo
        ~~~~~

        Adjust the tempo without changing the pitch.

        It accepts the following parameters:

        ``tempo``

        Set tempo scale factor.
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
        filter_name = filter["name"]

        if filter_name == "fade":
            kwargs["start_time"] = float(filter["start_time"]) * bar_time
            kwargs["duration"] = float(filter["duration"]) * bar_time
            kwargs["curve"] = filter["curve"] if "curve" in filter else "tri"
            kwargs["type"] = filter["type"]
            filter_name = "afade"
        elif filter_name == "volume":
            kwargs["volume"] = float(filter["volume"])
        elif filter_name == "pitch":
            kwargs["tempo"] = 1.0
            kwargs["pitch"] = float(filter["pitch"])
            filter_name = "rubberband"
        elif filter_name == "tempo":
            kwargs["tempo"] = float(filter["tempo"])
            kwargs["pitch"] = 1.0
            filter_name = "rubberband"
        elif "filters" in self.definition:
            filter_name, kwargs = self._parse_filter(
                [x for x in self.definition["filters"] if x["alias"] == filter_name][0],
                bar_time,
            )
        else:
            raise Exception('Filter not found "{0}"'.format(filter_name))

        return filter_name, kwargs

    def _create_mix_parts(self, parts, tempo, bars_global=None):
        _logger.info("Creating mix parts")
        self.mix_parts = {}
        for name, part in parts.items():
            _logger.info('Creating mix part "{0}"'.format(name))
            clips = []
            for definition in part["clips"]:
                if not definition["name"] in self.clips:
                    continue
                c = self.clips[definition["name"]]
                bar_time = (60 / tempo) * 4
                bars_original = math.ceil(float(c.probe["duration"]) / bar_time)
                bars_part = definition.get("bars", part.get("bars", bars_global))
                diff = bars_part - bars_original
                if diff >= 0:
                    bars = bars_original
                    while bars > bars_original and bars > 1 or (bars_part % bars) != 0:
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
                clip_time = bars * bar_time

                sample_rate = int(c.probe["sample_rate"])
                hash = random.getrandbits(128)

                tmp_filename = os.path.join(self.tmp_dir, "%032x.wav" % hash)
                c.input.output(tmp_filename, loglevel=self.loglevel).run()
                clip = ffmpeg.input(tmp_filename)
                if offset > 0:
                    clip = ffmpeg.filter(clip, "apad", pad_dur=offset * bar_time)
                    clip_time += offset * bar_time
                clip = ffmpeg.filter(clip, "atrim", start=0, end=clip_time)
                clip = ffmpeg.filter(
                    clip, "aloop", loop=loop, size=sample_rate * clip_time
                )

                if "filters" in definition:
                    for filter in definition["filters"]:
                        filter_name, kwargs = self._parse_filter(filter, bar_time)
                        clip = ffmpeg.filter(
                            clip,
                            filter_name,
                            **{k: v for k, v in kwargs.items() if v is not None}
                        )

                clips.append({"definition": definition, "clip": clip})

            weights = " ".join(
                [
                    str(
                        x["definition"]["weight"]
                        if "weight" in x["definition"]
                        else "1"
                    )
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
            ffmpeg.filter(
                [x["clip"] for x in clips],
                "amix",
                weights=weights,
                inputs=len(clips),
                normalize=False,
            ).output(filename, loglevel=self.loglevel).run(
                overwrite_output=self.overwrite_output
            )
            self.mix_parts[name] = ffmpeg.input(filename)

    def _setup(self):
        _logger.info("Setting up amix")
        self._load_clips()
        Path(self.parts_dir).mkdir(parents=True, exist_ok=True)
        Path(self.mix_dir).mkdir(parents=True, exist_ok=True)
        Path(self.tmp_dir).mkdir(parents=True, exist_ok=True)

        self._create_mix_parts(
            self.definition["parts"],
            self.definition["original_tempo"],
            self.definition.get("bars", 16),
        )

    def _create_mixes(self):
        _logger.info("Creating mixes")
        self.mixes = {}
        for mix_name, definition in self.definition["mixes"].items():
            mix = []
            mix_dir = os.path.join(self.mix_dir, mix_name)
            Path(mix_dir).mkdir(parents=True, exist_ok=True)
            for track in definition["segments"]:
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
                ffmpeg.filter(
                    [x for x in parts],
                    "amix",
                    weights=weights,
                    inputs=len(parts),
                    normalize=False,
                ).output(filename, loglevel=self.loglevel).run(
                    overwrite_output=self.overwrite_output
                )
                mix.append(ffmpeg.input(filename))
            self.mixes[mix_name] = ffmpeg.filter(mix, "concat", n=len(mix), v=0, a=1)
            tempo = float(definition.get("tempo", self.definition.get("tempo", 1)))
            pitch = float(definition.get("pitch", self.definition.get("pitch", 1)))
            if tempo != 1 or pitch != 1:
                self.mixes[mix_name] = ffmpeg.filter(
                    self.mixes[mix_name], "rubberband", tempo=tempo, pitch=pitch
                )

    def _render_mixes(self):
        _logger.info("Rendering mixes")
        for mix_name, mix in self.mixes.items():
            filename = os.path.join(
                self.output, "{0} ({1}).wav".format(self.definition["name"], mix_name)
            )
            _logger.info('Rendering mix to "{0}"'.format(filename))
            mix.output(filename, loglevel=self.loglevel).run(
                overwrite_output=self.overwrite_output
            )

    def _cleanup(self):
        _logger.info("Cleaning up")
        if self.keep_tempfiles == False:
            shutil.rmtree(self.tmp_dir, ignore_errors=False)

    def run(self):
        """
        The generator method, sets up everything, creates temporary files, parts and renders the mixes.
        """

        self._setup()
        self._create_mixes()
        self._render_mixes()
        self._cleanup()
