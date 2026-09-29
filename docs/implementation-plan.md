# 声音克隆网站 — 实现方案

## 目标

搭一个「声音克隆 + 语音转文字」的网站：上传一段参考音频即可克隆音色，输入文本合成语音；同时支持上传音频转成文字。全部能力在本机运行，不依赖外部付费服务。

## 硬件与环境约束（本机实测）

选型的前置条件。以下为实测结果，不是假设：

| 项 | 实测结果 | 对方案的影响 |
|---|---|---|
| GPU | 仅 Intel UHD Graphics 730 集显，无 NVIDIA 卡，`nvidia-smi` 不存在 | fish-speech 不可用（官方要求 Linux/WSL + 24GB 显存） |
| 内存 | 15.7 GB | 两个模型常驻需实测；uvicorn 必须单 worker |
| CPU | 16 逻辑核 | CPU 推理可用但慢，是最大不确定性 |
| 系统 | Windows 11 家庭中文版 | 原生 Windows 跑，不进 WSL |
| Python | 3.13.3（`C:\Program Files\Python313`），有 pip；无 uv / conda | 需自建 3.12 venv 规避轮子缺失 |
| 音频工具 | 无 ffmpeg | 依赖包自带解码能力，不引入 ffmpeg |
| Node | v24.16.0，git 2.54.0 | 满足 Next.js 要求 |
| MySQL | 8.0.46 服务运行中，`127.0.0.1:3306`，utf8mb4，`mysql_native_password` | 直接使用。客户端在 `D:\ws-soft\MySql\mysql-8.0.46-winx64\bin\mysql.exe`，不在 PATH |
| WSL2 | 可用（装了 Docker Desktop） | 本方案未使用，留作后备 |

## 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | Next.js（App Router）+ TypeScript + React + Tailwind CSS v4 + shadcn/ui | 用户指定。shadcn 当前 CLI 默认即 Next + Tailwind v4 组合 |
| 数据库 | MySQL 8.0.46（本机），库 `voice_clone` | 已有且在跑 |
| ORM | Drizzle ORM + `mysql2` | 轻量、类型安全、无 codegen 守护进程 |
| 模型服务 | Python 3.12 + FastAPI + uvicorn | 纯 REST，便于 Next.js 代理 |
| 语音转文字 | `faster-whisper` 1.2.1（`small` + `int8`） | CTranslate2 后端，CPU 友好，pip 即装，PyAV 自带解码 |
| 声音克隆 + TTS | `coqui-tts` 0.27.5 + XTTS-v2 | **零样本克隆**：一段参考音频 + 文本即可，免训练；支持中文等 17 语种 |

### 弃用记录

| 方案 | 弃用原因 |
|---|---|
| fish-speech（Fish Audio 开源模型） | 官方要求 Linux/WSL + 推荐 24GB 显存，本机无独显跑不动 |
| Fish Audio 云 API | 最初考虑，后确定要求全本地 |
| Gradio / Streamlit | 最初考虑，后确定用 Next.js |
| SQLite | 初衷方案，后改用户已有的 MySQL |

## 目录结构

```
D:\ws-soft\study\demo\
├─ CLAUDE.md                 项目指引
├─ todo.md                   待办
├─ docs\
│   ├─ implementation-plan.md  本文档
│   ├─ api.md                  接口契约
│   ├─ database.md             建表 DDL
│   └─ fish-audio.md           Fish Audio 云 API 速查（备选方案，未采用）
├─ scripts\
│   └─ dev.bat               一键启动两服务
├─ server\                   Python 模型服务
│   ├─ pyproject.toml
│   ├─ smoke_test.py         可行性验证脚本
│   ├─ SMOKE_TEST.md         验证结果记录
│   ├─ .cache\               模型权重缓存（不入库）
│   └─ app\
│       ├─ main.py           FastAPI 应用与路由
│       ├─ asr.py            faster-whisper 封装
│       ├─ tts.py            XTTS-v2 封装
│       ├─ schemas.py        Pydantic 请求/响应模型
│       └─ config.py         环境变量与模型配置
└─ web\                      Next.js 前端
    ├─ app\
    │   ├─ page.tsx          首页
    │   ├─ clone\page.tsx    声音克隆
    │   ├─ transcribe\page.tsx 语音转文字
    │   ├─ voices\page.tsx   音色库与历史
    │   └─ api\…             服务端路由（见 api.md）
    ├─ components\           shadcn/ui 组件 + 业务组件
    ├─ db\
    │   ├─ schema.ts         Drizzle 表定义
    │   └─ index.ts          连接池
    └─ data\                 运行时音频（不入库）
        ├─ refs\             参考音频
        └─ audio\            生成音频
```

## 架构

```
浏览器
  │  multipart 上传 / JSON
  ▼
Next.js (127.0.0.1:3000)
  ├─ 服务端路由 /api/*：校验、落库、管文件
  │        │  HTTP 代理
  │        ▼
  │  Python 模型服务 (127.0.0.1:8000)   ← 模型常驻内存
  │        ├─ /asr    faster-whisper
  │        └─ /tts    XTTS-v2 零样本克隆
  └─ MySQL (127.0.0.1:3306)  元数据
     磁盘 data/refs、data/audio  音频文件
```

分层原则：**音频文件只在 Next.js 侧落盘与读取**，Python 服务无状态、不碰数据库，只做「音频字节 → 文本」和「文本 + 参考音频 → 音频字节」的纯计算。这样模型服务可独立重启与替换。

