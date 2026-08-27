# funtalk

语音相关的小工具库，封装了 TTS（文字转语音）和 ASR（语音转文字）两部分，主要配合 [funvideo](https://github.com/farfarfun/funvideo) 项目使用，用来给自动生成的视频配音、生成对齐的字幕文件。

## 安装

```bash
pip install funtalk
```

注意：仓库的 `pyproject.toml` 目前没有声明任何运行依赖（`dependencies = []`），实际使用时需要自行安装 `edge-tts`、`openai-whisper`、`funutil`、`moviepy`，如果要用 Azure TTS 还需要 `azure-cognitiveservices-speech`。TTS 模块还直接 `import` 了 `funvideo.app.utils` / `funvideo.app.config`（属于对 funvideo 内部模块的紧耦合），脱离 funvideo 项目单独使用会因为缺依赖而报错。

## TTS：文字转语音

```python
from funtalk.tts import tts_generate  # 包一级导出的默认是 edge-tts 实现

tts_generate(
    text="你好，世界",
    voice_name="zh-CN-XiaoxiaoNeural",
    voice_rate=1.0,
    voice_file="out.mp3",
    subtitle_file="out.srt",
)
```

`BaseTTS`（`funtalk/tts/base.py`）定义了统一接口：`create_tts()` 生成音频，并能根据引擎返回的时间戳，把文本按标点切分对齐后生成 SRT 字幕（`create_subtitle`）。目前有两个实现：

- `funtalk.tts._edge.EdgeTTS`：基于 [edge-tts](https://github.com/rany2/edge-tts)，包一级导出的 `tts_generate` / `edge_tts_generate` 就是它。
- `funtalk.tts._azure.AzureTTS`：基于 Azure 认知服务语音合成，需要从 `funtalk.tts._azure` 单独导入，依赖 `azure-cognitiveservices-speech` 以及 funvideo 配置里的 `speech_key`/`speech_region`。

## ASR：语音转文字

```python
from funtalk.asr import WhisperASR

asr = WhisperASR(name="turbo")  # 基于 openai-whisper
result = asr.transcribe("audio.mp3", language="ZH")
```

`BaseASR`（`funtalk/asr/base.py`）定义了 `load()` / `transcribe()` 接口，目前只有 `WhisperASR` 一个实现。
