# Windows 설치·사용 가이드

이 문서 하나로 **Windows**에서 이 프로젝트를 설치하고 처음부터 끝까지 실행할
수 있습니다. macOS 얘기는 이 문서에 없습니다 — macOS를 쓰신다면
[`docs/SETUP_MAC.md`](./SETUP_MAC.md)를 봐주세요.

프로그래밍을 몰라도 따라 할 수 있도록 순서대로 적었습니다. 회색 상자 안의
명령어를 **명령 프롬프트**(또는 아래에서 설치할 "Miniforge Prompt")에
복사해서 붙여넣고 Enter를 누르는 것이 전부입니다.

---

## 0. 이 프로젝트가 하는 일

촬영 현장에서 카메라 영상에 AI로 배경을 합성하는 4단계 파이프라인입니다.

| 단계 | 내용 | 파일 |
|---|---|---|
| ① | 웹캠/HDMI 캡처카드 영상을 3~5초 단위로 저장 | `scripts/capture_segments.py` |
| ② | 각 조각의 첫 프레임에서 사람 위치 자동 인식 | `scripts/extract_pose_points.py` |
| ③ | ComfyUI(클라우드 또는 로컬)로 보내서 배경 합성 | `main.py` |
| ④ | 합성된 조각을 순서대로 화면에 재생 | `scripts/play_segments.py` |

---

## 1. Git 설치

1. https://git-scm.com/downloads 에서 **Windows**용 설치 파일을 받습니다.
2. 설치 파일을 실행하고, 옵션은 전부 기본값으로 "Next"만 눌러 설치를
   끝냅니다.
3. 설치 확인 — 시작 메뉴에서 **"cmd"**를 검색해 명령 프롬프트를 열고:
   ```
   git --version
   ```
   버전이 출력되면 성공입니다.

## 2. Miniforge 설치 (Python + 가상환경 도구)

이 프로젝트는 Python으로 작성되어 있습니다. Python 자체와, 프로젝트별로
독립된 실행 환경(가상환경)을 만들어 주는 **Miniforge**를 함께 설치합니다.
(파이썬 공식 설치 파일 대신 Miniforge를 쓰는 이유: `conda` 가상환경 하나로
Python 버전과 패키지 설치 환경을 한 번에 깔끔하게 관리할 수 있고, 이 프로젝트가
쓰는 OpenCV/MediaPipe 같은 패키지들과의 호환성 문제가 적습니다.)

1. https://github.com/conda-forge/miniforge/releases/latest 접속
2. 파일 목록에서 **`Miniforge3-Windows-x86_64.exe`**를 클릭해서 받습니다.
   (대부분의 Windows PC는 x86_64입니다. ARM 기반 Windows PC라면
   `Miniforge3-Windows-arm64.exe`를 받으세요.)
3. 받은 설치 파일을 실행합니다.
   - "Install for" 화면에서 **"Just Me"** 선택 (권장)
   - **"Create start menu shortcuts"** 체크박스를 켜 둡니다 — 이게 켜져 있어야
     시작 메뉴에 **"Miniforge Prompt"**가 생깁니다.
   - 나머지는 기본값 그대로 "Install" → "Finish"
4. 설치가 끝나면, **시작 메뉴에서 "Miniforge Prompt"를 검색해서 실행**합니다.
   앞으로 이 프로젝트와 관련된 모든 명령어는 (평범한 명령 프롬프트가 아니라)
   이 **Miniforge Prompt**에서 실행합니다.
5. 설치 확인 (Miniforge Prompt에서):
   ```
   conda --version
   python --version
   ```
   각각 버전이 출력되면 성공입니다.

## 3. 저장소 내려받기 (Clone)

Miniforge Prompt에서, 코드를 저장하고 싶은 폴더로 이동한 뒤 내려받습니다.
예를 들어 바탕화면에 받고 싶다면:

```
cd Desktop
git clone https://github.com/workseok/part1_ai-test.git
cd part1_ai-test
git checkout claude/ai-background-synthesis-prototype-6hp3a9
```

> 마지막 줄은 지금 이 작업이 올라간 개발 브랜치로 이동하는 명령입니다. 나중에
> 이 브랜치 내용이 메인 브랜치로 합쳐지면 이 줄은 생략하고 `git clone`만 해도
> 됩니다.

## 4. 가상환경 만들기

