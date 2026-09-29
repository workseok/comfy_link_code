# macOS 설치·사용 가이드

이 문서 하나로 **macOS**에서 이 프로젝트를 설치하고 처음부터 끝까지 실행할
수 있습니다. Windows 얘기는 이 문서에 없습니다 — Windows를 쓰신다면
[`docs/SETUP_WINDOWS.md`](./SETUP_WINDOWS.md)를 봐주세요.

프로그래밍을 몰라도 따라 할 수 있도록 순서대로 적었습니다. 회색 상자 안의
명령어를 **터미널(Terminal)** 앱에 복사해서 붙여넣고 Enter를 누르는 것이
전부입니다.

---

## 0. 이 프로젝트가 하는 일

촬영 현장에서 카메라 영상에 AI로 배경을 합성하는 4단계 파이프라인입니다.

| 단계 | 내용 | 파일 |
|---|---|---|
| ① | 웹캠/HDMI 캡처카드 영상을 3~5초 단위로 저장 | `scripts/capture_segments.py` |
| ② | 각 조각의 첫 프레임에서 사람 위치 자동 인식 | `scripts/extract_pose_points.py` |
| ③ | ComfyUI(클라우드 또는 로컬)로 보내서 배경 합성 | `main.py` |
| ④ | 합성된 조각을 순서대로 화면에 재생 | `scripts/play_segments.py` |

## 0-1. 내 Mac이 Apple Silicon인지 Intel인지 확인하기

아래 설치 과정에서 몇 군데는 이 정보가 필요합니다.

1. 화면 왼쪽 위 **애플 메뉴( )** → **"이 Mac에 관하여"** 클릭
2. "칩" 항목에 `Apple M1`/`M2`/`M3`/`M4` 등이 적혀 있으면 **Apple Silicon
   (arm64)**, "프로세서" 항목에 `Intel`이 적혀 있으면 **Intel(x86_64)**
   입니다.

---

## 1. Git 설치

macOS에는 Xcode Command Line Tools를 설치하면 Git이 함께 설치됩니다.

1. **터미널(Terminal)** 앱을 엽니다 (Spotlight 검색 `Cmd + Space` → "터미널"
   입력 → Enter).
2. 아래 명령을 입력합니다:
   ```
   git --version
   ```
3. Git이 아직 없으면 "명령줄 개발자 도구가 설치되어 있지 않습니다" 같은
   팝업이 뜹니다 → **"설치"** 클릭 → 완료될 때까지 기다립니다 (몇 분 걸릴 수
   있음).
4. 설치가 끝나면 다시 `git --version`을 실행해서 버전이 출력되는지
   확인합니다.

## 2. Miniforge 설치 (Python + 가상환경 도구)

이 프로젝트는 Python으로 작성되어 있습니다. Python 자체와, 프로젝트별로
독립된 실행 환경(가상환경)을 만들어 주는 **Miniforge**를 함께 설치합니다.
(macOS 기본 Python이나 Homebrew Python 대신 Miniforge를 쓰는 이유: `conda`
가상환경 하나로 Python 버전과 패키지 설치 환경을 한 번에 깔끔하게 관리할 수
있고, 특히 Apple Silicon에서 OpenCV/MediaPipe 같은 패키지들의 호환성 문제가
적습니다.)

> Homebrew로 Miniforge를 설치하지 마세요(`brew install miniforge`). 공식
> 설치 파일과 호환성 문제가 있을 수 있어 권장하지 않습니다. 아래처럼 공식
> 설치 파일(.pkg)을 직접 받아 설치하세요.

1. https://github.com/conda-forge/miniforge/releases/latest 접속
2. 위 0-1에서 확인한 칩에 맞는 파일을 클릭해서 받습니다.
   - **Apple Silicon (M1/M2/M3/M4)**: `Miniforge3-MacOSX-arm64.pkg`
   - **Intel**: `Miniforge3-MacOSX-x86_64.pkg`
3. 받은 `.pkg` 파일을 더블클릭해서 설치 마법사를 엽니다.
   - "확인되지 않은 개발자" 경고가 뜨면: 파일을 **Control 키를 누른 채
     클릭(또는 우클릭) → "열기"**를 선택하면 설치를 계속할 수 있습니다.
   - 화면의 안내대로 "계속" → "동의" → "설치"를 눌러 끝까지 진행합니다
     (본인 계정에만 설치하는 옵션이면 관리자 암호 없이 설치됩니다).
4. 설치가 끝나면 **터미널을 완전히 껐다가 다시 엽니다** (설정이 반영되려면
   새 터미널 창이 필요합니다).
5. 설치 확인:
   ```
   conda --version
   python --version
   ```
   각각 버전이 출력되면 성공입니다. 터미널 프롬프트 맨 앞에 `(base)`라고
   붙어 있으면 정상입니다.

