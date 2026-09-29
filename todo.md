# 待办需求

按实现方案的阶段组织。**P0~P7 是阶段编号**，不是优先级。

状态：`[ ]` 未开始 · `[-]` 进行中 · `[x]` 已完成

阶段说明与产出要求见 [docs/implementation-plan.md](docs/implementation-plan.md)。

## P0 环境与可行性验证

门禁：CPU 上速度不可接受则回到选型，不往下走。

- [ ] 安装 `uv`（`pip install uv`）
- [ ] 在 `server/` 建 Python 3.12 虚拟环境
- [ ] 安装 `faster-whisper` 1.2.1 与 `coqui-tts` 0.27.5（含 torch CPU）
- [ ] 编写 `server/smoke_test.py`：识别 + 合成 + 零样本克隆，打印实时率
- [ ] 执行验证，结果写入 `server/SMOKE_TEST.md`
- [ ] 拿着实时率结果评审，确认是否继续

## P1 契约与数据层冻结

- [x] 写 `docs/implementation-plan.md`
- [x] 写 `docs/api.md`
- [x] 写 `docs/database.md`
- [x] 更新 `CLAUDE.md`（技术栈、命令、目录、约定）
- [ ] 建 `voice_clone` 库与 `voices` / `generations` 两张表
- [ ] 写 `web/db/schema.ts`（Drizzle 表定义）

## P2 Python 模型服务

- [ ] `server/pyproject.toml` 与 `app/config.py`（环境变量、模型配置）
- [ ] `app/asr.py` — faster-whisper 封装
- [ ] `app/tts.py` — XTTS-v2 封装（零样本克隆）
- [ ] `app/schemas.py` — Pydantic 请求/响应模型
- [ ] `app/main.py` — `/health` `/asr` `/tts` 三个端点
- [ ] curl 自测三个端点通过

## P3 Next.js 骨架

- [ ] `create-next-app` 脚手架（TS + App Router + Tailwind）
- [ ] `shadcn init` + 安装所需组件
- [ ] 路由布局与导航（首页 / 克隆 / 转文字 / 音色库）
- [ ] 音频上传与播放共用组件
- [ ] `web/db/index.ts` 连接池，验证 DB 连通

## P4 语音转文字竖切

- [ ] `app/api/asr/route.ts` — 透传到 FastAPI
- [ ] `app/transcribe/page.tsx` — 上传音频、展示文本与分段
- [ ] 浏览器实测通过

## P5 声音克隆竖切

- [ ] `app/api/voices/route.ts` — 列表与新建
- [ ] `app/api/voices/[id]/route.ts` — 删除
- [ ] `app/api/tts/route.ts` — 合成、落盘、落库
- [ ] `app/api/audio/[name]/route.ts` 与 `app/api/refs/[name]/route.ts` — 音频读取
- [ ] `app/clone/page.tsx` — 上传参考音频、输入文本、试听
- [ ] `app/voices/page.tsx` — 音色库
- [ ] 浏览器实测通过

## P6 历史与收尾

- [ ] `app/api/generations/route.ts` — 历史查询
- [ ] 历史列表（含「音色已删除」态）
- [ ] 统一错误处理与 loading 态

## P7 端到端验收

- [ ] 完整走一遍：上传参考音频 → 克隆 → 试听 → 语音转文字 → 查历史
- [ ] `scripts/dev.bat` 一键启动脚本（含端口占用检查）
- [ ] 回填 `CLAUDE.md`，确认无残留占位

## 其他

- [ ] 初始化 git 仓库并添加 `.gitignore`（当前未纳管，忽略清单见实现方案）

## 已完成

- [x] 初始化项目目录
- [x] 确定技术栈（Next.js + 本地 Python 模型服务 + MySQL）
- [x] 本机环境探测（无独显、15.7GB 内存、MySQL 8.0.46、Python 3.13）
- [x] Fish Audio 云 API 调研并归档 `docs/fish-audio.md`（备选，未采用）
- [x] 方案落地到 `docs/`
