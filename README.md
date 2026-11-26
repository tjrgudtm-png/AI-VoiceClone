# AI-VoiceClone — GPT-SoVITS로 내 목소리 클론 만들기 (Windows + RTX)

이 저장소는 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)로 **내 목소리 TTS 모델**을 만드는 과정을 정리한 가이드와 보조 도구입니다.

| 파일 | 용도 |
|---|---|
| `docs/recording_script.md` | 녹음할 때 읽을 한국어 대본 (약 5~7분 분량) |
| `scripts/check_audio.py` | 녹음 파일 점검 (총 길이, 샘플레이트, 클리핑, 너무 작은 소리) |
| `scripts/tts_client.py` | 학습한 모델을 API로 불러 문장을 음성 파일로 만들기 |

---

## 0. 전체 흐름

```
녹음(5~10분) → 점검 → WebUI: 잡음 제거·자르기·받아쓰기·교정 → 학습(SoVITS → GPT) → 음성 생성
```

예상 소요 시간: 설치 30분 + 녹음 30분 + 데이터 정리 30분 + 학습 20~40분 (RTX 3060급 기준)

---

## 1. 설치

1. GPT-SoVITS GitHub 페이지의 README에 있는 **Windows 통합 패키지(Integrated Package)** 링크(HuggingFace)에서 최신 `.7z` 파일을 받습니다.
   - **RTX 50 시리즈**(5060/5070/5080/5090)라면 파일명에 `nvidia50`이 들어간 패키지를 받으세요.
   - RTX 20/30/40 시리즈는 일반 패키지를 받으면 됩니다.
