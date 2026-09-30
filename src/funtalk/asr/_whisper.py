import contextvars
import importlib
from collections.abc import Callable
from typing import Any

import tqdm
from farlog import getLogger

from .base import BaseASR

# Whisper 的 transcribe() 会在内部创建 tqdm.tqdm 实例，无法直接传入回调，
# 因此通过上下文变量把当前调用的进度接收器传给替换后的进度条类。
logger = getLogger("funtalk")
_progress_sink: contextvars.ContextVar[Callable[[float], None] | None] = (
    contextvars.ContextVar("funtalk_progress_sink", default=None)
)


class _CustomProgressBar(tqdm.tqdm):
    def __init__(self, disable: bool = True, *args: Any, **kwargs: Any) -> None:
        super().__init__(disable=False, *args, **kwargs)

    def update(self, n: int | float = 1) -> bool | None:
        result = super().update(n)
        sink = _progress_sink.get()
        if sink is not None and self.total:
            sink(min(self.n / self.total, 1.0))
        return result


class WhisperASR(BaseASR):
    """基于 openai-whisper 的语音识别实现。"""

    def __init__(self, name: str = "turbo", *args: Any, **kwargs: Any) -> None:
        """加载指定名称的 Whisper 模型。"""
        super().__init__(*args, **kwargs)
        import whisper

        # whisper/__init__.py 会把 whisper.transcribe 属性绑定为同名函数并遮蔽子模块。
        # import_module() 通过 sys.modules 取得真实子模块，以便替换内部进度条。
        # 此补丁只影响进度显示；遇到不兼容的 whisper 包时记录原因并继续加载模型。
        try:
            transcribe_module = importlib.import_module("whisper.transcribe")
            transcribe_module.tqdm.tqdm = _CustomProgressBar
        except (ImportError, AttributeError) as exc:
            logger.warning(f"无法替换 Whisper 进度条，将使用默认实现：{exc}")

        self.model = whisper.load_model(name, *args, **kwargs)

    def transcribe(
        self,
        audio: object,
        language: str = "ZH",
        on_progress: Callable[[float], None] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """转写音频并按需报告进度。"""
        token = _progress_sink.set(on_progress)
        try:
            return self.model.transcribe(audio, language=language, *args, **kwargs)
        finally:
            _progress_sink.reset(token)