이 프로젝트 전용 Python 환경을 하나 만듭니다. 이름은 `ai-bg-synthesis`로
정했습니다 (원하는 이름으로 바꿔도 됩니다 — 그러면 아래 활성화 명령의 이름도
똑같이 바꿔주세요).

```
conda create -n ai-bg-synthesis python=3.11 -y
conda activate ai-bg-synthesis
```

명령 프롬프트 맨 앞에 `(ai-bg-synthesis)`라고 표시되면 활성화된 것입니다.
**앞으로 이 프로젝트 명령어를 실행할 때마다, 새 Miniforge Prompt 창을 열 때마다
`conda activate ai-bg-synthesis`를 먼저 실행**해야 합니다.

## 5. 의존성 설치

가상환경이 활성화된 상태(`(ai-bg-synthesis)`가 보이는 상태)에서, 저장소
폴더 안(`part1_ai-test`)에서:

```
pip install -r requirements.txt
```

- `opencv-python`: 영상 파일/카메라를 열고 프레임을 다루고, 화면 창에 재생하는
  패키지
- `mediapipe`: 구글에서 만든 사람 자세(관절 위치) 인식 AI 패키지
- `numpy`: 좌표 계산에 쓰이는 수학 패키지

버전이 정확히 고정되어 있으니(`requirements.txt` 참고) 그대로 설치하면 됩니다.
설치 중 `WARNING: Running pip as ...` 같은 노란 경고는 무시해도 됩니다.

## 6. 설치 확인

```
python -c "import cv2, mediapipe, numpy; print('설치 확인 OK:', cv2.__version__, mediapipe.__version__, numpy.__version__)"
```

`설치 확인 OK: ...` 줄이 출력되면 준비 완료입니다.

---

## 7. 사용법 ① — 웹캠/캡처카드로 3초 단위 영상 저장하기

FX9 같은 카메라를 HDMI 캡처카드로 연결한 경우, Windows 입장에서는 그 캡처카드가
그냥 웹캠 하나로 인식됩니다.

아무 옵션 없이 실행하면 연결된 영상 장치 목록을 보여주고 번호를 직접 고를 수
있습니다.

```
python scripts\capture_segments.py
```

```
[안내] 영상 장치 목록 (ffmpeg -f dshow -list_devices):
  [0] Integrated Camera
  [1] USB Capture HDMI 4K+
사용할 장치 번호를 입력하세요 [0, 1]: 1
```

장치 이름까지 보고 싶다면 **ffmpeg**가 설치되어 있어야 합니다 (없으면 열리는
번호만 보여줍니다, 그래도 선택과 녹화 자체는 됩니다):

1. https://www.gyan.dev/ffmpeg/builds/ 에서 "release essentials" 버전을 받아
   압축을 풉니다.
2. 압축을 푼 폴더 안 `bin` 폴더를 시스템 PATH에 추가합니다 (시작 메뉴 →
   "환경 변수 편집" 검색 → "시스템 변수"의 `Path`에 그 `bin` 폴더 경로 추가).
3. 새 Miniforge Prompt를 열어서 `ffmpeg -version`이 출력되면 성공입니다.

자주 쓰는 옵션:

```
python scripts\capture_segments.py --list-devices              REM 장치 목록만 보고 종료
python scripts\capture_segments.py --source 1                  REM 장치 번호를 미리 알 때 바로 지정
python scripts\capture_segments.py --source 1 --num-segments 5 REM 5개 조각만 저장하고 자동 종료
python scripts\capture_segments.py --source 1 --width 3840 --height 2160  REM 해상도 요청 (FX9의 UHD 등)
```

`--width`/`--height`로 UHD(3840x2160) 같은 해상도를 요청했는데 캡처카드가 그
해상도를 지원하지 않으면, 실제로 적용된(다운컨버전된) 해상도가 무엇인지
`[주의] ... 다운컨버전 ...` 메시지로 알려줍니다. 10bit나 4:2:2 같은 색상
서브샘플링까지는 이 스크립트(OpenCV 기반)만으로 100% 확정할 수 없습니다 —
캡처카드가 실제로 지원하는 전체 모드 목록도 같이 보여주니(ffmpeg 필요) 그걸
참고해서 판단해 주세요.

