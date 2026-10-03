import asyncio
from typing import Any

from edge_tts import Communicate, list_voices
from edge_tts import SubMaker
from farlog import getLogger
from funtalk._util import convert_rate_to_percent
from funtalk.tts.base import BaseTTS
from funutil import deep_get
from funutil.util.retrying import retry

logger = getLogger("funtalk")


class TTSSynthesisError(RuntimeError):
    """TTS 引擎未生成有效音频或字幕时抛出的领域异常。"""


__all__ = ["EdgeTTS", "TTSSynthesisError", "convert_rate_to_percent", "tts_generate"]


class EdgeTTS(BaseTTS):
    """基于 edge-tts 的语音合成实现。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化 Edge TTS 客户端。"""
        super().__init__(*args, **kwargs)

    @staticmethod
    def list_voices(gender: str | None = None, locale: str | None = "zh-CN") -> list[dict]:
        """列出指定性别和区域的可用语音。"""
        result = []
        voice_list = asyncio.run(list_voices())
        for voice in voice_list:
            if locale and deep_get(voice, "Locale") != locale:
                continue
            if gender and deep_get(voice, "Gender") != gender:
                continue
            result.append(voice)

        return result

    @retry(4)
    def _tts(
        self, text: str, voice_rate: float, voice_file: str, *args: Any, **kwargs: Any
    ) -> SubMaker:
        text = text.strip()
        rate_str = convert_rate_to_percent(voice_rate)
        communicate = Communicate(text, self.voice_name, rate=rate_str)
        sub_maker = SubMaker()

        with open(voice_file, "wb") as file:
            for chunk in communicate.stream_sync():
                if chunk["type"] == "audio":
                    file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    sub_maker.create_sub(
                        (chunk["offset"], chunk["duration"]), chunk["text"]
                    )
        if not sub_maker or not sub_maker.subs:
            raise TTSSynthesisError("未生成有效字幕，语音合成结果为空")
        logger.info(
            f"completed with voice_name:{self.voice_name}, output file: {voice_file}"
        )
        return sub_maker


def tts_generate(
    text: str, voice_name: str, voice_rate: float, voice_file: str, subtitle_file: str
) -> BaseTTS:
    """合成语音并返回 Edge TTS 客户端。

    Args:
        text: 待合成的文本。
        voice_name: edge-tts 语音名称，例如 ``"zh-CN-XiaoxiaoNeural"``。
        voice_rate: 语速倍率，1.0 为正常语速。
        voice_file: 合成音频的输出路径。
        subtitle_file: 对齐字幕的输出路径；生成字幕依赖可选依赖 ``funtalk[tts]``
            （moviepy），未安装时会抛出 `SubtitleGenerationError`。

    Returns:
        已完成合成的 `EdgeTTS` 客户端实例，可通过 `client.sub_maker` 获取字幕时间戳。

    Raises:
        TTSSynthesisError: 语音合成未产生有效字幕时抛出。
    """
    client = EdgeTTS(voice_name)
    client.create_tts(
        text=text,
        voice_rate=voice_rate,
        voice_file=voice_file,
        subtitle_file=subtitle_file,
    )
    return client
