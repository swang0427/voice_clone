# Fish Audio 使用速查

> **状态：备选方案，未采用。** 本项目最终走全本地开源部署（见 [实现方案](implementation-plan.md)），
> 原因是要求不依赖外部付费服务。本文档保留作为将来若改用云 API 时的参考。

Fish Audio 是 AI 语音平台，提供文本转语音（TTS）、音色克隆和实时流式合成能力。

> 来源：Context7 库 `/websites/fish_audio`（官方文档站点 `docs.fish.audio`）与 `/fishaudio/fish-audio-python`。
> 查询日期：2026-09-29。代码片段保留原文，未作改写。

## 认证

API Key 从 fish.audio 后台获取，通过 `Authorization` 请求头传递：

```
Authorization: Bearer $FISH_API_KEY
```

推荐存放在环境变量中，不要硬编码到代码或提交到仓库。

## REST API

基础地址：`https://api.fish.audio/v1`

### POST /tts — 一次性合成

返回完整音频数据。

```bash
curl --request POST https://api.fish.audio/v1/tts \
    --header "Authorization: Bearer $FISH_API_KEY" \
    --header "Content-Type: application/json" \
    --header "model: s2-pro" \
    --data '{ "text": "Hello from Fish Audio!", "format": "mp3" }' \
    --output hello.mp3
```

### POST /tts/stream — 分块流式

逐块返回音频，适合边生成边播放。

### POST /tts/stream/with-timestamp — 带时间戳流式

```bash
curl --no-buffer --request POST \
  --url https://api.fish.audio/v1/tts/stream/with-timestamp \
  --header 'Authorization: Bearer <token>' \
  --header 'Content-Type: application/json' \
  --header 'model: s2-pro' \
  --data '{
    "text": "Hello! Welcome to Fish Audio.",
    "reference_id": "model-id",
    "format": "opus",
    "latency": "balanced"
  }'
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | string | 是 | 待合成文本 |
| `reference_id` | string | 否 | 音色 ID（覆盖 `config.reference_id`） |
| `references` | list[ReferenceAudio] | 否 | 参考音频样本，用于即时克隆（覆盖 `config.references`） |
| `format` | AudioFormat | 否 | `mp3` / `wav` / `pcm` / `opus`（覆盖 `config.format`） |
| `latency` | LatencyMode | 否 | `normal` / `balanced`（覆盖 `config.latency`） |
| `speed` | float | 否 | 语速倍率，如 `1.5` 表示 1.5 倍速（覆盖 `config.prosody.speed`） |
| `config` | TTSConfig | 否 | 音频、音色、模型参数的完整配置对象 |
| `model` | Model | 否 | 使用的 TTS 模型，默认 `s2-pro` |

## Python SDK

官方库 `fishaudio`。

```bash
pip install fishaudio
```

### 同步与异步客户端

```python
import asyncio
from fishaudio import AsyncFishAudio

async def main():
    # Basic initialization
    client = AsyncFishAudio()

    # With explicit API key
    client = AsyncFishAudio(api_key="your_api_key")

    # Generate audio
    audio = await client.tts.convert(text="Hello world")
    await client.close()

asyncio.run(main())
```

### 一次性合成

`convert()` 是便捷方法：内部把流式分块全部收集后合并返回完整音频。需要逐块处理时改用 `stream()`。

```python
from fishaudio import FishAudio
from fishaudio.utils import play, save

client = FishAudio(api_key="...")

# Get complete audio
audio = client.tts.convert(text="Hello world")

# Play it
play(audio)

# Or save it
save(audio, "output.mp3")
```

### 流式合成

```python
from fishaudio import FishAudio

client = FishAudio(api_key="...")

# Simple streaming
for chunk in client.tts.stream(text="Hello, world!"):
    process_chunk(chunk)

# With format control
audio_stream = client.tts.stream(
    text="Hello, world!",
    format="wav"
)

# With speed control
for chunk in client.tts.stream(
    text="Hello, world!",
    speed=1.5  # 1.5x speed
):
    write_to_file(chunk)

