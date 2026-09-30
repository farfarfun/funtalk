from typing import Any


class BaseASR:
    """语音识别实现的统一接口。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化语音识别器。"""
        pass

    def load(self, *args: Any, **kwargs: Any) -> None:
        """加载语音识别模型。"""
        raise NotImplementedError

    def transcribe(self, audio: object, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """将音频转写为包含文本及相关信息的字典。"""
        raise NotImplementedError
