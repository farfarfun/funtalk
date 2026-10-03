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

关于 funvideo（farfarfun/todo-list#156）：funtalk 之前 `import funvideo` 来获取
`split_string_by_punctuations()` 和 Azure 语音凭据（`funvideo.app.config.config`），
而 funvideo 的 pyproject.toml 又声明依赖 funtalk，构成循环依赖。已修复：
`split_string_by_punctuations` 复制为本地的 `funtalk._util`（纯函数，无第三方依赖），
Azure 凭据改为直接读环境变量 `AZURE_SPEECH_KEY`/`AZURE_SPEECH_REGION`，不再依赖
funvideo 的全局 config 单例（该单例本身在 import 时还有读取 `./config.toml` 的
副作用）。funtalk 现在完全不 import funvideo。
"""

import asyncio
import re
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


def test_split_string_by_punctuations_is_local_to_funtalk():
    """#156: this used to be funvideo.app.utils.utils.split_string_by_punctuations."""
    import sys

    from funtalk._util import split_string_by_punctuations

    assert split_string_by_punctuations("你好，世界。这是一个测试！") == [
        "你好",
        "世界",
        "这是一个测试",
    ]
    # decimal points aren't treated as sentence breaks
    assert split_string_by_punctuations("单价2.5元") == ["单价2.5元"]
    assert "funvideo" not in sys.modules


def test_edge_voice_listing_has_no_stdout(monkeypatch, capsys):
    """列出语音不应把诊断信息写到标准输出。"""
    import funtalk.tts._edge as edge_mod

    async def fake_list_voices():
        return [{"Name": "x", "Locale": "zh-CN", "Gender": "Female"}]

    monkeypatch.setattr(edge_mod, "list_voices", fake_list_voices)
    assert edge_mod.EdgeTTS.list_voices() == [{"Name": "x", "Locale": "zh-CN", "Gender": "Female"}]
    assert capsys.readouterr().out == ""


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
# ---------------------------------------------------------------------------


@pytest.fixture
def azure_tts_class():
    from funtalk.tts._azure import AzureTTS

    return AzureTTS


def test_azure_tts_reads_credentials_from_env_not_funvideo_config(
    azure_tts_class, tmp_path, monkeypatch
):
    """Azure SDK 配置应直接读取环境变量，且不导入 funvideo。"""
    import sys

    assert "funvideo" not in sys.modules

    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "test-region")
    speechsdk, speech_config = _install_fake_azure_sdk(monkeypatch)
    client = azure_tts_class(voice_name="zh-CN-XiaoxiaoNeural-Female")

    result = client._tts("你好", 1.0, str(tmp_path / "out.mp3"))

    speechsdk.SpeechConfig.assert_called_once_with(
        subscription="test-key", region="test-region"
    )
    assert result.subs == ["你好"]
    assert result.offset == [(0, 10000000)]
    assert speech_config.speech_synthesis_voice_name == "zh-CN-XiaoxiaoNeural"


def test_azure_tts_applies_voice_rate_via_ssml(azure_tts_class, tmp_path, monkeypatch):
    """回归测试：voice_rate 必须真正传给 Azure，而不是被静默忽略。

    此前 `_tts` 调用 `speak_text_async(text)`，voice_rate 形参从未被使用，
    合成结果恒为默认语速。修复后通过 SSML `<prosody rate="...">` 生效。
    """
    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "test-region")
    speechsdk, _ = _install_fake_azure_sdk(monkeypatch)
    client = azure_tts_class(voice_name="zh-CN-XiaoxiaoNeural-Female")

    client._tts("你好", 1.5, str(tmp_path / "out.mp3"))

    assert len(speechsdk.synthesizers) == 1
    ssml = speechsdk.synthesizers[0].last_ssml
    assert '<prosody rate="+50%">' in ssml
    assert 'xml:lang="zh-CN"' in ssml
    assert '<voice name="zh-CN-XiaoxiaoNeural">' in ssml
    assert "你好" in ssml


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