## 3. 저장소 내려받기 (Clone)

터미널에서, 코드를 저장하고 싶은 폴더로 이동한 뒤 내려받습니다. 예를 들어
바탕화면에 받고 싶다면:

```
cd ~/Desktop
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

터미널 프롬프트 맨 앞이 `(base)`에서 `(ai-bg-synthesis)`로 바뀌면 활성화된
것입니다. **앞으로 이 프로젝트 명령어를 실행할 때마다, 새 터미널 창을 열
때마다 `conda activate ai-bg-synthesis`를 먼저 실행**해야 합니다.

> `conda activate`가 "shell not initialized" 같은 오류를 낸다면,
> `conda init zsh`(macOS 기본 셸인 zsh 기준)를 한 번 실행한 뒤 터미널을 새로
> 열고 다시 시도하세요.

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
Apple Silicon(arm64)에서도 이 패키지들은 conda-forge/PyPI의 네이티브 arm64
빌드로 설치되므로 별도 조치가 필요 없습니다. 설치 중
`WARNING: Running pip as ...` 같은 노란 경고는 무시해도 됩니다.

## 6. 설치 확인

```
python -c "import cv2, mediapipe, numpy; print('설치 확인 OK:', cv2.__version__, mediapipe.__version__, numpy.__version__)"
```

`설치 확인 OK: ...` 줄이 출력되면 준비 완료입니다.

---

## 7. 사용법 ① — 웹캠/캡처카드로 3초 단위 영상 저장하기

FX9 같은 카메라를 HDMI 캡처카드로 연결한 경우, macOS 입장에서는 그
캡처카드가 그냥 웹캠 하나로 인식됩니다.

아무 옵션 없이 실행하면 연결된 영상 장치 목록을 보여주고 번호를 직접 고를 수
있습니다.

```
python scripts/capture_segments.py
```

```
[안내] 영상 장치 목록 (ffmpeg -f avfoundation -list_devices):
  [0] FaceTime HD Camera
  [1] USB Capture HDMI+
