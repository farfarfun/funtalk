import asyncio
from edge_tts import Communicate, list_voices
from edge_tts import SubMaker
from farlog import getLogger
from funtalk.tts.base import BaseTTS
from funutil import deep_get
from funutil.util.retrying import retry

logger = getLogger("funtalk")


class TTSSynthesisError(RuntimeError):
    """TTS 引擎未生成有效音频或字幕时抛出的领域异常。"""


def convert_rate_to_percent(rate: float) -> str:
    if rate == 1.0:
        return "+0%"
    percent = round((rate - 1.0) * 100)
    if percent > 0:
        return f"+{percent}%"
    else:
        return f"{percent}%"


class EdgeTTS(BaseTTS):
    """基于 edge-tts 的语音合成实现。"""

    def __init__(self, *args, **kwargs) -> None:
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
        self, text: str, voice_rate: float, voice_file: str, *args, **kwargs
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
    """合成语音并返回 Edge TTS 客户端。"""
    client = EdgeTTS(voice_name)
    client.create_tts(
        text=text,
        voice_rate=voice_rate,
        voice_file=voice_file,
        subtitle_file=subtitle_file,
    )
    return client
