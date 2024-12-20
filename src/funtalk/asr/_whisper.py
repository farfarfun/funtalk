import sys

import tqdm

from .base import BaseASR


class _CustomProgressBar(tqdm.tqdm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


transcribe_module = sys.modules["whisper.transcribe"]
transcribe_module.tqdm.tqdm = _CustomProgressBar


class WhisperASR(BaseASR):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = None

    def load(self, name="turbo", *args, **kwargs):
        import whisper

        self.model = whisper.load_model(name, *args, **kwargs)

    def transcribe(self, audio, *args, **kwargs):
        self.model.transcribe(audio, *args, **kwargs)