2. [7-Zip](https://www.7-zip.org/)으로 압축을 풉니다.
   - ⚠️ 경로에 **한글이나 공백이 없는 곳**에 푸세요. 예: `C:\AI\GPT-SoVITS`
3. 그래픽 드라이버를 최신으로 업데이트합니다(NVIDIA App 또는 GeForce Experience).
4. 폴더 안의 **`go-webui.bat`**을 더블클릭합니다.
5. 잠시 뒤 브라우저에 학습용 WebUI(`http://localhost:9874`)가 열리면 설치 성공입니다.
   - 검은 창(콘솔)은 끄지 마세요. WebUI가 이 창에서 돌아갑니다.

---

## 2. 녹음

1. `docs/recording_script.md`의 문장을 읽으며 녹음합니다.
   - Windows 기본 "녹음기" 앱, [Audacity](https://www.audacityteam.org/), 스마트폰 모두 괜찮습니다.
   - 조용한 방에서, 입과 마이크 거리를 일정하게(주먹 하나~두 개) 유지하세요.
   - 문장 사이에 **0.5~1초 정도 쉬면** 나중에 자동으로 자르기 좋습니다.
   - 한 파일로 길게 녹음해도 되고, 여러 파일로 나눠도 됩니다.
2. **WAV**로 저장합니다. (m4a/mp3라면 Audacity로 열어서 WAV로 내보내기)
3. 파일을 한 폴더에 모읍니다. 예: `C:\AI\my_voice_raw\`

### 녹음 점검 (선택이지만 추천)

GPT-SoVITS 폴더에 들어 있는 파이썬으로 바로 실행할 수 있습니다.

```bat
cd C:\AI\GPT-SoVITS
runtime\python.exe C:\경로\AI-VoiceClone\scripts\check_audio.py C:\AI\my_voice_raw
```

총 녹음 길이와 함께 소리가 너무 작거나 찢어지는(클리핑) 파일을 알려줍니다.

---

## 3. 데이터 정리 (WebUI의 "0-전처리 데이터셋" 탭)

> WebUI 언어가 중국어/영어로 나오면 상단 또는 `config`에서 언어를 바꿀 수 있습니다. 메뉴 이름은 버전마다 조금씩 다를 수 있어요.

| 단계 | 할 일 | 설정 |
|---|---|---|
| **0a. UVR5** (선택) | 잡음·반주 제거 | 깨끗한 녹음이면 건너뛰기. 쓴다면 `HP5` 계열 모델로 보컬만 추출 |
| **0b. 오디오 자르기** | 긴 녹음을 문장 단위로 자르기 | 입력 경로: `C:\AI\my_voice_raw` / 출력: `output\slicer_opt` (기본값 그대로 OK) |
| **0c. 음성 인식(ASR)** | 잘린 음성을 텍스트로 받아쓰기 | 입력: `output\slicer_opt`, **모델: Faster Whisper**, **언어: ko**, 크기: `large-v3` |
| **0d. 교정(라벨링)** | 받아쓴 텍스트 확인·수정 | "라벨링 WebUI 열기" → 틀린 글자 고치기, 너무 짧거나 이상한 조각은 삭제 |

💡 **0d가 품질에 가장 중요합니다.** 대본대로 읽었으니 대본과 비교하며 고치면 빠릅니다.

---

## 4. 학습 (WebUI의 "1-GPT-SoVITS-TTS" 탭)

### 1A. 데이터 포맷팅
1. **실험 이름**: 영어로 (예: `myvoice`)
2. **텍스트 라벨 파일**: `output\asr_opt\slicer_opt.list` (0c 결과)
3. **오디오 폴더**: `output\slicer_opt`
4. **"원클릭 실행(一键三连)"** 클릭 → 끝날 때까지 대기

### 1B. 미세조정 학습
순서대로 진행합니다. **SoVITS 먼저, GPT 나중.**

| 항목 | 권장값 (데이터 5~10분 기준) |
|---|---|
| SoVITS epoch | 8~10 |
| GPT epoch | 10~15 |
| batch size | 기본값. 메모리 부족(CUDA out of memory) 에러가 나면 절반으로 줄이기 |

- VRAM 8GB면 기본값으로 대부분 됩니다. 6GB 이하면 batch size를 2~4로 줄이세요.
- 학습된 모델은 `GPT_weights...` / `SoVITS_weights...` 로 시작하는 폴더에 저장됩니다.

---

## 5. 음성 생성 (1C. 추론)

1. **"추론 WebUI 열기"** 클릭 → 새 탭(`http://localhost:9872`)이 열립니다.
2. 모델 목록 **새로고침** 후 방금 학습한 GPT / SoVITS 모델을 고릅니다. (epoch 숫자가 큰 것 = 마지막)
3. **참고 음성(Reference audio)**: `output\slicer_opt`에서 **3~10초짜리, 또박또박한 클립** 하나를 고릅니다.
4. **참고 음성 텍스트**: 그 클립에서 말한 내용을 정확히 입력하고, 언어는 **한국어**.
5. **합성할 텍스트** 입력, 언어 **한국어** → **합성** 클릭.

### 결과가 마음에 안 들 때

| 증상 | 해결 |
|---|---|
| 발음이 뭉개지거나 틀림 | 0d 교정 다시 확인, 참고 음성 텍스트가 정확한지 확인 |
| 목소리가 덜 닮음 | 참고 음성을 다른 클립으로 바꿔보기, 녹음 분량 늘리기 |
| 소리가 깨지거나 기계음 | epoch를 줄인 모델(더 이른 저장본) 사용 → 과적합일 수 있음 |
| 톤이 단조로움 | 감정이 있는 참고 음성 사용, 녹음 대본의 감정 문장 비중 늘리기 |

---

## 6. (선택) 파이썬으로 자동 생성하기

WebUI 없이 문장 여러 개를 한 번에 음성 파일로 만들 수 있습니다.

**① API 서버 실행** (GPT-SoVITS 폴더에서)
```bat
runtime\python.exe api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS\configs\tts_infer.yaml
```

**② 다른 명령 창에서 클라이언트 실행**
```bat
runtime\python.exe C:\경로\AI-VoiceClone\scripts\tts_client.py ^
  --gpt  "GPT_weights_v2Pro\myvoice-e15.ckpt" ^
  --sovits "SoVITS_weights_v2Pro\myvoice_e10_s200.pth" ^
  --ref "C:\AI\GPT-SoVITS\output\slicer_opt\ref.wav" ^
  --ref-text "참고 음성에서 말한 문장" ^
  --text "안녕하세요, 이건 제 목소리로 만든 AI 음성입니다." ^
  --out hello.wav
```

여러 문장을 한꺼번에: 한 줄에 한 문장씩 적은 `lines.txt`를 만들고 `--text` 대신 `--text-file lines.txt --out-dir outputs`.

`--gpt` / `--sovits`는 실제 저장된 파일 이름으로 바꾸세요. 생략하면 서버에 이미 로드된 모델을 씁니다.

---

## 자주 나는 문제

- **`go-webui.bat`이 바로 꺼짐** → 경로에 한글/공백이 있는지 확인. 백신이 파일을 막았는지 확인.
- **CUDA out of memory** → batch size 줄이기, 다른 프로그램(게임, 브라우저 영상) 끄기.
- **RTX 50 시리즈에서 학습 에러** → `nvidia50` 패키지를 받았는지 확인.
- **WebUI가 안 열림** → 콘솔에 나온 주소(`http://localhost:9874`)를 브라우저에 직접 입력.

---

⚠️ 본인 목소리, 또는 당사자의 명시적 동의를 받은 목소리만 사용하세요. 타인 사칭·사기 등에 사용하면 법적 책임이 따릅니다.