저장된 조각은 `segments\segment_0001.mp4`, `segments\segment_0002.mp4` ...
순서로 쌓입니다. **멈추려면 `Ctrl+C`** — 그 순간까지 녹화 중이던 조각도 끊긴
지점까지 안전하게 저장됩니다.

## 8. 사용법 ② — 조각 첫 프레임에서 사람 위치 찾기

```
python scripts\extract_pose_points.py --video segments\segment_0001.mp4 --output output\segment_0001_points.json
```

처음 실행할 때는 사람 인식 AI 모델 파일(약 5MB)을 자동으로 내려받습니다.
`output\segment_0001_points.json`에 코/양쪽 어깨/양쪽 골반 좌표가 ComfyUI가
바로 쓸 수 있는 형식으로 저장되고, `output\pose_preview.jpg`에 검출된 점을
찍은 미리보기 이미지도 함께 저장됩니다.

## 9. 사용법 ③ — ComfyUI로 배경 합성 전송하기

준비물: ComfyUI에서 **"Save (API Format)"**로 내보낸 워크플로우 JSON 파일을
`workflows\` 폴더에 넣어두세요 (예: `workflows\background_composite.json`).
이 폴더는 회사 내부 워크플로우가 실수로 GitHub에 올라가지 않도록 git에서
제외되어 있으니, 직접 파일을 복사해 넣어야 합니다.

### 9-1. ComfyUI Cloud로 보내기 (기본값)

```
set COMFY_API_KEY=sk-...
python main.py --workflow workflows\background_composite.json --frame segments\segment_0001.mp4 --prompt-point output\segment_0001_points.json --pose-node-id 11 --video-node-id 1 --segment-index 1
```

- API 키는 **환경 변수**(`set COMFY_API_KEY=...`)로만 넘기고, 명령어 인자로
  직접 쓰지 마세요 (명령 기록에 남습니다).
- `--pose-node-id`, `--video-node-id`는 여러분의 워크플로우 JSON 안에서
  `Sam2VideoSegmentationAddPoints` 노드와 원본 영상 입력 노드(`VHS_LoadVideo`
  계열)의 번호입니다. JSON 파일을 텍스트 편집기로 열어서
  `"class_type": "Sam2VideoSegmentationAddPoints"`를 검색하면, 그 노드를 감싸는
  큰따옴표 숫자가 번호입니다.
- 크레딧을 아끼려면 `--frame-load-cap 30`(30프레임=1초 분량으로 제한)과, 배경을
  반복하는 노드가 있다면 `--repeat-node-id`로 그 노드 번호도 같이 알려주세요
  (두 값이 어긋나면 합성이 깨집니다).
- 먼저 `--dry-run`을 붙여서 실행하면 실제로 전송하지 않고, 최종적으로 어떤
  값이 워크플로우에 들어갔는지 `output\dry_run_workflow.json`으로 저장만 하고
  끝냅니다. 값이 맞는지 확인한 뒤 `--dry-run`을 빼고 다시 실행하세요.

### 9-2. 로컬 ComfyUI로 보내기 (NVIDIA GPU가 있는 경우)

로컬 ComfyUI 연동(`comfyui_client/local_client.py`, `--backend local`)은 아직
구현되지 않았습니다 (다음 단계 작업). 지금은 위 9-1의 클라우드 방식만
사용하세요.

로컬 ComfyUI를 직접 설치해서 쓰실 계획이라면(이 저장소와는 별개의 프로그램),
Windows에서는 보통 **NVIDIA GPU + CUDA**로 가속합니다. 미리 알아두면 좋은 점:

- ComfyUI를 설치하기 전에, `nvidia-smi` 명령으로 GPU와 드라이버가 잡히는지
  확인해 두세요 (명령 프롬프트에서 실행 — 드라이버가 설치되어 있어야 나옵니다).
- ComfyUI는 PyTorch의 CUDA 빌드를 사용합니다. ComfyUI 공식 설치 안내
  (https://github.com/comfyanonymous/ComfyUI) 의 Windows/NVIDIA 섹션을 따라
  설치하면 CUDA용 PyTorch가 자동으로 맞춰집니다 — 이 부분은 이 저장소가
  아니라 ComfyUI 자체 설치 과정이므로, 이 프로젝트의 `requirements.txt`와는
  무관합니다.
- 이 프로젝트가 쓰는 워크플로우의 SAM2 모델 노드(`DownloadAndLoadSAM2Model`)가
  `device: cpu`로 고정되어 있다면, GPU가 없어도 그 부분은 CPU로 동작합니다
  (다만 느립니다). GPU로 돌리려면 그 노드의 `device` 값을 ComfyUI 화면에서
  `cuda`로 바꾼 뒤 다시 API 형식으로 내보내야 합니다.

## 10. 사용법 ④ — 결과를 화면에 순서대로 재생하기

```
python scripts\play_segments.py
```

`output\processed\` 폴더를 감시하면서 `segment_0001.mp4`부터 순서대로 화면에
재생합니다. 아직 처리되지 않은 조각은 "처리 대기 중" 화면을 보여주며
기다렸다가, 파일이 생기면 자동으로 이어서 재생합니다. `q`를 누르면 종료,
다른 키를 누르면 지금 조각을 건너뜁니다.

---

## 11. 문제 해결 (Windows)

**`git`이나 `python`, `conda` 명령을 찾을 수 없다는 오류가 날 때**
→ 새로 연 창이 **일반 명령 프롬프트**인지 확인하세요. Python/conda 명령은
**"Miniforge Prompt"**에서만 바로 동작합니다 (일반 명령 프롬프트에서 쓰려면
`conda init cmd.exe`를 Miniforge Prompt에서 한 번 실행한 뒤 새 창을 열어야
합니다).

**`pip install` 도중 빨간 글씨의 `ERROR`가 날 때**
→ 회사 네트워크의 방화벽/프록시 문제일 수 있습니다. IT 담당자에게
"pypi.org 접속을 허용해달라"고 요청하거나, 개인 네트워크(핫스팟 등)에서 한 번
시도해 보세요.

**`capture_segments.py` 실행 시 "N번 장치를 열 수 없습니다" 라고 나올 때**
→ 다음을 순서대로 확인하세요.
1. 카메라/캡처카드가 실제로 USB로 연결되어 있는지
2. 화상회의 프로그램(Zoom, Teams 등)이나 다른 캡처 소프트웨어가 이미 그
   장치를 쓰고 있지 않은지 — 열려 있다면 종료 후 다시 시도
3. `--list-devices`로 지금 인식되는 장치 번호를 다시 확인

**장치 목록에 이름이 안 보이고 번호만 나올 때**
→ 위 7번의 ffmpeg 설치 안내를 따라 ffmpeg를 PATH에 추가해 보세요.

**"첫 프레임에서 사람을 찾지 못했습니다" 라고 나올 때**
→ 영상의 첫 프레임에 사람이 온전히 보이지 않는 경우입니다 (너무 어둡거나,
화면 밖으로 나가 있거나, 뒷모습이라 관절 인식이 어려운 경우). 사람이 잘
보이는 다른 영상으로 먼저 테스트해 보세요.

**모델 파일 다운로드가 실패할 때**
→ 회사 네트워크가 `storage.googleapis.com` 접속을 막고 있을 수 있습니다.
오류 메시지에 나온 주소를 다른 네트워크에서 내려받은 뒤, 오류 메시지에 나온
저장 경로(`models\pose_landmarker_lite.task`)에 파일을 직접 복사해 넣고
다시 실행하면 됩니다.

**`main.py` 실행 시 "ComfyUI 서버에 연결할 수 없습니다" 라고 나올 때**
→ `--server` 주소가 맞는지, 이 컴퓨터에서 외부 인터넷 접속이 되는지
확인하세요. 회사 네트워크가 `cloud.comfy.org` 접속을 막고 있을 수도
있습니다 — 그렇다면 IT 담당자에게 문의하세요.

**`main.py` 실행 시 "환경변수 COMFY_API_KEY가 설정되어 있지 않습니다" 라고
나올 때**
→ 같은 Miniforge Prompt 창에서 `set COMFY_API_KEY=sk-...`를 먼저 실행한 뒤
바로 이어서 `python main.py ...`를 실행하세요. 창을 새로 열면 다시
설정해야 합니다.

**`play_segments.py`를 실행했는데 화면 창이 안 뜰 때**
→ 원격 데스크톱으로 접속해서 실행 중이라면, 화면(그래픽) 세션이 제대로
연결되어 있는지 확인하세요. 컴퓨터에 직접 앉아서 실행하는 경우라면 보통
문제가 없습니다.