# Collect all at once
audio = client.tts.stream(text="Hello, world!").collect()
with open("output.mp3", "wb") as f:
    f.write(audio)
```

### 异步流式收集

```python
import asyncio
from fishaudio import AsyncFishAudio

async def main():
    client = AsyncFishAudio(api_key="...")

    # Collect audio from async stream
    stream = await client.tts.stream(text="Hello!")
    audio = await stream.collect()

    # Save audio
    with open("output.mp3", "wb") as f:
        f.write(audio)

asyncio.run(main())
```

### WebSocket 流式

适合长文本逐句生成。文本以可迭代对象（生成器）形式传入，边生成边合成。

```python
from fishaudio import FishAudio, WebSocketOptions

client = FishAudio(api_key="...")

# Simple text generator
def text_generator():
    yield "Hello, "
    yield "this is "
    yield "streaming text!"

# Stream and save
with open("output.mp3", "wb") as f:
    for audio_chunk in client.tts.stream_websocket(text_generator()):
        f.write(audio_chunk)

# With format and speed control
with open("output.wav", "wb") as f:
    for chunk in client.tts.stream_websocket(
        text_generator(),
        format="wav",
        speed=1.3
    ):
        f.write(chunk)

# With WebSocket options for long-running generations
ws_options = WebSocketOptions(keepalive_ping_timeout_seconds=60.0)
with open("output.mp3", "wb") as f:
    for chunk in client.tts.stream_websocket(
        text_generator(),
        ws_options=ws_options
    ):
        f.write(chunk)

# Using FlushEvent to force immediate synthesis
from fishaudio import TextEvent, FlushEvent

def advanced_generator():
    yield TextEvent(text="First sentence.")
    yield FlushEvent()  # Force synthesis of buffered text
    yield "Second sentence."

for chunk in client.tts.stream_websocket(advanced_generator()):
    process_audio(chunk)
```

## 音色克隆

两条路径：即时克隆不落库，只在单次请求内生效；持久化音色模型生成后可反复用 `reference_id` 引用。

### 即时克隆（不落库）

```python
from fishaudio.types import ReferenceAudio

with open("reference.wav", "rb") as f:
    audio = client.tts.convert(
        text="This will sound like the reference voice.",
        references=[ReferenceAudio(
            audio=f.read(),
            text="The exact words spoken in the reference clip.",
        )],
    )
```

`ReferenceAudio` 需要音频数据 **和** 该段音频的原文文本（用于对齐音色）。

### 持久化音色模型

```python
def create(
    self,
    *,
    title: str,
    voices: list[bytes],
    description: Optional[str] = OMIT,
    texts: Optional[list[str]] = OMIT,
    tags: Optional[list[str]] = OMIT,
    cover_image: Optional[bytes] = OMIT,
    visibility: Visibility = "private",
    train_mode: str = "fast",
    enhance_audio_quality: bool = True,
    request_options: Optional[RequestOptions] = None,
) -> Voice
```

```python
from fishaudio import FishAudio

client = FishAudio(api_key="...")

# Clone voice from multiple samples
voices_list = []
for filename in ["sample1.wav", "sample2.wav", "sample3.wav"]:
    with open(filename, "rb") as f:
        voices_list.append(f.read())

voice = client.voices.create(
    title="My Custom Voice",
    voices=voices_list,
    description="A voice clone of myself",
    tags=["personal", "english"],
    visibility="private"
)

print(f"Created voice: {voice.id}")
print(f"Status: {voice.state}")
```

## JavaScript SDK

实时流式 TTS 走 WebSocket，文本以 `AsyncIterable<string>` 传入。

### textToSpeech.convertRealtime()

发起 realtime 流式合成会话。

- 参数：`request`（TTSRequest，必填）、`textStream`（AsyncIterable\<string\>，必填）、`backend`（Backends，可选）
- 返回：`RealtimeConnection`

## 相关链接

- 官方文档：`docs.fish.audio`
- Python SDK 源码：`github.com/fishaudio/fish-audio-python`
- 开源模型（本地部署路线）：`github.com/fishaudio/fish-speech`