def _install_fake_azure_sdk(monkeypatch, *, reason="completed", failure=None):
    """安装最小 Azure SDK 桩，并返回 SDK 模块和语音配置对象。"""
    speechsdk = types.ModuleType("azure.cognitiveservices.speech")
    speech_config = MagicMock()
    speechsdk.SpeechConfig = MagicMock(return_value=speech_config)
    speechsdk.PropertyId = types.SimpleNamespace(
        SpeechServiceResponse_RequestWordBoundary="word-boundary"
    )
    speechsdk.SpeechSynthesisOutputFormat = types.SimpleNamespace(
        Audio48Khz192KBitRateMonoMp3="mp3"
    )
    speechsdk.ResultReason = types.SimpleNamespace(
        SynthesizingAudioCompleted="completed", Canceled="canceled"
    )
    speechsdk.CancellationReason = types.SimpleNamespace(Error="error")
    speechsdk.SessionEventArgs = object
    speechsdk.audio = types.SimpleNamespace(AudioOutputConfig=MagicMock())

    class FakeSignal:
        def __init__(self):
            self.callback = None

        def connect(self, callback):
            self.callback = callback

    synthesizers = []

    class FakeSynthesizer:
        def __init__(self, **kwargs):
            self.synthesis_word_boundary = FakeSignal()
            self.last_ssml = None
            synthesizers.append(self)

        def speak_ssml_async(self, ssml):
            self.last_ssml = ssml
            if failure is not None:
                raise failure
            if reason == "completed":
                # 从 SSML 的 <prosody> 内容里取出原始文本，模拟 Azure 真实
                # 按合成文本（而非整段 SSML）触发 word boundary 事件的行为。
                match = re.search(r"<prosody[^>]*>(.*?)</prosody>", ssml, re.DOTALL)
                spoken_text = match.group(1) if match else ssml
                event = types.SimpleNamespace(
                    duration="00:00:01.000000", audio_offset=0, text=spoken_text
                )
                self.synthesis_word_boundary.callback(event)
            details = types.SimpleNamespace(
                reason="error", error_details="凭据无效"
            )
            result = types.SimpleNamespace(
                reason=reason, cancellation_details=details
            )
            return types.SimpleNamespace(get=lambda: result)

    speechsdk.SpeechSynthesizer = FakeSynthesizer
    speechsdk.synthesizers = synthesizers
    azure = types.ModuleType("azure")
    cognitive = types.ModuleType("azure.cognitiveservices")
    azure.cognitiveservices = cognitive
    cognitive.speech = speechsdk
    monkeypatch.setitem(sys.modules, "azure", azure)
    monkeypatch.setitem(sys.modules, "azure.cognitiveservices", cognitive)
    monkeypatch.setitem(sys.modules, "azure.cognitiveservices.speech", speechsdk)
    return speechsdk, speech_config


def test_azure_tts_cancellation_raises_domain_error(
    azure_tts_class, tmp_path, monkeypatch
):
    from funtalk.tts._azure import AzureSynthesisError

    _install_fake_azure_sdk(monkeypatch, reason="canceled")
    client = azure_tts_class(voice_name="zh-CN-XiaoxiaoNeural-Female")

    with pytest.raises(AzureSynthesisError, match="凭据无效"):
        client._tts("你好", 1.0, str(tmp_path / "out.mp3"))


def test_azure_tts_runtime_error_preserves_cause(
    azure_tts_class, tmp_path, monkeypatch
):
    from funtalk.tts._azure import AzureSynthesisError

    failure = RuntimeError("服务不可用")
    _install_fake_azure_sdk(monkeypatch, failure=failure)
    client = azure_tts_class(voice_name="zh-CN-XiaoxiaoNeural-Female")

    with pytest.raises(AzureSynthesisError) as exc_info:
        client._tts("你好", 1.0, str(tmp_path / "out.mp3"))
    assert exc_info.value.__cause__ is failure


def test_azure_tts_real_speech_synthesis_requires_credentials():
    pytest.skip("需要真实 Azure 语音服务订阅凭据，跳过真实合成调用")


def test_whisper_asr_real_model_download_requires_network():
    pytest.skip("需要下载真实 whisper 模型权重，跳过真实 ASR 推理")


def test_whisper_asr_on_progress_reports_real_frame_progress():
    """真实加载 tiny 模型、真实转写一段随机噪声音频，断言 on_progress 回调
    收到了单调递增、最终到 1.0 的百分比序列——不是只测 import/mock。

    用纯静音/低幅度噪声作为输入时，whisper 内部的 no-speech 检测会在
    `if should_skip: seek += segment_size; continue` 直接跳过整个 segment，
    根本不会执行到 `pbar.update(...)` 那一行（实测验证过：静音输入下
    on_progress 一次都不会被调用）。这里传 `no_speech_threshold=None`
    （whisper.transcribe 的真实公开参数）关掉这个跳过优化，只是为了让测试
    音频也能走到 pbar.update 那条路径，不是在 mock 或绕过被测代码本身。
    """
    np = pytest.importorskip("numpy")

    from funtalk.asr import WhisperASR

    asr = WhisperASR(name="tiny")

    rng = np.random.default_rng(0)
    audio = (rng.standard_normal(16000 * 90) * 0.05).astype(np.float32)

    progress_values = []
    result = asr.transcribe(
        audio,
        language="zh",
        on_progress=progress_values.append,
        no_speech_threshold=None,
    )

    assert isinstance(result, dict)
    assert "text" in result
    assert len(progress_values) > 0, "on_progress 回调一次都没被调用"
    assert all(0.0 <= p <= 1.0 for p in progress_values)
    assert progress_values == sorted(progress_values), "进度值应该单调递增"
    assert progress_values[-1] == 1.0


def test_whisper_asr_transcribe_without_on_progress_still_works():
    """确认不传 on_progress 时（现有调用方式）行为不受影响。"""
    np = pytest.importorskip("numpy")

    from funtalk.asr import WhisperASR

    asr = WhisperASR(name="tiny")
    audio = np.zeros(16000 * 5, dtype=np.float32)

    result = asr.transcribe(audio, language="zh")
    assert isinstance(result, dict)
    assert "text" in result