사용할 장치 번호를 입력하세요 [0, 1]: 1
```

macOS는 카메라 접근 권한 팝업이 처음 실행할 때 뜰 수 있습니다 —
**"허용"**을 눌러주세요. 나중에 다시 설정하려면 **시스템 설정 → 개인정보
보호 및 보안 → 카메라**에서 터미널(또는 사용 중인 터미널 앱)에 권한을 켜두면
됩니다.

장치 이름까지 보고 싶다면 **ffmpeg**가 설치되어 있어야 합니다 (없으면 열리는
번호만 보여줍니다, 그래도 선택과 녹화 자체는 됩니다). Homebrew가 있다면:

```
brew install ffmpeg
```

Homebrew가 없다면 https://brew.sh 안내에 따라 먼저 설치하거나, ffmpeg 설치는
건너뛰고 그냥 번호로 장치를 선택해도 됩니다.

자주 쓰는 옵션:

```
python scripts/capture_segments.py --list-devices              # 장치 목록만 보고 종료
python scripts/capture_segments.py --source 1                  # 장치 번호를 미리 알 때 바로 지정
python scripts/capture_segments.py --source 1 --num-segments 5 # 5개 조각만 저장하고 자동 종료
python scripts/capture_segments.py --source 1 --width 3840 --height 2160  # 해상도 요청 (FX9의 UHD 등)
```

`--width`/`--height`로 UHD(3840x2160) 같은 해상도를 요청했는데 캡처카드가 그
해상도를 지원하지 않으면, 실제로 적용된(다운컨버전된) 해상도가 무엇인지
`[주의] ... 다운컨버전 ...` 메시지로 알려줍니다. 10bit나 4:2:2 같은 색상
서브샘플링까지는 이 스크립트(OpenCV 기반)만으로 100% 확정할 수 없습니다 —
캡처카드가 실제로 지원하는 전체 모드 목록도 같이 보여주니(ffmpeg 필요) 그걸
참고해서 판단해 주세요.

저장된 조각은 `segments/segment_0001.mp4`, `segments/segment_0002.mp4` ...
순서로 쌓입니다. **멈추려면 `Ctrl+C`** — 그 순간까지 녹화 중이던 조각도 끊긴
지점까지 안전하게 저장됩니다.

## 8. 사용법 ② — 조각 첫 프레임에서 사람 위치 찾기

```
python scripts/extract_pose_points.py --video segments/segment_0001.mp4 --output output/segment_0001_points.json
```

처음 실행할 때는 사람 인식 AI 모델 파일(약 5MB)을 자동으로 내려받습니다.
`output/segment_0001_points.json`에 코/양쪽 어깨/양쪽 골반 좌표가 ComfyUI가
바로 쓸 수 있는 형식으로 저장되고, `output/pose_preview.jpg`에 검출된 점을
찍은 미리보기 이미지도 함께 저장됩니다.

## 9. 사용법 ③ — ComfyUI로 배경 합성 전송하기

준비물: ComfyUI에서 **"Save (API Format)"**로 내보낸 워크플로우 JSON 파일을
`workflows/` 폴더에 넣어두세요 (예: `workflows/background_composite.json`).
이 폴더는 회사 내부 워크플로우가 실수로 GitHub에 올라가지 않도록 git에서
제외되어 있으니, 직접 파일을 복사해 넣어야 합니다.

### 9-1. ComfyUI Cloud로 보내기 (기본값)

```
export COMFY_API_KEY="sk-..."
python main.py --workflow workflows/background_composite.json --frame segments/segment_0001.mp4 --prompt-point output/segment_0001_points.json --pose-node-id 11 --video-node-id 1 --segment-index 1
```

- API 키는 **환경 변수**(`export COMFY_API_KEY=...`)로만 넘기고, 명령어
  인자로 직접 쓰지 마세요 (셸 기록에 남습니다).
- `--pose-node-id`, `--video-node-id`는 여러분의 워크플로우 JSON 안에서
  `Sam2VideoSegmentationAddPoints` 노드와 원본 영상 입력 노드(`VHS_LoadVideo`
  계열)의 번호입니다. JSON 파일을 텍스트 편집기로 열어서
  `"class_type": "Sam2VideoSegmentationAddPoints"`를 검색하면, 그 노드를 감싸는
  큰따옴표 숫자가 번호입니다.
- 크레딧을 아끼려면 `--frame-load-cap 30`(30프레임=1초 분량으로 제한)과, 배경을
  반복하는 노드가 있다면 `--repeat-node-id`로 그 노드 번호도 같이 알려주세요
  (두 값이 어긋나면 합성이 깨집니다).
- 먼저 `--dry-run`을 붙여서 실행하면 실제로 전송하지 않고, 최종적으로 어떤
  값이 워크플로우에 들어갔는지 `output/dry_run_workflow.json`으로 저장만 하고
  끝냅니다. 값이 맞는지 확인한 뒤 `--dry-run`을 빼고 다시 실행하세요.

### 9-2. 로컬 ComfyUI로 보내기 (Apple Silicon Mac인 경우)

로컬 ComfyUI 연동(`comfyui_client/local_client.py`, `--backend local`)은 아직
구현되지 않았습니다 (다음 단계 작업). 지금은 위 9-1의 클라우드 방식만
사용하세요.

로컬 ComfyUI를 직접 설치해서 쓰실 계획이라면(이 저장소와는 별개의 프로그램),
**Apple Silicon Mac은 GPU 가속에 CUDA가 아니라 Apple의 MPS(Metal Performance
Shaders)를 씁니다.** 미리 알아두면 좋은 점:

- Intel Mac은 지원되는 GPU 가속이 없어 CPU로만 동작합니다(많이 느립니다).
  로컬 ComfyUI를 무겁게 쓸 계획이라면 Apple Silicon Mac이나 클라우드(9-1)
  쪽을 권장합니다.
- Apple Silicon Mac에서 ComfyUI를 설치하면, PyTorch가 MPS 백엔드를 자동으로
  잡는 경우가 많습니다. 설치 후 아래로 확인할 수 있습니다:
  ```
  python -c "import torch; print(torch.backends.mps.is_available())"
  ```
  `True`가 나오면 MPS 가속을 쓸 수 있는 상태입니다. (이 명령은 ComfyUI가
  설치한 PyTorch 환경에서 실행해야 합니다 — 이 프로젝트의
  `requirements.txt`에는 PyTorch가 포함되어 있지 않습니다.)
- ComfyUI 자체 설치는 이 저장소와 무관합니다. 공식 안내
  (https://github.com/comfyanonymous/ComfyUI) 의 Apple Silicon/macOS 섹션을
  따라 설치하세요.
- 이 프로젝트가 쓰는 워크플로우의 SAM2 모델 노드(`DownloadAndLoadSAM2Model`)가
  `device: cpu`로 고정되어 있다면, GPU가 없어도(또는 MPS를 안 써도) 그 부분은
  CPU로 동작합니다 (다만 느립니다). MPS로 돌리려면 그 노드의 `device` 값을
  ComfyUI 화면에서 `mps`로 바꾼 뒤 다시 API 형식으로 내보내야 합니다 — 다만
  일부 ComfyUI 커스텀 노드는 아직 MPS를 완전히 지원하지 않을 수 있으니, 오류가
  나면 CPU로 되돌리는 것도 방법입니다.

## 10. 사용법 ④ — 결과를 화면에 순서대로 재생하기

```
python scripts/play_segments.py
```

`output/processed/` 폴더를 감시하면서 `segment_0001.mp4`부터 순서대로 화면에
재생합니다. 아직 처리되지 않은 조각은 "처리 대기 중" 화면을 보여주며
기다렸다가, 파일이 생기면 자동으로 이어서 재생합니다. `q`를 누르면 종료,
다른 키를 누르면 지금 조각을 건너뜁니다.

---

## 11. 문제 해결 (macOS)

**`git`, `python`, `conda` 명령을 찾을 수 없다는 오류가 날 때**
→ 터미널을 완전히 종료했다가 다시 열어보세요 (설치 직후에는 새 터미널
세션이어야 PATH 설정이 반영됩니다). 그래도 안 되면 `conda init zsh`를 실행한
뒤 다시 열어보세요.

**`pip install` 도중 빨간 글씨의 `ERROR`가 날 때**
→ 회사 네트워크의 방화벽/프록시 문제일 수 있습니다. IT 담당자에게
"pypi.org 접속을 허용해달라"고 요청하거나, 개인 네트워크(핫스팟 등)에서 한 번
시도해 보세요.

**Miniforge `.pkg` 설치 시 "확인되지 않은 개발자" 경고가 뜰 때**
→ 위 2번 안내대로 파일을 Control 키를 누른 채 클릭(또는 우클릭) →
"열기"로 실행하세요. 그래도 막히면 **시스템 설정 → 개인정보 보호 및 보안**
맨 아래에 "확인 없이 열기" 버튼이 나타나는지 확인하세요.

**`capture_segments.py` 실행 시 "N번 장치를 열 수 없습니다" 라고 나올 때**
→ 다음을 순서대로 확인하세요.
1. 카메라/캡처카드가 실제로 USB로 연결되어 있는지
2. **시스템 설정 → 개인정보 보호 및 보안 → 카메라**에서 터미널 앱에 권한이
   켜져 있는지
3. 화상회의 프로그램(Zoom, Teams 등)이나 다른 캡처 소프트웨어가 이미 그
   장치를 쓰고 있지 않은지 — 열려 있다면 종료 후 다시 시도
4. `--list-devices`로 지금 인식되는 장치 번호를 다시 확인

**장치 목록에 이름이 안 보이고 번호만 나올 때**
→ 위 7번의 `brew install ffmpeg` 안내를 따라 ffmpeg를 설치해 보세요.

**"첫 프레임에서 사람을 찾지 못했습니다" 라고 나올 때**
→ 영상의 첫 프레임에 사람이 온전히 보이지 않는 경우입니다 (너무 어둡거나,
화면 밖으로 나가 있거나, 뒷모습이라 관절 인식이 어려운 경우). 사람이 잘
보이는 다른 영상으로 먼저 테스트해 보세요.

**모델 파일 다운로드가 실패할 때**
→ 회사 네트워크가 `storage.googleapis.com` 접속을 막고 있을 수 있습니다.
오류 메시지에 나온 주소를 다른 네트워크에서 내려받은 뒤, 오류 메시지에 나온
저장 경로(`models/pose_landmarker_lite.task`)에 파일을 직접 복사해 넣고
다시 실행하면 됩니다.

**`main.py` 실행 시 "ComfyUI 서버에 연결할 수 없습니다" 라고 나올 때**
→ `--server` 주소가 맞는지, 이 컴퓨터에서 외부 인터넷 접속이 되는지
확인하세요. 회사 네트워크가 `cloud.comfy.org` 접속을 막고 있을 수도
있습니다 — 그렇다면 IT 담당자에게 문의하세요.

**`main.py` 실행 시 "환경변수 COMFY_API_KEY가 설정되어 있지 않습니다" 라고
나올 때**
→ 같은 터미널 창에서 `export COMFY_API_KEY="sk-..."`를 먼저 실행한 뒤 바로
이어서 `python main.py ...`를 실행하세요. 터미널을 새로 열면 다시 설정해야
합니다. 매번 다시 치기 싫다면 `~/.zshrc` 파일 맨 아래에
`export COMFY_API_KEY="sk-..."` 줄을 추가해두면 새 터미널마다 자동으로
설정됩니다 (다만 이 방법은 키가 파일에 평문으로 남으니, 공용 컴퓨터라면
피하세요).

**`play_segments.py`를 실행했는데 화면 창이 안 뜨거나, 카메라/화면 권한
경고가 뜰 때**
→ 화면 녹화나 카메라 권한을 요구하는 팝업이 뜨면 허용해 주세요. 원격
화면 공유로 접속해서 실행 중이라면, 화면 세션이 제대로 연결되어 있는지도
확인하세요.