## 阶段划分

「先冻结契约与数据 → 后端与骨架 → 三条竖切 → 收尾」，竖切阶段每段都端到端可用。

| 阶段 | 内容 | 产出 | 门禁 |
|---|---|---|---|
| **P0** | 环境与可行性验证 | 装 uv、建 3.12 venv、装 faster-whisper + coqui-tts，跑 `smoke_test.py` 实测克隆与识别耗时，结果写 `server/SMOKE_TEST.md` | **停下来评审**，速度不可接受则回到选型 |
| **P1** | 契约与数据层冻结 | 建 `voice_clone` 库与两张表、Drizzle schema、写 `docs/` 三份文档、更新 `CLAUDE.md` | 表可查、文档齐全 |
| **P2** | Python 模型服务 | `server/app/` 实现 `/health` `/asr` `/tts`，curl 自测通过 | 三个端点独立可用 |
| **P3** | Next.js 骨架 | 脚手架 + shadcn 初始化与组件 + 路由布局 + 音频上传/播放共用组件 + `db/index.ts` | 空页面能开，DB 连通 |
| **P4** | 语音转文字竖切 | `/transcribe` 页面 + `/api/asr` | 浏览器上传音频出文本 |
| **P5** | 声音克隆竖切 | `/clone` 页面 + `/api/tts` + `/api/voices` + `/voices` 音色库 | 上传参考音频 → 克隆 → 试听 → 落库 |
| **P6** | 历史与收尾 | `/api/generations` + 历史列表 + 错误处理与 loading 态 | 历史可见可播放 |
| **P7** | 端到端验收 | 完整走一遍全流程；回填 `CLAUDE.md`、勾掉 `todo.md` | 无报错 |

## 启动与部署

端口分配：

| 服务 | 地址 | 启动方式 |
|---|---|---|
| MySQL | `127.0.0.1:3306` | 已有 Windows 服务，随系统自启 |
| Python 模型服务 | `127.0.0.1:8000` | 手动 / `scripts/dev.bat` |
| Next.js | `127.0.0.1:3000` | 手动 / `scripts/dev.bat` |

全部绑定 `127.0.0.1`，不对外暴露。

启动顺序与命令：

```bash
# 1) 模型服务（首次运行会自动下载模型权重到 server/.cache）
cd server
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1

# 2) 前端
cd web
npm run dev
```

`scripts/dev.bat` 用 `start` 各开一个窗口依次拉起两个服务，启动前检查 `8000` / `3000` 是否已被占用。

> **`--workers 1` 是硬性要求**：模型常驻内存，多 worker 会各自加载一份，15.7GB 内存会被撑爆。

### 环境变量

`server/.env`：

| 变量 | 示例值 | 说明 |
|---|---|---|
| `DEVICE` | `cpu` | 本机无独显 |
| `WHISPER_MODEL` | `small` | 可调 `base`（更快）/ `medium`（更准） |
| `WHISPER_COMPUTE_TYPE` | `int8` | CPU 量化 |
| `TTS_SPEAKER_LANG` | `zh` | 默认合成语言 |
| `HF_HOME` | `server/.cache/hf` | whisper 权重缓存 |
| `TTS_HOME` | `server/.cache/tts` | XTTS 权重缓存 |

`web/.env.local`：

```ini
MYSQL_URL=mysql://root:123456@127.0.0.1:3306/voice_clone
MODEL_API_BASE=http://127.0.0.1:8000
```

### 忽略清单

`web/.env.local`、`server/.env`、`web/data/`、`server/.cache/`、`__pycache__/`、`node_modules/`、`.venv/`

## 关键风险

- **CPU 速度是最大不确定性**。XTTS-v2 无 GPU 时零样本克隆预计 1~3 倍实时率或更慢，长文本更明显。P0 就是为了量化这一点；若不可接受，妥协方向是限制文本长度上限、缓存音色参考编码。
- **`coqui-tts` 在 Python 3.13 的轮子覆盖不确定**，用固定 3.12 venv 规避。
- **XTTS-v2 权重许可为 CPML（Coqui Public Model License），仅限非商业**。本项目为学习 demo 属允许范围，转商用需换模型。
- **内存**：whisper + XTTS 同时驻留需实测；必要时让 XTTS 懒加载或在空闲时卸载。
- **无 ffmpeg**：参考音频统一走 `soundfile` / `torchaudio` 读取，避免引入 ffmpeg 依赖。
- **中文断句**：XTTS-v2 对中文长句的停顿控制有限，可能需要按标点预先切分再逐段合成。

## 验证方式

- **P0**：`uv run python smoke_test.py` 产出 wav、文本正确、打印实时率
- **P1**：`mysql -uroot -p123456 -e "SHOW TABLES" voice_clone` 显示两张表
- **P2**：`curl 127.0.0.1:8000/health`；`curl -F audio=@test.wav 127.0.0.1:8000/asr`；`curl -F text=你好 -F ref_audio=@a.wav 127.0.0.1:8000/tts -o out.wav`
- **P3~P6**：`npm run dev` 后浏览器逐个操作页面，用 MySQL 客户端核对 `voices` / `generations` 记录与音频文件是否对应
- **P7**：完整走「上传参考音频 → 克隆 → 试听 → 语音转文字 → 查历史」，确认无报错
