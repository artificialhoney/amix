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
        """
        this the short description:

        Filters
        -------

        fade
        ~~~~

        Apply fade-in/out effect to input audio.

        A description of the accepted parameters follows.

        ``type, t``
        Specify the effect type, can be either ``in`` for fade-in, or ``out``
        for a fade-out effect. Default is ``in``.

        ``start_sample, ss``
        Specify the number of the start sample for starting to apply the fade
        effect. Default is 0.

        ``nb_samples, ns``
        Specify the number of samples for which the fade effect has to last.
        At the end of the fade-in effect the output audio will have the same
        volume as the input audio, at the end of the fade-out transition the
        output audio will be silence. Default is 44100.

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

        ``silence``
        Set the initial gain for fade-in or final gain for fade-out. Default
        value is ``0.0``.

        ``unity``
        Set the initial gain for fade-out or final gain for fade-in. Default
        value is ``1.0``.

        lowpass
        ~~~~~~~~

        Apply a low-pass filter with 3dB point frequency. The filter can be either single-pole or double-pole (the default). The filter roll off at 6dB per pole per octave (20dB per pole per decade).

        The filter accepts the following options:

        ``frequency, f``

        Set frequency in Hz. Default is 500.

        ``poles, p``

        Set number of poles. Default is 2.

        ``width_type, t``

        Set method to specify band-width of filter.

        ``h``
        Hz

        ``q``
        Q-Factor

        ``o``
        octave

        ``s``
        slope

        ``k``
        kHz

        ``width, w``

        Specify the band-width of a filter in width_type units. Applies only to
        double-pole filter. The default is 0.707q and gives a Butterworth
        response.

        ``mix, m``

        How much to use filtered signal in output. Default is 1. Range is
        between 0 and 1.

        ``channels, c``

        Specify which channels to filter, by default all available are filtered.

        ``normalize, n``

        Normalize biquad coefficients, by default is disabled. Enabling it will
        normalize magnitude response at DC to 0dB.

        ``transform, a``

        Set transform type of IIR filter.

        ``di``

        ``dii``

        ``tdi``

        ``tdii``

        ``latt``

        ``svf``

        ``zdf``

        ``precision, r``

        Set precison of filtering.

        ``auto``
        Pick automatic sample format depending on surround filters.

        ``s16``
        Always use signed 16-bit.

        ``s32``
        Always use signed 32-bit.

        ``f32``
        Always use float 32-bit.

        ``f64``
        Always use float 64-bit.

        ``block_size, b``

        Set block size used for reverse IIR processing. If this value is set to
        high enough value (higher than impulse response length truncated when
        reaches near zero values) filtering will become linear phase otherwise
        if not big enough it will just produce nasty artifacts.

        Note that filter delay will be exactly this many samples when set to
        non-zero value.

        """

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
        elif "filters" in self.definition:
            filter_name, kwargs = self.parse_filter(
                [x for x in self.definition["filters"] if x["alias"] == filter_name][0], bar_time)
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
                bars_original = int(definition.get("bars", math.ceil(float(
                    c.probe["duration"]) / bar_time)))
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
