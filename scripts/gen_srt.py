#!/usr/bin/env python3
"""
gen_srt.py — Generate subtitles.srt for AgentHub demo video.

Source: docs/deliverables/video/script.md (per-section narration paragraphs)
Timing: derived from probe of voice-001.mp3 ... voice-007.mp3 (TTS actual durations).
Per-sentence timing within each section is proportional to character count
(Chinese ~3-4 chars/sec at TTS rate).

Output: docs/deliverables/video/subtitles.srt
"""
import subprocess
from pathlib import Path

VOICE_DIR = Path(r"C:\Users\yhn\Desktop\字节比赛\AgentHub\docs\deliverables\video\voice")
SRT_PATH = Path(r"C:\Users\yhn\Desktop\字节比赛\AgentHub\docs\deliverables\video\subtitles.srt")
FFMPEG = "ffmpeg"

# 7 sections in the demo. Each tuple: (section_index, voice_id_number, [sentences])
# start_in_video = 4 (intro cover) + 0, 15, 45, 75, 105, 135, 165  (script pacing)
# We re-derived these from script.md 章节 0-6 boundaries
SECTIONS = [
    # (section_idx, voice_idx, start_offset_in_video_seconds, [sentences])
    (0, 1,  4,  [
        "AgentHub，多 Agent 协作平台。",
        "一个界面，把 Claude、Codex、OpenCode、本地自建 Agent 全部串起来。",
        "五个核心场景，三分钟看完。",
    ]),
    (1, 2,  20, [
        "场景一：和单个 Agent 一对一私聊。",
        "点加号新建会话，选 Claude 团队，进入对话。",
        "流式回复，边生成边出，体感像有人在打字。",
        "Python 代码块自动高亮，右下角可复制代码、Pin 整段消息。",
    ]),
    (2, 3,  50, [
        "场景二：群聊，一个任务多 Agent 接力。",
        "点左导航群组，进 S2 营销页升级群，四个 Agent 协同。",
        "@协调者拆任务，三个 worker 并行回复，紫色 @mention 高亮。",
        "真人只看汇报，不盯中间过程。",
    ]),
    (3, 4,  80, [
        "场景三：Agent 出的产物直接内联预览。",
        "URL 自动转成 WebPreviewCard iframe 沙箱卡片。",
        "代码 diff 自动转成 emerald rose 双色 DiffView。",
        "不用跳出聊天。",
    ]),
    (4, 5,  110, [
        "场景四：自定义 Agent，五个字段填完上线。",
        "点左导航 AI 队友，右上加号唤起创建队友弹窗。",
        "选 CLI 模板，填名字、描述、默认技能。",
        "新建完直接开聊，CLI 模式自动接 CLI runner。",
    ]),
    (5, 6,  140, [
        "场景五：Inbox 收件箱加任务看板。",
        "进入私聊 tab 栏的任务，Kanban 四列，看板视图就位。",
        "Inbox 审批是 M4 计划，本地通过 zustand 持久化加 seed 数据已就绪。",
        "审批通过、拒绝，diff 卡片，行内回执。",
    ]),
    (6, 7,  170, [
        "工程上：规范、SPEC、ADR 全留痕。",
        "docs/conventions 九个规范文档，docs/specs 五个规格文档，worklogs/decisions 四个 ADR。",
        "任何变更，先冻结接口，两人 Review，才写代码。Demo 完。",
    ]),
    # Outro cover: 196s-200s, the closing card
    (-1, None, 196, ["AgentHub · Demo 完"]),
]


def probe_duration(mp3: Path) -> float:
    """ffprobe duration of mp3 → seconds (float)."""
    proc = subprocess.run(
        [FFMPEG, "-i", str(mp3)],
        capture_output=True,
    )
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    for line in out.splitlines():
        if "Duration" in line:
            # "  Duration: 00:00:12.92, ..."
            ts = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = ts.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"Could not parse duration from {mp3}")


def format_srt_time(seconds: float) -> str:
    """Format seconds → HH:MM:SS,mmm for SRT."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:s:06.3f"  # placeholder, replace


def fmt(seconds: float) -> str:
    """Format seconds → HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def main() -> None:
    # Probe each TTS audio's actual duration (skip outro -1 entries that have no voice)
    durations = {}
    for sec_idx, voice_idx, _, _ in SECTIONS:
        if voice_idx is None:
            continue
        mp3 = VOICE_DIR / f"voice-{voice_idx:03d}.mp3"
        durations[voice_idx] = probe_duration(mp3)
        print(f"voice-{voice_idx:03d}: {durations[voice_idx]:.2f}s")

    # Build SRT
    entries = []
    sub_idx = 1
    for sec_idx, voice_idx, start_offset, sentences in SECTIONS:
        if voice_idx is None:
            # Outro cover entry: single sentence, fixed 4s duration
            for s in sentences:
                entries.append((sub_idx, float(start_offset), float(start_offset) + 4.0, s))
                sub_idx += 1
            continue
        duration = durations[voice_idx]
        total_chars = sum(len(s) for s in sentences)
        cum_chars = 0
        for s in sentences:
            sent_start = start_offset + (cum_chars / total_chars) * duration
            cum_chars += len(s)
            sent_end = start_offset + (cum_chars / total_chars) * duration
            entries.append((sub_idx, sent_start, sent_end, s))
            sub_idx += 1

    # Write SRT
    lines = []
    for idx, t0, t1, text in entries:
        lines.append(str(idx))
        lines.append(f"{fmt(t0)} --> {fmt(t1)}")
        lines.append(text)
        lines.append("")  # blank line

    SRT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {len(entries)} subtitle entries to {SRT_PATH}")
    print(f"Last subtitle ends at: {fmt(entries[-1][2])}")


if __name__ == "__main__":
    main()
