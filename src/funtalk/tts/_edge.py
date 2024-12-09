import asyncio

from edge_tts import Communicate
from edge_tts import SubMaker
from funutil import getLogger

from .base import BaseTTS

logger = getLogger("funtalk")


def convert_rate_to_percent(rate: float) -> str:
    if rate == 1.0:
        return "+0%"
    percent = round((rate - 1.0) * 100)
    if percent > 0:
        return f"+{percent}%"
    else:
        return f"{percent}%"


class EdgeTTS(BaseTTS):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _tts(
        self, text: str, voice_rate: float, voice_file: str, *args, **kwargs
    ) -> [SubMaker, None]:
        text = text.strip()
        rate_str = convert_rate_to_percent(voice_rate)
        for i in range(3):
            try:
                logger.info(f"start, voice name: {self.voice_name}, try: {i + 1}")

                async def _do() -> SubMaker:
                    communicate = Communicate(text, self.voice_name, rate=rate_str)
                    sub_maker = SubMaker()
                    with open(voice_file, "wb") as file:
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                file.write(chunk["data"])
                            elif chunk["type"] == "WordBoundary":
                                sub_maker.create_sub(
                                    (chunk["offset"], chunk["duration"]), chunk["text"]
                                )
                    return sub_maker

                sub_maker = asyncio.run(_do())
                if not sub_maker or not sub_maker.subs:
                    logger.warning(
                        f"failed, sub_maker is None or sub_maker.subs is None"
                    )
                    continue

                logger.info(f"completed, output file: {voice_file}")
                return sub_maker
            except Exception as e:
                logger.error(f"failed, error: {str(e)}")
        return None


def tts_generate(
    text: str, voice_name: str, voice_rate: float, voice_file: str, subtitle_file: str
) -> [BaseTTS, None]:
    client = EdgeTTS(voice_name)
    client.create_tts(
        text=text,
        voice_rate=voice_rate,
        voice_file=voice_file,
        subtitle_file=subtitle_file,
    )
    return client
