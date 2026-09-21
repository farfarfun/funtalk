# funtalk

语音相关的小工具库，封装了 TTS（文字转语音）和 ASR（语音转文字）两部分，主要配合 [funvideo](https://github.com/farfarfun/funvideo) 项目使用，用来给自动生成的视频配音、生成对齐的字幕文件。

## 安装

```bash
pip install funtalk
```

基础 TTS 依赖已在项目配置中声明；按需安装可选功能：

```bash
pip install 'funtalk[tts]'  # 字幕校验和 TTS 工具
pip install 'funtalk[asr]'  # Whisper ASR（包含较重的模型依赖）
pip install 'funtalk[azure]'  # Azure TTS SDK
```

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
- `funtalk.tts._azure.AzureTTS`：基于 Azure 认知服务语音合成，需要从 `funtalk.tts._azure` 单独导入，并设置 `AZURE_SPEECH_KEY` 与 `AZURE_SPEECH_REGION` 环境变量。

## ASR：语音转文字

```python
from funtalk.asr import WhisperASR

asr = WhisperASR(name="turbo")  # 基于 openai-whisper
result = asr.transcribe("audio.mp3", language="ZH")
```

`BaseASR`（`funtalk/asr/base.py`）定义了 `load()` / `transcribe()` 接口，目前只有 `WhisperASR` 一个实现。

---

## 关于 farfarfun

[farfarfun](https://github.com/farfarfun) 是一个专注于实用工具库的开源组织，
涵盖云存储、数据处理、AI、多媒体与开发工具链等方向。

- 🏠 组织主页：<https://github.com/farfarfun>
- 📦 PyPI：<https://pypi.org/user/niuliangtao/>
- 📧 联系：farfarfun@qq.com

本项目基于 [MIT](LICENSE) 协议开源。
