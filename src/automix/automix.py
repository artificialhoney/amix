import logging
import os
import shutil
import random
from pathlib import Path
import math
import ffmpeg

_logger = logging.getLogger(__name__)


class Clip():
    def __init__(self, name, path):
        self.name = name
        self.path = path

    def load(self):
        file = os.path.realpath(self.path)
        _logger.info('Loading clip "{0}" from "{1}"'.format(self.name, self.path))
        self.input = ffmpeg.input(file)
        self.probe = ffmpeg.probe(file)["streams"][0]
        _logger.debug('Probe for clip "{0}" is "{1}"'.format(
            self.name, self.probe))


class Automix():
    def __init__(self, definition, output=None, overwrite_output=False, loglevel=None):
        self.definition = definition
        self.parts_dir = os.path.join(os.getcwd(), "parts")
        self.mix_dir = os.path.join(os.getcwd(), "mix")
        self.tmp_dir = os.path.join(self.mix_dir, "tmp")
        if output == None:
            self.output = os.getcwd()
        else:
            self.output = os.path.realpath(output)
        self.overwrite_output = overwrite_output
        if loglevel == logging.DEBUG:
            self.loglevel = 'debug'
        elif loglevel == logging.INFO:
            self.loglevel = 'info'
        else:
            self.loglevel = 'error'

    def load_clips(self):
        _logger.info("Loading clips")
        self.clips = {}
        for name, path in self.definition["clips"].items():
            clip = Clip(name, path)
            clip.load()
            self.clips[clip.name] = clip

    def parse_filter(self, filter, bar_time):
        if "from" in filter:
            enable_from = float(filter["from"])
            enable_to = float(filter["to"]) if "to" in filter else None

            if enable_to:
                enable = "between(t,{0},{1})".format(
                    enable_from * bar_time, enable_to * bar_time)
            else:
                enable = "gte(t,{0})".format(
                    enable_from * bar_time)
        else:
            enable = None

        kwargs = dict(enable=enable)
        filter_name = filter["name"]

        if filter_name == "fade":
            kwargs["start_time"] = float(
                filter["start_time"]) * bar_time
            kwargs["duration"] = float(filter["duration"]) * bar_time
            kwargs["curve"] = filter["curve"] if "curve" in filter else "tri"
            kwargs["type"] = filter["type"]
            filter_name = "afade"
        elif filter_name == "lowpass":
            kwargs["frequency"] = float(filter["frequency"])
        elif filter_name == "highpass":
            kwargs["frequency"] = float(filter["frequency"])
        elif filter_name == "bandpass":
            kwargs["frequency"] = float(filter["frequency"])
            kwargs["width"] = float(filter["width"])
        elif filter_name == "volume":
            kwargs["volume"] = float(filter["volume"])
        elif filter_name == "pitch":
            kwargs["tempo"] = 1.0
            kwargs["pitch"] = float(filter["pitch"])
            filter_name = "rubberband"
        elif "filters" in self.definition and filter_name in self.definition["filters"]:
            filter_name, kwargs = self.parse_filter(
                self.definition["filters"][filter_name], bar_time)
        else:
            raise Exception('Filter not found "{0}"'.format(filter_name))

        return filter_name, kwargs

    def create_mix_parts(self, definition, tempo):
        _logger.info('Creating mix parts')
        self.mix_parts = {}
        for name, part in definition.items():
            _logger.info('Creating mix part "{0}"'.format(name))
            clips = []
            for definition in part["clips"]:
                if not definition["name"] in self.clips:
                    continue
                bars_part = int(part["bars"])
                c = self.clips[definition["name"]]
                bar_time = (60 / tempo) * 4
                bars_original = math.ceil(float(
                    c.probe["duration"]) / bar_time)
                diff = bars_part - bars_original
                if diff >= 0:
                    bars = bars_original
                    while bars >= bars_original and bars > 1 or (bars_part % bars) != 0:
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
                clip = ffmpeg.filter(clip, "aloop", loop=loop,
                                     size=sample_rate * clip_time)

                if "filters" in definition:
                    for filter in definition["filters"]:
                        filter_name, kwargs = self.parse_filter(filter, bar_time)
                        clip = ffmpeg.filter(
                            clip, filter_name, **{k: v for k, v in kwargs.items() if v is not None})

                clips.append({"definition": definition, "clip": clip})

            weights = " ".join(
                [str(x["definition"]["weight"] if "weight" in x["definition"] else "1") for x in clips])
            _logger.debug('Using {0} clips "{1}" with weights "{2}"'.format(
                len(clips), [x["definition"]["name"] for x in clips], weights))

            filename = os.path.join(self.parts_dir, "{0}.wav".format(name))
            _logger.info(
                'Creating temporary file "{0}" for part "{1}"'.format(name, filename))
            ffmpeg.filter([x["clip"] for x in clips], 'amix', weights=weights,
                          inputs=len(clips), normalize=False).output(filename, loglevel=self.loglevel).run(overwrite_output=self.overwrite_output)
            self.mix_parts[name] = ffmpeg.input(filename)

    def setup(self):
        _logger.info("Setting up automix")
        self.load_clips()
        Path(self.parts_dir).mkdir(parents=True, exist_ok=True)
        Path(self.mix_dir).mkdir(parents=True, exist_ok=True)
        Path(self.tmp_dir).mkdir(parents=True, exist_ok=True)
        self.create_mix_parts(
            self.definition["parts"], self.definition["original_tempo"])

    def create_mixes(self):
        _logger.info("Creating mixes")
        self.mixes = {}
        for mix_name, definition in self.definition["mixes"].items():
            mix = []
            mix_dir = os.path.join(self.mix_dir, mix_name)
            Path(mix_dir).mkdir(parents=True, exist_ok=True)
            for track in definition["segments"]:
                weights = " ".join(
                    [str(x["weight"] if "weight" in x else "1") for x in track["parts"]])
                parts = [self.mix_parts[x["name"]] for x in track["parts"]]
                _logger.debug('Using {0} parts "{1}" with weights "{2}"'.format(
                    len(parts), [x["name"] for x in parts], weights))
                filename = os.path.join(mix_dir, "{0}.wav".format(track["name"]))
                _logger.info(
                    'Creating temporary file "{0}" for part "{1}"'.format(track["name"], filename))
                ffmpeg.filter([x for x in parts], 'amix', weights=weights,
                              inputs=len(parts), normalize=False).output(filename, loglevel=self.loglevel).run(overwrite_output=self.overwrite_output)
                mix.append(ffmpeg.input(filename))
            self.mixes[mix_name] = ffmpeg.filter(
                mix, 'concat', n=len(mix), v=0, a=1)
            tempo = float(definition.get("tempo", 1))
            pitch = float(definition.get("pitch", 1))
            if tempo != 1 or pitch != 1:
                self.mixes[mix_name] = ffmpeg.filter(
                    self.mixes[mix_name], 'rubberband', tempo=tempo, pitch=pitch)

    def render_mixes(self):
        _logger.info("Rendering mixes")
        for mix_name, mix in self.mixes.items():
            filename = os.path.join(self.output, "{0} ({1}).wav".format(
                self.definition["name"], mix_name))
            _logger.info('Rendering mix to "{0}"'.format(filename))
            mix.output(filename, loglevel=self.loglevel).run(
                overwrite_output=self.overwrite_output)

    def cleanup(self):
        _logger.info("Cleaning up")
        shutil.rmtree(self.tmp_dir, ignore_errors=False)

    def run(self):
        self.setup()
        self.create_mixes()
        self.render_mixes()
        self.cleanup()
