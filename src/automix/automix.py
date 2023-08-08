import logging
import os
import shutil
import random
from pathlib import Path
import ffmpeg

_logger = logging.getLogger(__name__)


class Clip():
    def __init__(self, name, path, bars):
        self.name = name
        self.path = path
        self.bars = bars

    def load(self):
        file = os.path.realpath(self.path)
        _logger.info('Loading clip "{0}" from "{1}"'.format(self.name, self.path))
        self.input = ffmpeg.input(file)
        self.probe = ffmpeg.probe(file)["streams"][0]
        _logger.debug('Probe for clip "{0}" is "{1}"'.format(
            self.name, self.probe))


class Automix():
    def __init__(self, definition, output=None, overwrite_output=False):
        self.definition = definition
        self.mix_dir = os.path.join(os.getcwd(), "mix")
        self.tmp_dir = os.path.join(self.mix_dir, "tmp")
        if output == None:
            self.output = os.path.join(
                os.getcwd(), "{0}.wav".format(self.definition["name"]))
        else:
            self.output = os.path.realpath(output)
        self.overwrite_output = overwrite_output

    def load_clips(self):
        _logger.info("Loading clips")
        self.clips = {}
        for c in self.definition["clips"]:
            clip = Clip(c["name"], c["path"], c["bars"])
            clip.load()
            self.clips[clip.name] = clip

    def create_mix_parts(self):
        _logger.info("Creating mix parts")
        Path(self.mix_dir).mkdir(parents=True, exist_ok=True)
        Path(self.tmp_dir).mkdir(parents=True, exist_ok=True)
        self.mix_parts = {}
        for part in self.definition["mix"]:
            _logger.info('Creating mix part "{0}"'.format(part["name"]))
            clips = []
            for definition in part["clips"]:
                c = self.clips[definition["name"]]
                loop = definition["loop"] if "loop" in definition else 1
                clip_time = float(c.probe["duration"])
                sample_rate = int(c.probe["sample_rate"])
                clip_length = clip_time * loop
                hash = random.getrandbits(128)

                tmp_filename = os.path.join(self.tmp_dir, "%032x.wav" % hash)
                c.input.output(tmp_filename).run()
                clip = ffmpeg.input(tmp_filename)
                clip = ffmpeg.filter(clip, "aloop", loop=loop,
                                     size=sample_rate * clip_time)

                if "filters" in definition:
                    for filter in definition["filters"]:

                        if "from" in filter:
                            enable_from = float(filter["from"])
                            enable_to = float(filter["to"]) if "to" in filter else None

                            if enable_to:
                                enable = "between(t,{0},{1})".format(
                                    enable_from * clip_time / c.bars, enable_to * clip_time / c.bars)
                            else:
                                enable = "gte(t,{0})".format(
                                    enable_from * clip_time / c.bars)
                        else:
                            enable = None

                        if filter["name"] == "fade":
                            clip = ffmpeg.filter(
                                clip, 'afade', filter["type"], duration=clip_length, curve=filter["curve"])
                        elif filter["name"] == "lowpass":
                            clip = ffmpeg.filter(
                                clip, 'lowpass', frequency=float(filter["frequency"]), enable=enable)
                        elif filter["name"] == "highpass":
                            clip = ffmpeg.filter(
                                clip, 'highpass', frequency=float(filter["frequency"]), enable=enable)
                        elif filter["name"] == "volume":
                            clip = ffmpeg.filter(
                                clip, 'volume', volume=float(filter["volume"]), enable=enable)

                clip = ffmpeg.filter(clip, "atrim", start=0, end=clip_length)

                clips.append({"definition": definition, "clip": clip})

            weights = " ".join([str(x["definition"]["weight"]) for x in clips])
            _logger.debug('Using {0} clips "{1}" with weights "{2}"'.format(
                len(clips), [x["definition"]["name"] for x in clips], weights))

            filename = os.path.join(self.mix_dir, "{0}.wav".format(part["name"]))
            _logger.info(
                'Creating temporary file "{0}" for part "{1}"'.format(part["name"], filename))
            ffmpeg.filter([x["clip"] for x in clips], 'amix', weights=weights,
                          inputs=len(clips)).output(filename).run(overwrite_output=self.overwrite_output)
            self.mix_parts[part["name"]] = ffmpeg.input(filename)

    def setup(self):
        _logger.info("Setting up automix")
        self.load_clips()
        self.create_mix_parts()

    def create_mix(self):
        _logger.info('Creating mix for "{0}"'.format(self.definition["name"]))
        self.mix = ffmpeg.filter(
            [x for x in self.mix_parts.values()], 'concat', n=2, v=0, a=1)
        tempo = self.definition.get("tempo", 1)
        pitch = self.definition.get("pitch", 1)
        if tempo != 1 or pitch != 1:
            self.mix = ffmpeg.filter(self.mix, 'rubberband', tempo=tempo, pitch=pitch)

    def render_mix(self):
        _logger.info('Rendering mix to "{0}"'.format(self.output))
        self.mix.output(self.output).run(overwrite_output=self.overwrite_output)

    def cleanup(self):
        _logger.info("Cleaning up")
        shutil.rmtree(self.tmp_dir, ignore_errors=False)

    def run(self):
        self.setup()
        self.create_mix()
        self.render_mix()
        self.cleanup()
