"""녹음 파일 점검 도구.

사용법:
    python check_audio.py <폴더 또는 wav 파일> [...]

각 WAV 파일의 길이, 샘플레이트, 채널, 최대 음량, 평균 음량을 보여주고
클리핑(소리 찢어짐)이나 너무 작은 소리를 경고합니다. 마지막에 총 녹음 길이를 알려줍니다.

외부 라이브러리 없이 동작합니다(16/24/32bit PCM WAV). GPT-SoVITS 통합 패키지의
runtime\\python.exe 로 실행해도 됩니다.
"""

from __future__ import annotations

import argparse
import math
import sys
import wave
from pathlib import Path

CLIP_RATIO = 0.999      # 최대값 대비 이 비율 이상이면 클리핑으로 간주
CLIP_COUNT_WARN = 50    # 클리핑 샘플이 이만큼 넘으면 경고
QUIET_PEAK_DB = -20.0   # 최대 음량이 이보다 작으면 "너무 작음"
LOUD_RMS_DB = -6.0      # 평균 음량이 이보다 크면 "너무 큼"


def read_samples(path: Path):
    """WAV를 읽어 (샘플 리스트[-1..1], 샘플레이트, 채널수, 길이초) 반환."""
    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if width not in (2, 3, 4):
        raise ValueError(f"지원하지 않는 비트 깊이: {width * 8}bit (16/24/32bit PCM만 지원)")

    full_scale = float(1 << (width * 8 - 1))
    # 큰 파일도 빠르게: 채널 상관없이 전체 샘플을 훑되, 통계는 일정 간격으로 샘플링
    total = len(raw) // width
    step = max(1, total // 2_000_000)
    samples = []
    for i in range(0, total, step):
        b = raw[i * width:(i + 1) * width]
        samples.append(int.from_bytes(b, "little", signed=True) / full_scale)
    return samples, rate, n_channels, n_frames / rate if rate else 0.0


def db(x: float) -> float:
    return 20 * math.log10(x) if x > 0 else -120.0


def analyze(path: Path):
    samples, rate, ch, dur = read_samples(path)
    if not samples:
        return dur, ["빈 파일"], rate, ch, -120.0, -120.0
    peak = max(abs(s) for s in samples)
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    clipped = sum(1 for s in samples if abs(s) >= CLIP_RATIO)

    warns = []
    if clipped >= CLIP_COUNT_WARN:
        warns.append(f"클리핑 의심({clipped}개 샘플) → 마이크와 거리를 두거나 입력 음량을 줄여 다시 녹음")
    if db(peak) < QUIET_PEAK_DB:
        warns.append("소리가 너무 작음 → 마이크 가까이, 또는 Audacity '정규화'로 키우기")
    if db(rms) > LOUD_RMS_DB:
        warns.append("평균 음량이 너무 큼 → 입력 음량 줄이기")
    if rate < 32000:
        warns.append(f"샘플레이트 {rate}Hz가 낮음 → 가능하면 44100Hz 이상으로 녹음")
    if dur < 1.0:
        warns.append("1초 미만으로 너무 짧음")
    return dur, warns, rate, ch, db(peak), db(rms)


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    others: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.suffix.lower() == ".wav":
                    files.append(f)
                elif f.suffix.lower() in {".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma"}:
                    others.append(f)
        elif p.is_file():
            files.append(p)
        else:
            print(f"[경로 없음] {p}")
    if others:
        print(f"참고: WAV가 아닌 오디오 {len(others)}개는 건너뜁니다 (예: {others[0].name}).")
        print("      GPT-SoVITS는 다른 형식도 읽지만, 이 점검 도구는 WAV만 봅니다.\n")
    return files


def fmt_time(sec: float) -> str:
    m, s = divmod(int(round(sec)), 60)
    return f"{m}분 {s:02d}초"


def main() -> int:
    ap = argparse.ArgumentParser(description="GPT-SoVITS 학습용 녹음 파일 점검")
    ap.add_argument("paths", nargs="+", help="WAV 파일 또는 폴더")
    args = ap.parse_args()

    files = collect(args.paths)
    if not files:
        print("WAV 파일을 찾지 못했습니다.")
        return 1

    total = 0.0
    n_warn = 0
    for f in files:
        try:
            dur, warns, rate, ch, peak_db, rms_db = analyze(f)
        except (wave.Error, ValueError, EOFError) as e:
            print(f"[읽기 실패] {f.name}: {e}")
            n_warn += 1
            continue
        total += dur
        mark = "⚠" if warns else "✓"
        print(f"{mark} {f.name}  {dur:6.1f}s  {rate}Hz  {ch}ch  최대 {peak_db:5.1f}dB  평균 {rms_db:5.1f}dB")
        for w in warns:
            print(f"    - {w}")
        n_warn += bool(warns)

    print("\n" + "=" * 60)
    print(f"파일 {len(files)}개, 총 길이 {fmt_time(total)}, 경고 있는 파일 {n_warn}개")
    if total < 60:
        print("→ 1분 미만입니다. 학습에는 최소 1분, 권장 5~10분이 필요해요.")
    elif total < 300:
        print("→ 학습은 가능하지만, 5분 이상이면 더 비슷해집니다.")
    else:
        print("→ 분량 충분합니다! 다음 단계(WebUI 전처리)로 넘어가세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
