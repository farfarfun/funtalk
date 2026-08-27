"""
funtalk 冒烟测试套件。

背景：该仓库在审计时完全没有 tests/ 目录，且 pyproject.toml 声明了 0 个依赖，
但源码实际 import 了 edge_tts / funvideo / moviepy / tqdm / openai-whisper 等
第三方包。本套件在补齐 pyproject.toml 依赖声明的基础上，对每个公开子模块做
"能否正常导入 + 核心类能否用简单参数构造 + 关键方法在 mock 掉真实网络/模型
调用后能否正常工作" 的最小验证，不下载真实模型、不请求真实的 TTS/ASR 服务。

关于 openai-whisper：其体积较大（依赖 torch），在本沙箱环境中安装成本过高，
按任务约定改为在测试中于 sys.modules 级别打桩，只验证 funtalk 对 whisper 模块
的调用方式（load_model / transcribe）是否与桩模块契合。

关于 funvideo.app.config：这是 funtalk 的一个真实上游依赖（AzureTTS 用到了
`funvideo.app.config.config`），但该模块在导入时会硬编码读取当前工作目录下的
`./config.toml`，若文件不存在会直接抛出 FileNotFoundError（这是 funvideo 自身的
一个健壮性问题，不在本仓库改动范围内）。测试中通过 chdir 到一个带有最小
config.toml 的临时目录来规避。
"""

import asyncio
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. 顶层 / 子模块导入
# ---------------------------------------------------------------------------


def test_import_top_level_package():
    import funtalk

    assert funtalk is not None


def test_import_asr_subpackage():
    from funtalk.asr import BaseASR, WhisperASR

    assert BaseASR is not None
    assert WhisperASR is not None


def test_import_tts_subpackage():
    from funtalk.tts import edge_tts_generate, tts_generate

    assert callable(edge_tts_generate)
    assert callable(tts_generate)
    # tts/__init__.py 里 tts_generate 和 edge_tts_generate 都来自 _edge 模块
    assert tts_generate is edge_tts_generate


# ---------------------------------------------------------------------------
# 2. ASR：BaseASR / WhisperASR
# ---------------------------------------------------------------------------


def test_base_asr_is_abstract_stub():
    from funtalk.asr import BaseASR

    asr = BaseASR()
    with pytest.raises(NotImplementedError):
        asr.load()
    with pytest.raises(NotImplementedError):
        asr.transcribe("audio.wav")


@pytest.fixture
def fake_whisper_module(monkeypatch):
    """
    用 sys.modules 打桩 whisper 包，避免安装体积巨大的 openai-whisper/torch。
    还原 funtalk.asr._whisper.WhisperASR.__init__ 里的真实使用方式：
      import whisper
      sys.modules["whisper.transcribe"].tqdm.tqdm = _CustomProgressBar
      whisper.load_model(name, ...)
    """
    fake_model = MagicMock(name="whisper_model")
    fake_model.transcribe.return_value = {"text": "你好，世界"}

    fake_whisper = types.ModuleType("whisper")
    fake_whisper.load_model = MagicMock(return_value=fake_model)

    fake_transcribe = types.ModuleType("whisper.transcribe")
    fake_transcribe.tqdm = types.SimpleNamespace(tqdm=object)
    fake_whisper.transcribe = fake_transcribe

    monkeypatch.setitem(sys.modules, "whisper", fake_whisper)
    monkeypatch.setitem(sys.modules, "whisper.transcribe", fake_transcribe)
    return fake_whisper, fake_model


def test_whisper_asr_construction_and_transcribe_mocked(fake_whisper_module):
    fake_whisper, fake_model = fake_whisper_module
    from funtalk.asr import WhisperASR

    asr = WhisperASR(name="turbo")
    fake_whisper.load_model.assert_called_once_with("turbo")
    assert asr.model is fake_model

    result = asr.transcribe("audio.wav", language="ZH")
    fake_model.transcribe.assert_called_once_with("audio.wav", language="ZH")
    assert result == {"text": "你好，世界"}


# ---------------------------------------------------------------------------
# 3. TTS：BaseTTS 纯函数
# ---------------------------------------------------------------------------


def test_base_tts_parse_voice_name():
    from funtalk.tts.base import BaseTTS

    assert BaseTTS.parse_voice_name("zh-CN-XiaoxiaoNeural-Female") == (
        "zh-CN-XiaoxiaoNeural"
    )
    assert BaseTTS.parse_voice_name("zh-CN-YunxiNeural-Male") == "zh-CN-YunxiNeural"


def test_base_tts_format_text_strips_brackets():
    from funtalk.tts.base import BaseTTS

    text = "hello [world] (foo) {bar}"
    formatted = BaseTTS._format_text(text)
    assert "[" not in formatted
    assert "(" not in formatted
    assert "{" not in formatted


# ---------------------------------------------------------------------------
# 4. TTS：EdgeTTS（mock 掉真实的 edge_tts 网络调用）
# ---------------------------------------------------------------------------


class _FakeCommunicate:
    """替代 edge_tts.Communicate，避免真实联网请求微软 TTS 服务。"""

    def __init__(self, text, voice, rate):
        self.text = text
        self.voice = voice
        self.rate = rate

    def stream_sync(self):
        yield {"type": "audio", "data": b"FAKE_AUDIO_BYTES"}
        yield {
            "type": "WordBoundary",
            "offset": 0,
            "duration": 1000,
            "text": self.text,
        }


