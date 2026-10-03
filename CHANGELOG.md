# 更新日志

## [未发布]

### 修复

- Azure TTS（`AzureTTS._tts`）此前调用 `speak_text_async(text)`，`voice_rate`
  形参从未被实际使用，合成语音恒为默认语速；改为通过 SSML
  `<prosody rate="...">` 传递语速，与 EdgeTTS 行为一致。
- `pyproject.toml` 的 `description` 补全为实际功能描述（原值只是包名）。
- README 的 TTS 最小示例显式标注 `subtitle_file` 依赖可选依赖
  `funtalk[tts]`（moviepy），避免按基础安装运行示例时报错。
- `_edge.py`/`_azure.py` 的 `tts_generate` 公开函数补齐参数与返回值的
  中文 docstring；`convert_rate_to_percent` 补齐 docstring 并与
  `EdgeTTS.__init__` 一起补齐类型标注。

### 变更

- 语速百分比换算函数 `convert_rate_to_percent` 从 `funtalk.tts._edge`
  移至 `funtalk._util`，供 EdgeTTS 与 AzureTTS 共用（`_edge` 模块仍重新
  导出，向后兼容）。
- `.gitignore` 补充 `*.rar`。

## [1.0.31] - 2026-09-21

### 新增

- 增加 `tts` 和 `asr` 可选依赖组，按功能隔离较重依赖。

### 修复

- 使用 `farlog` 统一日志，移除语音列表诊断输出，并使用专用 TTS 异常。

### 变更

- 支持 Python 3.10，补齐公开 API 类型标注和中文文档。

### 废弃

- 无。
