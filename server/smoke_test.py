"""P0 可行性验证。

在 CPU 上实测两条路径的耗时，回答「这套选型在这台机器上能不能用」：

  1. XTTS-v2 合成（内置发音人）
  2. faster-whisper 识别
  3. XTTS-v2 零样本克隆（用参考音频）

打印每条路径的实时率 RTF = 推理耗时 / 音频时长。RTF < 1 表示比实时快，
> 1 表示生成 N 秒音频要花 N 倍的时间，页面上的等待感直接由它决定。

用法：
    uv run python smoke_test.py            # 用自生成的音频当参考
    uv run python smoke_test.py ref.wav    # 用外部参考音频做克隆
"""

import os
import sys
import time
from pathlib import Path

# XTTS-v2 权重受 CPML 许可约束，非商业用途。这里事先声明已阅读，
# 否则 coqui-tts 会在下载权重前抛错中断。
os.environ.setdefault("COQUI_TOS_AGREED", "1")

# 模型权重收敛到项目内，便于清理（须在导入 torch/TTS 之前设置）
SERVER_DIR = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(SERVER_DIR / ".cache" / "hf"))
os.environ.setdefault("TTS_HOME", str(SERVER_DIR / ".cache" / "tts"))

OUT_DIR = SERVER_DIR / "out"
REF_FALLBACK = OUT_DIR / "step1_tts_en.wav"

EN_TEXT = "Hello. This is a smoke test for the text to speech pipeline."
ZH_CLONE_TEXT = "你好，这是用一段参考音频克隆出来的声音，用来验证整条链路是否可用。"


def audio_duration(path: Path) -> float:
    import soundfile as sf

    info = sf.info(str(path))
    return info.frames / info.samplerate


def report(name: str, elapsed: float, duration: float, extra: str = "") -> str:
    rate = f"{elapsed / duration:.2f}x" if duration else "n/a"
    line = f"  {name}: 音频 {duration:.2f}s，耗时 {elapsed:.2f}s，实时率 {rate}"
    if extra:
        line += f"\n    {extra}"
    print(line, flush=True)
    return line


def step1_tts(out_dir: Path) -> tuple[float, float]:
    from TTS.api import TTS

    print("[1/3] 加载 XTTS-v2 并合成英文 …", flush=True)
    t0 = time.perf_counter()
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
    load = time.perf_counter() - t0
    print(f"      模型加载 {load:.1f}s，发音人 {len(tts.speakers or [])} 个", flush=True)

    target = out_dir / "step1_tts_en.wav"
    t0 = time.perf_counter()
    tts.tts_to_file(
        text=EN_TEXT,
        speaker=tts.speakers[0],
        language="en",
        file_path=str(target),
    )
    return time.perf_counter() - t0, audio_duration(target)


def step2_asr(audio: Path) -> tuple[float, float, str]:
    from faster_whisper import WhisperModel

    print("[2/3] 加载 faster-whisper 并识别上一步的音频 …", flush=True)
    t0 = time.perf_counter()
    model = WhisperModel("small", device="cpu", compute_type="int8")
    print(f"      模型加载 {time.perf_counter() - t0:.1f}s", flush=True)

    t0 = time.perf_counter()
    segments, info = model.transcribe(str(audio), beam_size=5)
    text = "".join(seg.text for seg in segments).strip()  # 生成器，必须消费完才计入耗时
    return time.perf_counter() - t0, info.duration, text


def step3_clone(ref: Path, out_dir: Path) -> tuple[float, float]:
    from TTS.api import TTS  # 复用步骤 1 已加载的权重，走本地缓存

    print("[3/3] 用参考音频做零样本克隆 …", flush=True)
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")

    target = out_dir / "step3_clone_zh.wav"
    t0 = time.perf_counter()
    tts.tts_to_file(
        text=ZH_CLONE_TEXT,
        speaker_wav=str(ref),
        language="zh",
        file_path=str(target),
    )
    return time.perf_counter() - t0, audio_duration(target)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ref = Path(sys.argv[1]) if len(sys.argv) > 1 else REF_FALLBACK

    print(f"输出目录 {OUT_DIR}")
    print(f"参考音频 {ref}（{'外部传入' if len(sys.argv) > 1 else '默认用步骤 1 自生成'}）")
    print(f"HF_HOME={os.environ['HF_HOME']}")
    print(f"TTS_HOME={os.environ['TTS_HOME']}\n")

    lines: list[str] = []
    failures: list[str] = []

    try:
        elapsed, duration = step1_tts(OUT_DIR)
        lines.append(report("合成（英文，内置发音人）", elapsed, duration))
    except Exception as exc:  # noqa: BLE001 — 验证脚本，任何异常都要记下来继续下一步
        failures.append(f"步骤 1 失败: {type(exc).__name__}: {exc}")
        print(f"      !! {failures[-1]}", flush=True)
        return finish(lines, failures)

    try:
        elapsed, duration, text = step2_asr(OUT_DIR / "step1_tts_en.wav")
        lines.append(report("识别", elapsed, duration, extra=f"识别结果: {text}"))
    except Exception as exc:  # noqa: BLE001
        failures.append(f"步骤 2 失败: {type(exc).__name__}: {exc}")
        print(f"      !! {failures[-1]}", flush=True)

    if not ref.exists():
        failures.append(f"参考音频不存在: {ref}")
    else:
        try:
            elapsed, duration = step3_clone(ref, OUT_DIR)
            lines.append(report("零样本克隆（中文）", elapsed, duration))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"步骤 3 失败: {type(exc).__name__}: {exc}")
            print(f"      !! {failures[-1]}", flush=True)

    return finish(lines, failures)


def finish(lines: list[str], failures: list[str]) -> int:
    print("\n===== 汇总 =====")
    for line in lines:
        print(line)
    if failures:
        print("\n失败项:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("\n全部通过。把上面结果填进 SMOKE_TEST.md。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
