from typing import Any


class BaseASR:
    """语音识别实现的统一接口。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化语音识别器。

        Args:
            *args: 保留给具体语音识别实现的额外位置参数。
            **kwargs: 保留给具体语音识别实现的额外关键字参数。
        """
        pass

    def load(self, *args: Any, **kwargs: Any) -> None:
        """加载语音识别模型。

        Args:
            *args: 传递给具体语音识别实现的额外位置参数。
            **kwargs: 传递给具体语音识别实现的额外关键字参数。

        Returns:
            无返回值；模型加载完成后可调用 `transcribe`。
        """
        raise NotImplementedError

    def transcribe(self, audio: object, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """将音频转写为包含文本及相关信息的字典。

        Args:
            audio: 具体实现支持的音频输入，例如音频文件路径或音频数据。
            *args: 传递给具体语音识别实现的额外位置参数。
            **kwargs: 传递给具体语音识别实现的额外关键字参数。

        Returns:
            包含转写文本及实现相关元数据的字典。
        """
        raise NotImplementedError
