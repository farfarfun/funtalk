import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import unescape

from edge_tts import SubMaker
from edge_tts.submaker import mktimestamp
from farlog import getLogger

from funtalk._util import split_string_by_punctuations

logger = getLogger("funtalk")


class SubtitleGenerationError(RuntimeError):
    """字幕生成或校验失败时抛出的领域异常。"""


class BaseTTS:
    """TTS 引擎的统一接口和字幕生成逻辑。"""

    def __init__(self, voice_name: str, *args: Any, **kwargs: Any) -> None:
        """初始化语音名称。"""
        self.voice_name = self.parse_voice_name(voice_name)
        self.sub_maker: SubMaker | None = None

    def _tts(
        self,
        text: str,
        voice_rate: float,
        voice_file: str,
        *args: Any,
        **kwargs: Any,
    ) -> SubMaker | None:
        raise NotImplementedError()

    @staticmethod
    def parse_voice_name(voice_name: str) -> str:
        """移除语音名称中的性别后缀。"""
        return voice_name.replace("-Female", "").replace("-Male", "").strip()

    @staticmethod
    def _format_text(text: str) -> str:
        text = text.replace("[", " ")
        text = text.replace("]", " ")
        text = text.replace("(", " ")
        text = text.replace(")", " ")
        text = text.replace("{", " ")
        text = text.replace("}", " ")
        text = text.strip()
        return text

    def create_subtitle(
        self, text: str, subtitle_file: str, *args: Any, **kwargs: Any
    ) -> None:
        """
        优化字幕文件
        1. 将字幕文件按照标点符号分割成多行
        2. 逐行匹配字幕文件中的文本
        3. 生成新的字幕文件
        """

        def formatter(
            idx: int, start_time: float, end_time: float, sub_text: str
        ) -> str:
            start_t = mktimestamp(start_time).replace(".", ",")
            end_t = mktimestamp(end_time).replace(".", ",")
            return f"{idx}\n{start_t} --> {end_t}\n{sub_text}\n"

        start_time = -1.0
        sub_items = []
        sub_index = 0

        script_lines = split_string_by_punctuations(text)

        def match_line(_sub_line: str, _sub_index: int) -> str:
            if len(script_lines) <= _sub_index:
                return ""

            _line = script_lines[_sub_index]
            if _sub_line == _line:
                return script_lines[_sub_index].strip()

            _sub_line_ = re.sub(r"[^\w\s]", "", _sub_line)
            _line_ = re.sub(r"[^\w\s]", "", _line)
            if _sub_line_ == _line_:
                return _line_.strip()

            _sub_line_ = re.sub(r"\W+", "", _sub_line)
            _line_ = re.sub(r"\W+", "", _line)
            if _sub_line_ == _line_:
                return _line.strip()

            return ""

        sub_line = ""

        if self.sub_maker is None:
            raise SubtitleGenerationError("语音合成未返回时间戳，无法生成字幕")

        for offset, sub in zip(self.sub_maker.offset, self.sub_maker.subs):
            _start_time, end_time = offset
            if start_time < 0:
                start_time = _start_time

            sub_line += unescape(sub)
            sub_text = match_line(sub_line, sub_index)
            if sub_text:
                sub_index += 1
                line = formatter(
                    idx=sub_index,
                    start_time=start_time,
                    end_time=end_time,
                    sub_text=sub_text,
                )
                sub_items.append(line)
                start_time = -1.0
                sub_line = ""

        if len(sub_items) != len(script_lines):
            raise SubtitleGenerationError(
                "字幕文本与时间戳无法完整匹配："
                f"已匹配 {len(sub_items)} 行，共 {len(script_lines)} 行"
            )

        with open(subtitle_file, "w", encoding="utf-8") as file:
            file.write("\n".join(sub_items) + "\n")
        try:
            from moviepy.video.tools import subtitles

            sbs = subtitles.file_to_subtitles(subtitle_file, encoding="utf-8")
            duration = max(tb for ((_, tb), _) in sbs)
        except (ImportError, OSError, TypeError, ValueError) as exc:
            Path(subtitle_file).unlink(missing_ok=True)
            raise SubtitleGenerationError(
                f"字幕文件校验失败：{subtitle_file}"
            ) from exc
        logger.info(
            f"completed, subtitle file created: {subtitle_file}, duration: {duration}"
        )

    def create_tts(
        self,
        text: str,
        voice_rate: float,
        voice_file: str,
        subtitle_file: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> SubMaker | None:
        """合成语音，并按需生成与校验字幕文件。"""
        text = self._format_text(text)
        self.sub_maker = self._tts(
            text=text, voice_rate=voice_rate, voice_file=voice_file, *args, **kwargs
        )
        if subtitle_file:
            self.create_subtitle(
                text=text, subtitle_file=subtitle_file, *args, **kwargs
            )
        return self.sub_maker

    def get_audio_duration(self) -> float:
        """返回最近一次合成音频的时长（秒）。"""
        if self.sub_maker is None or not self.sub_maker.offset:
            return 0.0
        return self.sub_maker.offset[-1][1] / 10000000
