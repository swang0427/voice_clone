# 项目说明

## 项目简介

声音克隆 + 语音转文字网站。上传一段参考音频即可克隆音色并合成语音，同时支持把音频转成文字。全部能力在本机运行，不依赖外部付费服务。

## 技术栈

- **前端**：Next.js（App Router）+ TypeScript + React + Tailwind CSS v4 + shadcn/ui
- **模型服务**：Python 3.12 + FastAPI（仅本机调用，`127.0.0.1:8000`）
- **语音转文字**：faster-whisper（`small` + `int8`）
- **声音克隆 / TTS**：coqui-tts + XTTS-v2（零样本克隆，免训练）
- **数据库**：MySQL 8.0.46（本机，库 `voice_clone`）+ Drizzle ORM

选型理由、被否方案与完整阶段划分见 [实现方案](docs/implementation-plan.md)。

## 关键环境约束

- **本机无 NVIDIA 显卡**（仅 Intel UHD Graphics 730 集显），fish-speech 这类需要大显存的方案不可用，模型一律按 CPU 路径选型。
- **内存 15.7 GB**，模型服务启动必须带 `--workers 1`，否则多份模型常驻会撑爆内存。
- **无 ffmpeg**，音频读写统一走 `soundfile` / `torchaudio`，不要引入 ffmpeg 依赖。
- 系统 Python 是 3.13，本项目的 venv 固定用 **3.12**。

## 常用命令

```bash
# 模型服务
cd server
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1

# 前端
cd web
npm run dev

# 一键启动两个服务
scripts/dev.bat

# MySQL（客户端不在 PATH）
"D:/ws-soft/MySql/mysql-8.0.46-winx64/bin/mysql.exe" -uroot -p123456 voice_clone
```

## 目录结构

- `.codegraph/` — 代码图谱工具的数据目录，本地生成，不入库
- `docs/` — 技术文档与方案
- `scripts/` — 启动脚本
- `server/` — Python 模型服务（FastAPI，无状态、不连数据库）
- `web/` — Next.js 前端（服务端路由负责落盘与落库），运行时音频在 `web/data/`

## 参考文档

- [实现方案](docs/implementation-plan.md) — 技术选型、架构、阶段划分、启动部署
- [接口契约](docs/api.md) — FastAPI 与 Next.js 两套接口、错误码、安全约定
- [数据库](docs/database.md) — 建表 DDL 与设计说明
- [Fish Audio 云 API 速查](docs/fish-audio.md) — 备选方案，未采用，留作参考

## 开发约定

- 遵循全局 CLAUDE.md：中文回答；改动前先出方案并等确认
- **分层原则**：Python 服务无状态，只做「音频 → 文本」和「文本 + 参考音频 → 音频」的纯计算；文件落盘与数据库读写都在 Next.js 侧
- **文件命名**：音频文件名一律由服务端生成 UUID，浏览器不参与命名；读取时用 `^[a-f0-9-]+\.wav$` 白名单校验，防目录穿越
- **表结构**：以 `docs/database.md` 的 DDL 为准，Drizzle 定义不得偏离
- **接口变更**：改了 `docs/api.md` 里的契约要同步更新文档
