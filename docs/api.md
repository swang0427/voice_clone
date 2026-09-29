# 接口契约

两套接口：Python 模型服务（内部，仅 Next.js 调用）与 Next.js 服务端路由（浏览器调用）。

错误响应统一为 `{ "detail": "错误说明" }`。

---

## 一、Python 模型服务

基址 `http://127.0.0.1:8000`。无状态，不连数据库，不落盘。

### GET /health

存活与模型加载状态。

**200**

```json
{
  "status": "ok",
  "asr_loaded": true,
  "tts_loaded": true,
  "device": "cpu"
}
```

`status` 取值：`ok`（全部就绪）、`loading`（模型仍在加载）、`degraded`（有模型加载失败，需看 `asr_loaded` / `tts_loaded`）。

### POST /asr

音频转文字。

**请求** `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `audio` | file | 是 | 待识别音频 |
| `language` | string | 否 | 语言代码如 `zh` / `en`；不传则自动检测 |

**200**

```json
{
  "text": "识别出的完整文本",
  "language": "zh",
  "duration": 5.42,
  "elapsed": 3.10,
  "segments": [
    { "start": 0.0, "end": 2.1, "text": "第一段" },
    { "start": 2.1, "end": 5.42, "text": "第二段" }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `text` | 完整转录文本 |
| `language` | 检测到的语言代码 |
| `duration` | 音频时长（秒） |
| `elapsed` | 推理耗时（秒），用于观察实时率 |
| `segments` | 分段时间戳 |

**错误**

| 状态码 | 场景 |
|---|---|
| 400 | 音频解码失败 / 未提供 `audio` |
| 503 | ASR 模型未加载完成 |

### POST /tts

文本转语音，用参考音频做零样本音色克隆。

**请求** `multipart/form-data`

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `text` | string | 是 | — | 待合成文本，**上限 500 字** |
| `ref_audio` | file | 是 | — | 参考音频，**时长需在 3~30 秒** |
| `language` | string | 否 | `zh` | 合成语言 |
| `speed` | float | 否 | `1.0` | 语速倍率，建议范围 0.5~2.0 |

**200**

返回 `audio/wav` 二进制流，响应头：

```
Content-Type: audio/wav
X-Elapsed-Seconds: 12.34
X-Audio-Duration: 6.80
```

`X-Elapsed-Seconds` 为推理耗时，`X-Audio-Duration` 为生成音频时长，两者相除即实时率。

**错误**

| 状态码 | 场景 |
|---|---|
| 400 | `text` 为空或超过 500 字 |
| 400 | 参考音频时长不在 3~30 秒 |
| 400 | 参考音频解码失败 |
| 503 | TTS 模型未加载完成 |

---

## 二、Next.js 服务端路由

基址 `http://127.0.0.1:3000`。负责校验、文件落盘、数据库读写，并代理到 Python 服务。

### POST /api/asr

透传至 Python `/asr`，原样返回其 JSON。

**请求** `multipart/form-data`：`audio`(file, 必填)、`language`(string, 可选)

**200**：与 Python `/asr` 的 200 响应一致

**错误**：模型服务不可达 → 502；模型服务返回 4xx/503 → 原样透传

### POST /api/tts

**请求** `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | string | 是 | 待合成文本，上限 500 字 |
| `voice_id` | string | 是 | `voices` 表主键 |
| `speed` | string | 否 | 语速倍率，默认 `1.0` |

服务端流程：查 `voices` → 读参考音频文件 → 调 Python `/tts` → 音频存为 `data/audio/{uuid}.wav` → 插入 `generations` → 返回。

**200**

```json
{
  "generation_id": 12,
  "audio_url": "/api/audio/7f3a1c2e-....wav",
  "duration": 6.80,
  "elapsed": 12.34
}
```

**错误**

| 状态码 | 场景 |
|---|---|
| 400 | `text` 为空或超过 500 字 / 缺 `voice_id` |
| 404 | `voice_id` 不存在，或参考音频文件已丢失 |
| 502 | Python 模型服务不可达 |

### GET /api/voices

音色列表。

**查询参数**

| 参数 | 默认 | 说明 |
|---|---|---|
| `q` | — | 按名称模糊搜索 |
| `page` | `1` | 页码，从 1 开始 |
| `page_size` | `20` | 每页条数，上限 100 |

**200**

```json
{
  "total": 3,
  "items": [
    {
      "id": 1,
      "name": "我的声音",
      "description": "用手机录的",
      "ref_audio_url": "/api/refs/9b2d....wav",
      "duration": 8.50,
      "created_at": "2026-09-29T15:40:00.000Z"
    }
  ]
}
```

### POST /api/voices

新建音色。

**请求** `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | 是 | 音色名，上限 100 字 |
| `description` | string | 否 | 描述，上限 500 字 |
| `ref_audio` | file | 是 | 参考音频，时长 3~30 秒 |

服务端流程：参考音频存为 `data/refs/{uuid}.wav` → 插入 `voices` → 返回音色对象（结构同列表项）。

**错误**

| 状态码 | 场景 |
|---|---|
| 400 | `name` 为空或超长 / 缺 `ref_audio` / 参考音频时长越界或解码失败 |

### DELETE /api/voices/[id]

删除音色：删数据库记录 + 删参考音频文件。`generations` 中相关记录**保留**，`voice_id` 被置空（外键 `ON DELETE SET NULL`），前端显示「音色已删除」。

**200**：`{ "deleted": true }`

**404**：`id` 不存在

### GET /api/generations

生成历史。

**查询参数**：`voice_id`（可选，筛选）、`page`（默认 1）、`page_size`（默认 20，上限 100）

**200**

```json
{
  "total": 8,
  "items": [
    {
      "id": 12,
      "voice_id": 1,
      "voice_name": "我的声音",
      "text": "合成的文本内容",
      "audio_url": "/api/audio/7f3a....wav",
      "duration": 6.80,
      "elapsed": 12.34,
      "created_at": "2026-09-29T15:40:00.000Z"
    }
  ]
}
```

`voice_id` 为 `null` 时 `voice_name` 返回 `null`，前端显示「音色已删除」。

### GET /api/audio/[name]

读取 `web/data/audio/` 下的音频文件。

### GET /api/refs/[name]

读取 `web/data/refs/` 下的参考音频。

**200**：`audio/wav` 二进制流，`Content-Type: audio/wav`

**400**：`name` 不匹配 `^[a-f0-9-]+\.wav$`
**404**：文件不存在

---

## 三、安全约定

- **文件名一律由服务端用 UUID 生成**，浏览器从不参与命名。
- **读取音频时用正则白名单校验文件名**（`^[a-f0-9-]+\.wav$`），不接受含 `/`、`\`、`..` 的片段 —— 防目录穿越。
- 文本与名称做长度上限校验（`text` 500 字、`name` 100 字、`description` 500 字）。
- 参考音频时长校验在 Python 侧执行（解码后才能知道真实时长），Next.js 侧只做文件存在性与大小预检。
- 所有服务只绑 `127.0.0.1`，不对局域网暴露。
