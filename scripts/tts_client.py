"""GPT-SoVITS api_v2.py 서버를 호출해서 텍스트를 내 목소리 음성으로 만드는 클라이언트.

먼저 GPT-SoVITS 폴더에서 서버를 띄우세요:
    runtime\\python.exe api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS\\configs\\tts_infer.yaml

예시 (한 문장):
    python tts_client.py --ref ref.wav --ref-text "참고 음성 내용" \\
        --text "안녕하세요" --out hello.wav

예시 (여러 문장, 한 줄에 한 문장):
    python tts_client.py --ref ref.wav --ref-text "참고 음성 내용" \\
        --text-file lines.txt --out-dir outputs

학습한 모델로 바꾸려면 --gpt / --sovits 에 가중치 파일 경로를 넣으세요
(경로는 서버 기준, GPT-SoVITS 폴더에서의 상대경로 또는 절대경로).

외부 라이브러리 없이 동작합니다.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def call(server: str, path: str, *, params: dict | None = None, body: dict | None = None,
         timeout: float = 600) -> bytes:
    url = server.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit(f"[서버 에러 {e.code}] {path}: {detail}") from None
    except urllib.error.URLError as e:
        raise SystemExit(
            f"[연결 실패] {server} 에 접속할 수 없습니다: {e.reason}\n"
            "→ api_v2.py 서버가 켜져 있는지, 주소/포트가 맞는지 확인하세요."
        ) from None


def main() -> int:
    ap = argparse.ArgumentParser(description="GPT-SoVITS API로 음성 생성")
    ap.add_argument("--server", default="http://127.0.0.1:9880", help="api_v2.py 서버 주소")
    ap.add_argument("--gpt", help="GPT 가중치(.ckpt) 경로 — 지정하면 서버 모델을 교체")
    ap.add_argument("--sovits", help="SoVITS 가중치(.pth) 경로 — 지정하면 서버 모델을 교체")
    ap.add_argument("--ref", required=True, help="참고 음성 wav 경로 (3~10초)")
    ap.add_argument("--ref-text", required=True, help="참고 음성에서 실제로 말한 문장")
    ap.add_argument("--lang", default="ko", help="합성할 텍스트 언어 (ko, en, ja, zh, yue, auto)")
    ap.add_argument("--ref-lang", default="ko", help="참고 음성 언어")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="합성할 문장")
    g.add_argument("--text-file", help="한 줄에 한 문장씩 적힌 UTF-8 텍스트 파일")
    ap.add_argument("--out", default="output.wav", help="--text 사용 시 저장할 파일")
    ap.add_argument("--out-dir", default="outputs", help="--text-file 사용 시 저장할 폴더")
    ap.add_argument("--speed", type=float, default=1.0, help="말하기 속도 (1.0 = 보통)")
    ap.add_argument("--top-k", type=int, default=15)
    ap.add_argument("--top-p", type=float, default=1.0)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--split", default="cut5", help="긴 문장 분할 방식 (cut0~cut5, cut5=문장부호 기준)")
    args = ap.parse_args()

    ref = str(Path(args.ref).resolve())

    if args.gpt:
        print(f"GPT 모델 로드: {args.gpt}")
        call(args.server, "/set_gpt_weights", params={"weights_path": args.gpt})
    if args.sovits:
        print(f"SoVITS 모델 로드: {args.sovits}")
        call(args.server, "/set_sovits_weights", params={"weights_path": args.sovits})

    if args.text is not None:
        jobs = [(args.text, Path(args.out))]
    else:
        lines = [l.strip() for l in Path(args.text_file).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        jobs = [(l, out_dir / f"{i:03d}.wav") for i, l in enumerate(lines, 1)]

    for text, out in jobs:
        body = {
            "text": text,
            "text_lang": args.lang,
            "ref_audio_path": ref,
            "prompt_text": args.ref_text,
            "prompt_lang": args.ref_lang,
            "text_split_method": args.split,
            "top_k": args.top_k,
            "top_p": args.top_p,
            "temperature": args.temperature,
            "speed_factor": args.speed,
            "media_type": "wav",
            "streaming_mode": False,
        }
        audio = call(args.server, "/tts", body=body)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio)
        print(f"✓ {out}  ← {text[:40]}{'…' if len(text) > 40 else ''}")

    print(f"\n완료: {len(jobs)}개 파일 생성")
    return 0


if __name__ == "__main__":
    sys.exit(main())
