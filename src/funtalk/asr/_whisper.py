import tqdm

from .base import BaseASR


class _CustomProgressBar(tqdm.tqdm):
    def __init__(self, disable=True, *args, **kwargs):
        super().__init__(disable=False, *args, **kwargs)


class WhisperASR(BaseASR):
    def __init__(self, name="turbo", *args, **kwargs):
        super().__init__(*args, **kwargs)
        import whisper
        import whisper.transcribe as transcribe_module

        transcribe_module.tqdm.tqdm = _CustomProgressBar

        self.model = whisper.load_model(name, *args, **kwargs)

    def transcribe(self, audio, language="ZH", *args, **kwargs):
        return self.model.transcribe(audio, language=language, *args, **kwargs)