def test_edge_tts_construction():
    from funtalk.tts._edge import EdgeTTS

    tts = EdgeTTS(voice_name="zh-CN-XiaoxiaoNeural-Female")
    assert tts.voice_name == "zh-CN-XiaoxiaoNeural"


def test_edge_tts_create_tts_mocked(tmp_path):
    import funtalk.tts._edge as edge_mod

    voice_file = str(tmp_path / "out.mp3")

    with patch.object(edge_mod, "Communicate", _FakeCommunicate):
        tts = edge_mod.EdgeTTS(voice_name="zh-CN-XiaoxiaoNeural-Female")
        sub_maker = tts.create_tts(
            text="hello world",
            voice_rate=1.0,
            voice_file=voice_file,
            subtitle_file=None,
        )

    assert sub_maker is not None
    assert sub_maker.subs == ["hello world"]
    assert sub_maker.offset == [(0, 1000)]
    with open(voice_file, "rb") as f:
        assert f.read() == b"FAKE_AUDIO_BYTES"


def test_edge_tts_generate_function_mocked(tmp_path):
    import funtalk.tts._edge as edge_mod

    voice_file = str(tmp_path / "out2.mp3")

    with patch.object(edge_mod, "Communicate", _FakeCommunicate):
        client = edge_mod.tts_generate(
            text="你好",
            voice_name="zh-CN-XiaoxiaoNeural-Female",
            voice_rate=1.0,
            voice_file=voice_file,
            subtitle_file=None,
        )

    assert client.sub_maker is not None
    assert client.sub_maker.subs == ["你好"]


def test_edge_tts_list_voices_mocked(monkeypatch):
    """list_voices 会真实联网获取语音列表，这里 mock 掉底层协程。"""
    import funtalk.tts._edge as edge_mod

    async def fake_list_voices():
        return [
            {"Name": "zh-CN-XiaoxiaoNeural", "Locale": "zh-CN", "Gender": "Female"},
            {"Name": "en-US-AriaNeural", "Locale": "en-US", "Gender": "Female"},
        ]

    monkeypatch.setattr(edge_mod, "list_voices", fake_list_voices)
    voices = edge_mod.EdgeTTS.list_voices(locale="zh-CN")
    assert len(voices) == 1
    assert voices[0]["Name"] == "zh-CN-XiaoxiaoNeural"


# ---------------------------------------------------------------------------
# 5. TTS：AzureTTS
#
# funvideo.app.config 在 import 时会读取当前工作目录下的 ./config.toml，
# 若不存在会抛出 FileNotFoundError（funvideo 自身的问题，不在本仓库改动范围）。
# 这里通过 chdir 到一个带有最小 config.toml 的临时目录来完成首次 import。
# ---------------------------------------------------------------------------


@pytest.fixture
def azure_tts_class(tmp_path, monkeypatch):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[app]\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from funtalk.tts._azure import AzureTTS

    return AzureTTS


def test_azure_tts_construction(azure_tts_class):
    tts = azure_tts_class(voice_name="zh-CN-XiaoxiaoNeural-Female")
    assert tts.voice_name == "zh-CN-XiaoxiaoNeural"


def test_azure_tts_get_all_voice_name_filters_locale(azure_tts_class):
    tts = azure_tts_class(voice_name="zh-CN-XiaoxiaoNeural-Female")
    voices = tts.get_all_voice_name(filter_locals=["zh-CN"])
    assert len(voices) > 0
    assert all(v.lower().startswith("zh-cn") for v in voices)


def test_azure_tts_check_strips_v2_suffix(azure_tts_class):
    assert azure_tts_class.check("zh-CN-XiaoxiaoMultilingualNeural-V2") == (
        "zh-CN-XiaoxiaoMultilingualNeural"
    )
    assert azure_tts_class.check("zh-CN-XiaoxiaoNeural") == "zh-CN-XiaoxiaoNeural"


def test_azure_tts_generate_without_sdk_returns_none_sub_maker(
    azure_tts_class, tmp_path
):
    """
    未安装 azure-cognitiveservices-speech（真实语音合成 SDK，需要真实 Azure
    订阅凭据才能真正调用）时，AzureTTS._tts 会捕获 ImportError 并重试 3 次后
    返回 None，而不是抛异常——这里验证该降级行为，不做真实的语音合成。
    """
    import funtalk.tts._azure as azure_mod

    voice_file = str(tmp_path / "out.mp3")
    client = azure_mod.tts_generate(
        text="hello",
        voice_name="zh-CN-XiaoxiaoNeural-Female",
        voice_rate=1.0,
        voice_file=voice_file,
        subtitle_file=None,
    )
    assert client.sub_maker is None


def test_azure_tts_real_speech_synthesis_requires_credentials():
    pytest.skip("需要真实 Azure 语音服务订阅凭据，跳过真实合成调用")


def test_whisper_asr_real_model_download_requires_network():
    pytest.skip("需要下载真实 whisper 模型权重，跳过真实 ASR 推理")
