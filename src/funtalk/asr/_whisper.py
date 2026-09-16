import contextvars
import importlib
from typing import Callable, Optional

import tqdm

from .base import BaseASR

# whisper's transcribe() creates its own tqdm.tqdm(...) instance internally --
# we can't pass a callback through that call, so a contextvar carries the
# "current call's" progress sink across the monkey-patched class instead.
_progress_sink: "contextvars.ContextVar[Optional[Callable[[float], None]]]" = (
    contextvars.ContextVar("funtalk_progress_sink", default=None)
)


class _CustomProgressBar(tqdm.tqdm):
    def __init__(self, disable=True, *args, **kwargs):
        super().__init__(disable=False, *args, **kwargs)

    def update(self, n=1):
        result = super().update(n)
        sink = _progress_sink.get()
        if sink is not None and self.total:
            try:
                sink(min(self.n / self.total, 1.0))
            except Exception:
                pass
        return result


class WhisperASR(BaseASR):
    def __init__(self, name="turbo", *args, **kwargs):
        super().__init__(*args, **kwargs)
        import whisper

        # whisper/__init__.py does `from .transcribe import transcribe`, which
        # rebinds the `whisper.transcribe` *attribute* to that function,
        # shadowing the submodule of the same name -- so `whisper.transcribe`
        # and `import whisper.transcribe as x` both resolve to the function,
        # not the module. importlib.import_module() goes through sys.modules
        # instead of attribute lookup, so it reliably returns the real
        # submodule. This patch is cosmetic (silences/customizes whisper's own
        # progress bar), so if it can't be applied -- e.g. an incompatible or
        # wrong "whisper" package is installed -- skip it instead of crashing
        # the whole pipeline over a progress bar.
        try:
            transcribe_module = importlib.import_module("whisper.transcribe")
            transcribe_module.tqdm.tqdm = _CustomProgressBar
        except (ImportError, AttributeError):
            pass

        self.model = whisper.load_model(name, *args, **kwargs)

    def transcribe(
        self,
        audio,
        language="ZH",
        on_progress: Optional[Callable[[float], None]] = None,
        *args,
        **kwargs,
    ):
        token = _progress_sink.set(on_progress)
        try:
            return self.model.transcribe(audio, language=language, *args, **kwargs)
        finally:
            _progress_sink.reset(token)
