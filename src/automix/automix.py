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
        self.mix_dir = os.path.join(os.getcwd(), "mix")
        self.tmp_dir = os.path.join(self.mix_dir, "tmp")
        if output == None:
            self.output = os.path.join(
                os.getcwd(), "{0}.wav".format(self.definition["name"]))
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
            kwargs["frequency"] = int(filter["frequency"])
        elif filter_name == "highpass":
            kwargs["frequency"] = int(filter["frequency"])
        elif filter_name == "volume":
            kwargs["volume"] = float(filter["volume"])
        elif filter_name == "flanger":
            kwargs["delay"] = float(filter["delay"])
        elif "filters" in self.definition and filter_name in self.definition["filters"]:
            filter_name, kwargs = self.parse_filter(
                self.definition["filters"][filter_name], bar_time)
        else:
            raise Exception('Filter not found "{0}"'.format(filter_name))

        return filter_name, kwargs

    def create_mix_parts(self, name, definition, tempo):
        _logger.info('Creating mix parts "{0}"'.format(name))
        self.mix_parts = {}
        for part in definition:
            _logger.info('Creating mix part "{0}"'.format(part["name"]))
            clips = []
            for definition in part["clips"]:
                if not definition["name"] in self.clips:
                    continue
                c = self.clips[definition["name"]]
                bar_time = (60 / tempo) * 4
                bars_original = math.ceil(float(
                    c.probe["duration"]) / bar_time)
                diff = part["bars"] - bars_original
                if diff >= 0:
                    bars = bars_original
                    while bars >= bars_original and bars > 1 or (part["bars"] % bars) != 0:
                        bars = bars - 1

                else:
                    bars = int(part["bars"] % bars_original)

                loop = definition.get("loop", 0 if int(part["bars"]) == bars else (
                    int(part["bars"]) / int(bars)) - 1)

                clip_time = bars * bar_time

                sample_rate = int(c.probe["sample_rate"])
                hash = random.getrandbits(128)

                tmp_filename = os.path.join(self.tmp_dir, "%032x.wav" % hash)
                c.input.output(tmp_filename, loglevel=self.loglevel).run()
                clip = ffmpeg.input(tmp_filename)
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

            filename = os.path.join(self.mix_dir, "{0}.wav".format(part["name"]))
            _logger.info(
                'Creating temporary file "{0}" for part "{1}"'.format(part["name"], filename))
            ffmpeg.filter([x["clip"] for x in clips], 'amix', weights=weights,
                          inputs=len(clips), normalize=False).output(filename, loglevel=self.loglevel).run(overwrite_output=self.overwrite_output)
            self.mix_parts[name] = self.mix_parts.get(name, {})
            self.mix_parts[name][part["name"]] = ffmpeg.input(filename)

    def setup(self):
        _logger.info("Setting up automix")
        self.load_clips()
        Path(self.mix_dir).mkdir(parents=True, exist_ok=True)
        Path(self.tmp_dir).mkdir(parents=True, exist_ok=True)
        for key in self.definition["mix"].keys():
            self.create_mix_parts(
                key, self.definition["mix"][key], self.definition["original_tempo"])

    def create_mix(self):
        _logger.info('Creating mix for "{0}"'.format(self.definition["name"]))
        mixes = []
        for key in self.mix_parts:
            mix_parts = self.mix_parts[key]
            segments = [x for x in mix_parts.values()]
            mixes.append({"parts": mix_parts, "clip": ffmpeg.filter(
                segments, 'concat', n=len(segments), v=0, a=1)})
        self.mix = ffmpeg.filter([x["clip"] for x in mixes], 'amix',
                                 inputs=len(mixes), normalize=False)
        tempo = self.definition.get("tempo", 1)
        pitch = self.definition.get("pitch", 1)
        if tempo != 1 or pitch != 1:
            self.mix = ffmpeg.filter(self.mix, 'rubberband', tempo=tempo, pitch=pitch)

    def render_mix(self):
        _logger.info('Rendering mix to "{0}"'.format(self.output))
        self.mix.output(self.output, loglevel=self.loglevel).run(
            overwrite_output=self.overwrite_output)

    def cleanup(self):
        _logger.info("Cleaning up")
        shutil.rmtree(self.tmp_dir, ignore_errors=False)

    def run(self):
        self.setup()
        self.create_mix()
        self.render_mix()
        self.cleanup()
