"""不依赖外部项目的轻量工具函数。

``split_string_by_punctuations`` 原先从 ``funvideo.app.utils.utils`` 引入，
``PUNCTUATIONS`` 则来自 ``funvideo.app.models.const``。这会让 funtalk 依赖
funvideo，而 funvideo 的 pyproject.toml 又依赖 funtalk，形成循环依赖
（farfarfun/todo-list#156）。该函数体量小、无副作用且不依赖第三方库，因此移至此处。
"""

PUNCTUATIONS = [
    "?",
    ",",
    ".",
    "、",
    ";",
    ":",
    "!",
    "…",
    "？",
    "，",
    "。",
    "、",
    "；",
    "：",
    "！",
    "...",
]


def convert_rate_to_percent(rate: float) -> str:
    """把语速倍率换算成 TTS 引擎接受的百分比字符串。

    edge-tts 与 Azure Speech SDK（SSML `<prosody rate="...">`）都接受同样
    格式的相对百分比字符串，因此两个后端共用这一转换逻辑。

    Args:
        rate: 语速倍率，1.0 表示正常语速，大于 1 加速、小于 1 减速。

    Returns:
        带符号的百分比字符串，例如 ``"+20%"``、``"-10%"``、``"+0%"``。
    """
    if rate == 1.0:
        return "+0%"
    percent = round((rate - 1.0) * 100)
    if percent > 0:
        return f"+{percent}%"
    else:
        return f"{percent}%"


def split_string_by_punctuations(s: str) -> list[str]:
    """按标点和换行拆分文本，过滤空行并保留小数点。"""
    result: list[str] = []
    txt = ""

    previous_char = ""
    next_char = ""
    for i in range(len(s)):
        char = s[i]
        if char == "\n":
            result.append(txt.strip())
            txt = ""
            continue

        if i > 0:
            previous_char = s[i - 1]
        if i < len(s) - 1:
            next_char = s[i + 1]

        if char == "." and previous_char.isdigit() and next_char.isdigit():
            # 取现1万，按2.5%收取手续费, 2.5 中的 . 不能作为换行标记
            txt += char
            continue

        if char not in PUNCTUATIONS:
            txt += char
        else:
            result.append(txt.strip())
            txt = ""
    result.append(txt.strip())
    # 过滤空字符串
    result = list(filter(None, result))
    return result
