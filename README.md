# AI 배경 합성 프로토타입

촬영 현장에서 카메라 영상에 AI로 배경을 합성하는 시스템입니다. 4단계 전체가 이
저장소에 있습니다.

| 단계 | 내용 | 스크립트 |
|---|---|---|
| 1 | 카메라 영상을 3~5초 단위로 저장 | `scripts/capture_segments.py` ✅ |
| 2 | 영상 첫 프레임에서 사람 위치 자동 인식 | `scripts/extract_pose_points.py` ✅ |
| 3 | ComfyUI API로 배경 합성 자동 전송 | `comfyui_client/cloud_client.py` ✅ |
| 4 | 처리된 결과 영상을 순서대로 화면에 재생 | `scripts/play_segments.py` ✅ |

**전체 흐름**: 카메라 → ①3초 조각 저장 → ②조각 첫 프레임에서 사람 위치 검출 →
③ComfyUI에 전송해서 배경 합성 → ④합성된 조각을 순서대로 화면에 재생.

```
capture_segments.py            extract_pose_points.py          cloud_client.py                play_segments.py
(웹캠 → 3초 조각)      →      (조각 첫 프레임 → 사람 위치 JSON)  →  (JSON+워크플로우 → ComfyUI → 결과 영상) →  (결과 조각을 화면에 순서대로 재생)
segments/segment_0001.mp4      output/segment_0001_points.json     output/processed/segment_0001.mp4
```

> **3번 단계에 대한 중요한 전제**: `cloud_client.py`는 배경 합성을 실제로
> 수행하는 **ComfyUI 워크플로우 JSON 파일**이 있어야 동작합니다. 이 저장소를 만든
> 시점에는 아직 그 워크플로우가 없어서, 나중에 전달받는 즉시 끼워 쓸 수 있도록
> **범용적인 "전송기"** 형태로 만들어뒀습니다. 워크플로우가 오면 `workflows/`
> 폴더에 넣고 노드 ID 몇 개만 지정하면 됩니다. 자세한 내용은 아래 "11. ComfyUI로
> 배경 합성 전송하기" 항목을 참고하세요.
>
> 이 스크립트 자체(요청 전송 → 처리 대기 → 결과 다운로드 로직)는 실제 ComfyUI
> 서버 없이도 **가짜(mock) ComfyUI 서버**로 왕복 전체를 검증했습니다
> (`scripts/dev/mock_comfyui_server.py`, 아래에서 설명).

---

## 0. 미리 알아둘 것

- 프로그래밍을 몰라도 아래 순서를 그대로 따라 하면 됩니다. 터미널(명령 프롬프트)에
  명령어를 복사해서 붙여넣고 Enter를 누르는 것이 전부입니다.
- 아래 안내는 **Windows** 기준이며, 중간중간 macOS 차이점을 괄호로 표시했습니다.
- 이 작업은 인터넷에서 파일을 하나 받습니다(사람 인식 AI 모델, 약 5MB). 회사 네트워크가
  외부 접속을 막고 있다면 이 부분에서 안내가 나옵니다 (아래 "문제 해결" 항목 참고).

---

## 1. Python 설치

1. https://www.python.org/downloads/ 접속
2. "Download Python 3.x.x" 버튼 클릭해서 설치 파일 받기
3. 설치 파일 실행 시, **첫 화면 아래쪽의 "Add python.exe to PATH" (또는 "Add Python to PATH")
   체크박스를 반드시 체크**한 뒤 "Install Now" 클릭
   - (macOS는 https://www.python.org/downloads/macos/ 에서 받거나, 터미널에서
     `brew install python` 사용)
4. 설치가 끝나면 확인:
   - Windows: 시작 메뉴에서 "cmd" 검색 → 명령 프롬프트 실행
   - macOS: "터미널(Terminal)" 앱 실행
   - 아래 명령어 입력 후 Enter:
     ```
     python --version
     ```
     (macOS에서 안 되면 `python3 --version`으로 시도)
   - `Python 3.11.x` 같은 버전이 출력되면 성공입니다.

## 2. Git 설치 (GitHub에서 코드 받기 위함)

1. https://git-scm.com/downloads 에서 운영체제에 맞는 설치 파일 다운로드 후 설치
   (설치 중 옵션은 전부 기본값으로 "Next"만 눌러도 됩니다)
2. 설치 확인:
   ```
   git --version
   ```
   버전이 출력되면 성공입니다.

## 3. 이 저장소 내려받기 (Clone)

터미널(명령 프롬프트)에서, 코드를 저장하고 싶은 폴더로 이동한 뒤 아래 명령어를 실행합니다.
예를 들어 바탕화면에 받고 싶다면:

```
cd Desktop
git clone https://github.com/workseok/part1_ai-test.git
cd part1_ai-test
git checkout claude/ai-background-synthesis-prototype-6hp3a9
```

> 마지막 줄은 지금 이 작업이 올라간 개발 브랜치로 이동하는 명령입니다. 나중에 이 브랜치의
> 내용이 메인 브랜치로 합쳐지면(Pull Request 병합) 이 줄은 생략하고 그냥
> `git clone` 만 해도 됩니다.

## 4. 가상환경 만들기 (선택이지만 권장)

가상환경은 이 프로젝트에서 쓰는 파이썬 패키지들을 컴퓨터의 다른 프로그램과 섞이지
않게 따로 모아두는 폴더입니다. 안 만들어도 동작은 하지만, 문제가 생겼을 때 원인
파악이 쉬워지므로 권장합니다.

**Windows:**
```
python -m venv venv
venv\Scripts\activate
```

**macOS:**
```
python3 -m venv venv
source venv/bin/activate
```

명령 프롬프트 맨 앞에 `(venv)` 라고 표시되면 활성화된 것입니다. 앞으로 이 터미널
창에서 작업하는 동안은 계속 `(venv)` 상태를 유지하면 됩니다. (터미널 창을 새로 열면
`venv\Scripts\activate` 를 다시 실행해야 합니다.)

## 5. 필요한 패키지 설치

```
pip install -r requirements.txt
```

- `opencv-python`: 영상 파일/카메라를 열고 프레임을 다루고, 화면 창에 재생하는 패키지
- `mediapipe`: 구글에서 만든 사람 자세(관절 위치) 인식 AI 패키지
- `numpy`: 좌표 계산에 쓰이는 수학 패키지

(`cloud_client.py`는 파이썬에 기본 내장된 기능만 사용해서 별도 패키지가
필요 없습니다.)

버전을 정확히 고정해 두었으니 (`requirements.txt` 참고) 그대로 설치하면 이 문서에서
검증한 것과 동일하게 동작합니다.

설치 중 `WARNING: Running pip as ...` 같은 노란색 경고는 무시해도 됩니다. 빨간색
`ERROR`가 나오면 아래 "문제 해결" 항목을 참고하세요.

## 6. 웹캠/캡처카드로 3초 단위 영상 저장하기 (`capture_segments.py`)

FX9 같은 카메라를 HDMI 캡처카드로 연결한 경우, 컴퓨터 입장에서는 그 캡처카드가
그냥 웹캠 하나로 인식됩니다. 그래서 이 스크립트는 웹캠과 캡처카드를 구분하지
않고 똑같은 방식(영상 장치 하나)으로 다룹니다.

### 6-1. 장치 목록 확인하고 고르기

아무 옵션 없이 실행하면, 연결된 영상 장치 목록을 보여주고 번호를 직접
고를 수 있습니다.

```
python scripts/capture_segments.py
```

```
[안내] 영상 장치 목록 (ffmpeg -f dshow -list_devices):
  [0] Integrated Camera
  [1] USB Capture HDMI 4K+
사용할 장치 번호를 입력하세요 [0, 1]: 1
```

목록만 확인하고 싶다면(아직 녹화는 안 하고):
```
python scripts/capture_segments.py --list-devices
```

장치 번호를 이미 알고 있다면 매번 고르지 않고 바로 지정할 수도 있습니다:
```
python scripts/capture_segments.py --source 1
```

> **장치 목록에 이름이 안 보이고 "이름 확인 불가"만 나올 때**: Windows/macOS는
> `ffmpeg`가 설치되어 있어야 장치 이름까지 보여줄 수 있습니다 (없으면 열리는
> 번호만 보여줍니다). Linux는 `v4l2-ctl`(보통 `v4l-utils` 패키지)이 있으면
> 이름까지 보여줍니다. 이름이 없어도 번호 선택과 녹화 자체는 그대로 됩니다.

### 6-2. 캡처카드가 실제로 받는 해상도/FPS 확인하기

장치를 고르고 나면(카메라/캡처카드일 때) 자동으로 두 가지를 확인해서 보여줍니다.

**① 장치가 지원한다고 "보고하는" 전체 모드 목록** (ffmpeg 또는 v4l2-ctl 필요):
```
[안내] 이 장치가 실제로 지원한다고 보고하는 전체 모드 목록:
    [0]: 'UYVY' (UYVY 4:2:2)
        Size: Discrete 3840x2160
            Interval: Discrete 0.033s (30.000 fps)
    [1]: 'YUYV' (YUYV 4:2:2)
        Size: Discrete 1920x1080
            Interval: Discrete 0.033s (30.000 fps)
[힌트] 4:2:2 계열로 보이는 픽셀 포맷이 목록에 있습니다 (YUYV/UYVY 등).
```

**② 지금 실제로 열려서 녹화 중인 값** (OpenCV가 실제로 받고 있는 값):
```
[시작] 소스: 1 / 실제 적용된 해상도: 1920x1080 / 30.0fps / 픽셀 포맷 코드: YUYV / 3.0초 단위로 저장 → 'segments/' (중지하려면 Ctrl+C)
```

이 예시라면 FX9는 UHD(3840x2160)로 보내고 있는데, 캡처카드가 실제로는
1920x1080으로 받고 있다는 뜻이라 **다운컨버전이 일어난 상태**입니다. `--width
3840 --height 2160`으로 UHD를 직접 요청했는데도 실제 값이 그보다 낮게 나온다면
아래처럼 눈에 띄는 경고가 뜹니다.

```
[주의] 3840x2160를 요청했지만, 장치는 실제로 1920x1080로 동작하고 있습니다. 캡처카드가
요청한 해상도를 지원하지 않아 다운컨버전(또는 가장 가까운 지원 해상도로 대체)했을
가능성이 있습니다.
```

> **10bit / 4:2:2 확인의 한계**: OpenCV로 신뢰성 있게 확인되는 건 해상도와
> FPS까지입니다. 10bit 여부나 4:2:2 색상 서브샘플링까지는 OpenCV만으로 확정하기
> 어렵습니다(운영체제 표준 카메라 인터페이스를 거치면서 캡처카드 드라이버가
> 내부적으로 8bit로 바꿔서 넘겨주는 경우가 흔합니다). 위 ①번 "지원 모드 목록"에
> `4:2:2`, `YUYV`, `UYVY`, `10bit`, `p010` 같은 문구가 보이면 그 캡처카드
> **자체는** 그 모드를 지원한다는 뜻이지만, 실제로 이 스크립트가 그 모드 그대로
> 받고 있는지는 별도로 확인이 필요합니다. 정확한 10bit 4:2:2 캡처가 꼭 필요하면
> 캡처카드 제조사의 전용 캡처 소프트웨어나 ffmpeg를 직접 쓰는 방법도 함께
> 검토해 보시길 권합니다. (`--no-probe`로 ①번 조회를 건너뛸 수 있습니다.)

### 6-3. 세그먼트 저장 (기존과 동일)

장치를 고르고 나면 실행하면 아래처럼 출력되면서 계속 녹화됩니다. **멈추려면
터미널에서 `Ctrl+C`를 누르면 됩니다.** (그 순간까지 녹화 중이던 조각도 끊긴
지점까지 정상적으로 저장되니 파일이 깨지는 것을 걱정하지 않아도 됩니다.)

```
[저장됨] segments/segment_0001.mp4 (약 3.0초, 90프레임)
[저장됨] segments/segment_0002.mp4 (약 3.0초, 90프레임)
...
```

자주 쓰는 옵션 정리:

- `--list-devices` : 장치 목록만 보고 종료
- `--source 1` : 장치 번호를 미리 알고 있을 때 바로 지정 (생략하면 매번 고르게 함)
- `--num-segments 5` : 5개 조각만 저장하고 자동으로 종료 (테스트할 때 유용)
- `--segment-seconds 5` : 3초 대신 5초 단위로 저장
- `--width 3840 --height 2160` : 장치에 요청할 해상도 (실제로 적용됐는지는 위 6-2 참고)
- `--no-probe` : 지원 모드 목록 조회(①번)를 건너뛰고 바로 녹화 시작

예:
```
python scripts/capture_segments.py --source 1 --width 3840 --height 2160 --num-segments 5
```

> **참고**: 이 컴퓨터에 연결된 카메라/캡처카드가 없거나 다른 프로그램(화상회의 앱,
> 다른 캡처 소프트웨어 등)이 이미 그 장치를 쓰고 있으면 `[오류] N번 장치를 열 수
> 없습니다` 라는 안내와 함께 종료됩니다.
>
> 이 스크립트는 실제 웹캠/캡처카드가 없는 원격 개발 환경에서 만들고 검증했습니다.
> 장치 목록 파싱 로직(v4l2-ctl/ffmpeg 출력 해석)은 실제 출력 형식을 그대로 본떠
> 유닛 테스트로 확인했고, 세그먼트 분할·Ctrl+C 안전 종료·해상도 다운컨버전 경고
> 로직은 영상 파일을 가짜 장치처럼 사용해서 실제로 확인했습니다(12초 분량 영상 →
> 3초, 3초, 3초, 2.7초 조각으로 정확히 분할, UHD 요청 시 실제 해상도와 다르면
> 경고 정상 출력). **다만 FX9 + 실제 캡처카드 조합으로 진짜 UHD 30fps 10bit
> 4:2:2 신호를 흘려보내는 테스트는 이 환경에 물리적인 장치가 없어 하지
> 못했습니다** — 실제 장비로 처음 연결하실 때 위 6-1, 6-2 결과를 한 번 확인해
> 주세요.

## 7. (2단계로 넘어가기) 저장된 조각에서 사람 위치 찾기

`segments/` 폴더에 조각들이 쌓이면, 각 조각을 순서대로 `extract_pose_points.py`에
넘겨서 사람 위치를 찾을 수 있습니다.

```
python scripts/extract_pose_points.py --video segments/segment_0001.mp4 --output output/segment_0001_points.json
python scripts/extract_pose_points.py --video segments/segment_0002.mp4 --output output/segment_0002_points.json
```

아래부터는 `extract_pose_points.py`를 처음 써보는 경우를 위한 자세한 설명입니다.

## 8. 테스트용 영상으로 먼저 실행해보기

아직 실제 촬영 영상이 없다면, 아래 명령어로 테스트용 영상을 하나 만들어서
스크립트가 잘 동작하는지 먼저 확인할 수 있습니다. (이 명령어는 사람이 나온 사진
한 장을 반복해서 짧은 영상 파일로 만드는 것뿐입니다.)

```
python -c "import urllib.request; urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-assets/pose.jpg', 'samples/test_person.jpg')"
python -c "
import cv2
img = cv2.imread('samples/test_person.jpg')
h, w = img.shape[:2]
out = cv2.VideoWriter('samples/test_video.mp4', cv2.VideoWriter_fourcc(*'mp4v'), 5, (w, h))
for _ in range(10):
    out.write(img)
out.release()
print('테스트 영상 생성 완료: samples/test_video.mp4')
"
```

그다음 본 스크립트를 실행합니다:

```
python scripts/extract_pose_points.py --video samples/test_video.mp4
```

**처음 실행할 때는** 사람 인식 AI 모델 파일(약 5MB)을 자동으로 내려받기 때문에
몇 초 더 걸립니다. 이후 실행부터는 `models/pose_landmarker_lite.task` 파일이
이미 있으므로 다시 받지 않습니다.

정상적으로 실행되면 아래와 같은 내용이 출력됩니다:

```
[완료] 사람 위치 검출 결과
  - 프레임 크기: 1000x666
  - nose: x=466, y=284 (visibility=1.0)
  - left_shoulder: x=543, y=320 (visibility=1.0)
  - right_shoulder: x=455, y=327 (visibility=1.0)
  - left_hip: x=519, y=474 (visibility=1.0)
  - right_hip: x=468, y=471 (visibility=1.0)

[저장됨] ComfyUI용 JSON: output/pose_points.json
[저장됨] 확인용 미리보기 이미지: output/pose_preview.jpg
```

`output/pose_preview.jpg` 파일을 열어서 초록색 점이 코/어깨/골반 위치에 잘
찍혀 있는지 눈으로 확인해 보세요. (아래는 이 프로젝트를 검증할 때 실제로 나온 결과입니다.)

이 저장소의 `output/` 폴더는 결과물을 git에 올리지 않도록 설정되어 있습니다
(사람이 나온 영상/이미지를 실수로 공개 저장소에 올리지 않기 위한 안전장치입니다).

## 9. 실제 영상으로 실행하기

본인이 준비한 영상 파일(예: `C:\videos\shot01.mp4`)로 실행하려면:

```
python scripts/extract_pose_points.py --video "C:\videos\shot01.mp4" --output output/shot01_points.json --preview output/shot01_preview.jpg
```

- `--video` : 처리할 영상 파일 경로 (필수)
- `--output` : 결과 JSON을 저장할 경로 (생략하면 `output/pose_points.json`)
- `--preview` : 검출 결과 확인용 이미지 경로 (생략하면 `output/pose_preview.jpg`)
- `--frame-index`, `--object-index` : ComfyUI 노드에 그대로 넘길 값
  (사람이 한 명이고 매 클립의 첫 프레임을 쓰는 기본 상황이면 둘 다 그대로 0으로 두면 됩니다)

## 10. ComfyUI에 값 넣는 방법

스크립트 실행 결과 마지막에 아래처럼 출력됩니다:

```
ComfyUI Sam2VideoSegmentationAddPoints 노드에 넣을 값:
  coordinates_positive = [{"x": 466, "y": 284}, {"x": 543, "y": 320}, ...]
  frame_index = 0
  object_index = 0
```

- `coordinates_positive` 값(대괄호 `[` 부터 `]` 까지 전체, 큰따옴표 포함)을 그대로 복사해서
  ComfyUI의 `Sam2VideoSegmentationAddPoints` 노드의 `coordinates_positive` 입력에
  붙여넣습니다. (이 입력은 보통 문자열을 만들어주는 별도 노드—예: Primitive/String
  노드—에 연결해서 넣게 됩니다.)
- `frame_index`, `object_index`는 각각 해당 숫자 입력 칸에 그대로 넣습니다.

같은 내용이 `output/pose_points.json` 파일에도 저장되어 있고, 이 JSON 파일을
바로 다음 단계인 `cloud_client.py`가 그대로 읽어서 API 요청에 자동으로
넣어줍니다 (직접 복사/붙여넣기 하지 않아도 됩니다).

## 11. ComfyUI로 배경 합성 전송하기 (`comfyui_client/`)

이 단계는 `comfyui_client/` 패키지로 구성되어 있습니다. ①번이 만든 사람 위치
JSON을 ComfyUI **워크플로우**(배경을 어떻게 합성할지 정의한 노드 그래프)에
끼워 넣어서 ComfyUI 서버로 전송하고, 처리가 끝난 결과 영상을 받아옵니다.

- **`comfyui_client/cloud_client.py`** — ComfyUI Cloud(https://cloud.comfy.org)
  전용. 예전에는 `scripts/send_to_comfyui.py`였던 파일을 이름/위치만 바꿔
  그대로 옮긴 것이라, **동작은 이전과 완전히 동일**합니다. 지금까지처럼
  `python comfyui_client/cloud_client.py ...` 로 직접 실행해도 되고, 아래
  11-6에서 설명하는 `main.py`를 통해 실행해도 됩니다.
- **`comfyui_client/local_client.py`** — 로컬 ComfyUI(`http://127.0.0.1:8188`)
  전용. 아직 미구현이며(다음 단계에서 작성 예정), 지금 불러오면 "아직
  구현되지 않았습니다"라는 안내와 함께 종료됩니다.
- 두 모듈 모두 `send_frame(frame, prompt_point, ...)`라는 같은 이름의 함수를
  제공해서(로컬 것은 지금은 껍데기뿐), `main.py`가 `--backend cloud`/`--backend
  local` 중 무엇을 고르든 호출하는 코드는 똑같습니다.

아래 11-1~11-4는 예전과 동일한 내용이며, 파일 경로만 `comfyui_client/cloud_client.py`로
바뀌었습니다.

### 11-1. 준비물: 워크플로우 JSON과 노드 ID

이 프로젝트에서 실제로 쓸 워크플로우는 이미 `workflows/background_composite.json`에
저장돼 있고, 노드 ID도 확인해뒀습니다 (아래 표). **바로 11-2로 넘어가도 됩니다.**

| 역할 | 노드 ID | 노드 종류 |
|---|---|---|
| 원본 영상 입력 | `1` | `VHS_LoadVideo` |
| 사람 위치 지정 | `11` | `Sam2VideoSegmentationAddPoints` |
| 결과 영상 저장 | `8` | `VHS_VideoCombine` |

(참고로 이 폴더는 회사 내부 워크플로우가 실수로 GitHub에 올라가지 않도록 git에서
제외되어 있습니다. `workflows/background_composite.json`은 로컬에만 있고
커밋되지 않습니다.)

나중에 워크플로우가 바뀌면 아래 순서로 새 노드 ID를 다시 확인하면 됩니다.

1. ComfyUI 화면에서 워크플로우를 연 상태에서, 메뉴의 **"Save (API Format)"**
   (또는 "Export (API)")로 저장합니다. (화면에 보이는 일반 저장과는 다른
   파일입니다 — 반드시 "API" 표시가 있는 저장 메뉴를 사용해야 합니다. 일반
   저장 파일은 `{"nodes": [...], "links": [...]}` 형태이고, API 형식은
   `{"1": {"class_type": ..., "inputs": {...}}, "2": {...}}` 형태입니다 —
   확장자는 둘 다 `.json`으로 같으니 파일 내용을 열어서 구분해야 합니다.)
2. 저장된 JSON 파일을 텍스트 편집기로 열어서 `"Sam2VideoSegmentationAddPoints"`
   문자열을 찾습니다. 그 앞에 있는 숫자(예: `"11": { "class_type": "Sam2VideoSegmentationAddPoints", ...`
   의 `"11"`)가 **노드 ID**입니다. 원본 영상을 입력받는 노드(`VHS_LoadVideo`
   계열)도 같은 방식으로 찾아둡니다.

### 11-2. 실행

```
python comfyui_client/cloud_client.py \
    --workflow workflows/background_composite.json \
    --pose-json output/segment_0001_points.json \
    --video segments/segment_0001.mp4 \
    --pose-node-id 11 \
    --video-node-id 1 \
    --segment-index 1
```

- `--workflow` : 워크플로우 JSON 경로
- `--pose-json` : `extract_pose_points.py`가 만든 JSON 경로
- `--video`, `--video-node-id` : 원본 영상 경로와, 그 영상을 넣을 노드 ID
  (워크플로우에 이미 영상 경로가 고정되어 있어서 매번 바꿀 필요가 없다면 생략 가능)
- `--pose-node-id` : `Sam2VideoSegmentationAddPoints` 노드 ID (필수)
- `--segment-index` : 결과 파일 이름에 쓸 순서 번호 (1이면 `segment_0001.mp4`로 저장됨)
- `--server` : ComfyUI 서버 주소 (기본값 `http://127.0.0.1:8188` — 같은 컴퓨터에서
  ComfyUI를 띄웠다면 그대로 두면 됩니다)

정상 처리되면 아래처럼 출력되고, 결과 영상이 `output/processed/segment_0001.mp4`에
저장됩니다 (`play_segments.py`가 감시하는 바로 그 폴더입니다):

```
[안내] 노드 '11'(Sam2VideoSegmentationAddPoints)에 사람 위치 좌표를 넣었습니다.
[안내] 노드 '1'(VHS_LoadVideo)의 'video' 입력에 영상 경로를 넣었습니다: segments/segment_0001.mp4
[전송됨] ComfyUI에 작업을 제출했습니다 (prompt_id=...)
[대기] ComfyUI 처리 완료를 기다리는 중... (prompt_id=...)
[완료] 결과 영상을 저장했습니다: output/processed/segment_0001.mp4
```

### 11-3. 이 워크플로우에서 참고할 점

`workflows/background_composite.json`을 열어보면서 확인한 내용입니다 (스크립트
문제가 아니라 워크플로우 자체의 설계에 관한 참고사항입니다).

- **배경은 매번 새로 생성되는 정지 이미지 1장**입니다. `CLIPTextEncode` 노드에
  고정된 프롬프트("부산 해변, 광안대교, 나무 벤치")로 SDXL이 이미지를 만들고,
  그 이미지 한 장을 세그먼트 길이만큼 반복(`RepeatImageBatch`)한 뒤 그 위에
  SAM2로 뽑은 사람 마스크를 합성합니다. 영상 배경이 아니라 고정된 그림입니다.
- **`KSampler`의 negative 프롬프트가 positive와 같은 `CLIPTextEncode` 노드(17)를
  참조**하고 있습니다. 보통은 negative용 별도 노드(빈 텍스트나 "low quality" 등)를
  쓰는데, 지금은 negative 프롬프트가 사실상 없는 것과 같은 효과입니다. 배경
  이미지 품질에 영향을 줄 수 있으니 확인해보시는 걸 권합니다.
- **`seed`가 고정값**(`28151948329631`)입니다. ComfyUI 화면에는 "randomize"
  옵션이 붙어있지만, API로 실행하면 그 옵션은 적용되지 않고 항상 이 시드 값
  그대로 실행됩니다. 매 세그먼트마다 똑같은 배경 이미지가 나온다는 뜻인데,
  배경이 계속 같은 그림이어야 자연스러우니 오히려 의도에 맞을 수도 있습니다.
  다만 세그먼트마다 SDXL 이미지 생성을 매번 새로 돌리는 구조라 처리 시간이
  걸릴 수 있고, 나중에 "배경 이미지는 한 번만 생성해서 재사용" 식으로
  최적화할 여지가 있습니다.
- `Sam2VideoSegmentationAddPoints`(노드 11)의 `coordinates_negative` 입력은
  `PointsEditor`(노드 12)에 저장된 값을 그대로 사용합니다. `extract_pose_points.py`는
  negative 좌표를 만들지 않으므로, 이 스크립트는 `coordinates_positive` /
  `frame_index` / `object_index`만 덮어쓰고 `coordinates_negative`는 건드리지
  않습니다.

### 11-4. 워크플로우 없이 스크립트 동작만 먼저 확인해보기

아직 워크플로우 JSON이 없거나, ComfyUI 서버를 아직 안 띄워봤어도 이 스크립트가
서버와 정확히 어떻게 통신하는지(요청 전송 → 처리 대기 → 결과 다운로드) 미리
확인해볼 수 있습니다. 이 저장소에는 진짜 ComfyUI 서버처럼 응답하는 **가짜(mock)
서버**가 포함되어 있습니다 (실제로 배경을 합성하지는 않고, 지정한 샘플 영상을
그대로 "결과"인 것처럼 돌려줍니다).

터미널 두 개를 엽니다.

**터미널 1** (가짜 서버 실행):
```
python scripts/dev/mock_comfyui_server.py --sample-video samples/test_video.mp4
```

**터미널 2** (전송 스크립트 실행 — 저장소에 포함된 테스트용 워크플로우 사용):
```
python comfyui_client/cloud_client.py \
    --workflow scripts/dev/fixtures/sample_workflow_api.json \
    --pose-json output/pose_points.json \
    --video samples/test_video.mp4 \
    --pose-node-id 6 \
    --video-node-id 3 \
    --segment-index 1
```

`output/processed/segment_0001.mp4`가 생기면 정상입니다. 실제 워크플로우를
받으면 `--workflow`와 `--pose-node-id`/`--video-node-id`만 실제 값으로 바꿔서
똑같이 쓰면 됩니다.

### 11-5. ComfyUI Cloud(https://cloud.comfy.org)로 실행하기

로컬 ComfyUI 대신 ComfyUI Cloud를 쓸 수도 있습니다. `--platform cloud`를 붙이면
됩니다 (엔드포인트 경로와 인증 방식이 로컬과 달라서 내부적으로 다르게 동작합니다).

**API 키를 받으면 그대로 실행할 명령 (준비 완료)**:

```
export COMFY_API_KEY="sk-..."   # 실제 발급받은 키로 교체. 절대 커맨드 인자로 넘기지 말 것

python comfyui_client/cloud_client.py \
    --platform cloud \
    --server https://cloud.comfy.org \
    --workflow workflows/background_composite.json \
    --pose-json output/segment_0001_points.json \
    --video segments/segment_0001.mp4 \
    --pose-node-id 11 \
    --video-node-id 1 \
    --frame-load-cap 30 \
    --repeat-node-id 6 \
    --segment-index 1 \
    --dry-run
```

먼저 `--dry-run`으로 한 번 실행해서 `output/dry_run_workflow.json`을 열어보고,
`coordinates_positive`/`frame_load_cap`(30)/`amount`(30)가 의도대로 들어갔는지
확인한 뒤, **`--dry-run`을 빼고** 다시 실행하면 실제로 ComfyUI Cloud에 전송됩니다.
`--frame-load-cap 30`은 처리할 프레임 수를 30개(1초 분량)로 줄여서 크레딧을
아끼기 위한 것이고, `--repeat-node-id 6`은 배경 반복 프레임 수를 그 30에 맞춰서
함께 줄이는 옵션입니다. 이 워크플로우가 원래 갖고 있던 negative 포인트, CPU
디바이스(`device: cpu`), `mp4/h264`, `crf 18` 설정은 스크립트가 건드리지 않으므로
그대로 유지됩니다.

- `--api-key-env` (기본값 `COMFY_API_KEY`): API 키를 어느 환경변수에서 읽을지.
  **API 키는 항상 환경변수로만 주고, `--api-key-env` 자체에 키 값을 직접 넣지
  마세요** (쉘 기록에 남습니다).
- 인증 헤더는 `X-API-Key`(ComfyUI Cloud 방식)를 사용합니다. Bearer 토큰이
  아닙니다.

> **이 저장소를 만든 환경(원격 개발 서버)에서는 실제 전송을 확인하지 못했습니다.**
> `cloud.comfy.org`로 나가는 네트워크 자체가 이 환경의 조직 정책으로 차단되어
> 있어서(`CONNECT` 요청이 403으로 거부됨), API 키가 있어도 이 환경에서는
> 애초에 접속이 안 됩니다. 대신:
> - 요청/응답 로직(작업 제출 → `X-API-Key` 인증 → 상태 폴링 → 파일 다운로드 →
>   `--frame-load-cap`/`--repeat-node-id` 값 주입)은 ComfyUI Cloud API 스펙을
>   그대로 흉내 낸 가짜 서버(`scripts/dev/mock_comfyui_server.py`)로 실제 왕복
>   테스트를 마쳤습니다. 인증 실패(401) 상황도 확인했습니다.
> - 실제 `cloud.comfy.org`의 정확한 API 응답 형식(특히 작업 ID 필드 이름이
>   `job_id`인지, `GET /api/jobs/{id}` 응답의 완료 상태 문자열이 정확히 무엇인지)은
>   공식 문서가 검색 결과로만 확인 가능했고 원문 페이지 접근은 막혀 있어서,
>   100% 확정하지는 못했습니다. 코드는 `job_id`/`prompt_id`/`id`, `completed`/
>   `success`/`succeeded` 등 후보를 여러 개 함께 확인하도록 방어적으로 만들어
>   뒀지만, 실제 응답이 이 가정과 다르면 원문 오류 메시지를 그대로 보여주게
>   되어 있으니 처음 실행할 때 로그를 확인해 주세요.
> - 회사 컴퓨터(또는 `cloud.comfy.org` 접속이 되는 다른 환경)에서 API 키를 받고
>   위 명령을 실행하면 됩니다. 실패하면 나온 오류 메시지를 그대로 알려주세요 —
>   특히 작업 ID나 완료 상태 판단이 어긋났다면 그 부분만 고치면 됩니다.

### 11-6. `main.py`로 실행하기 (cloud/local 공용 진입점)

`comfyui_client/cloud_client.py`를 직접 실행하는 대신, 저장소 최상위의
`main.py`를 통해 실행할 수도 있습니다. `--backend` 옵션으로 클라우드/로컬을
고르는데, **기본값이 `cloud`라서 옵션을 안 주면 지금까지와 완전히 같은
동작**입니다.

```
python main.py \
    --workflow workflows/background_composite.json \
    --frame segments/segment_0001.mp4 \
    --prompt-point output/segment_0001_points.json \
    --pose-node-id 11 \
    --video-node-id 1 \
    --frame-load-cap 30 \
    --repeat-node-id 6 \
    --segment-index 1
```

`comfyui_client/cloud_client.py`를 직접 실행할 때와 옵션 이름이 대부분
같은데, 두 가지만 다릅니다: `--video` 대신 `--frame`(처리할 세그먼트 영상
경로), `--pose-json` 대신 `--prompt-point`(사람 위치 JSON 경로)를 씁니다.
나중에 `--backend local`이 준비되면(local_client.py, 다음 단계) 같은
명령에 `--backend local`만 추가하면 됩니다 — 지금 시도하면 아직
미구현이라는 안내와 함께 종료됩니다.

이 저장소를 검증할 때는, 가짜(mock) ComfyUI 서버를 대상으로 (1)
`comfyui_client/cloud_client.py`를 예전과 같은 방식으로 직접 실행한 결과와
(2) `main.py`를 통해 실행한 결과가 둘 다 동일하게 성공하는 것을 확인했고,
`--dry-run`으로 만든 최종 워크플로우 JSON에서 `frame_load_cap`/`amount`가
의도대로 반영된 것도 확인했습니다. `comfyui_client/cloud_client.py`
파일 자체는 예전 `scripts/send_to_comfyui.py`에서 **줄 단위로 삭제되거나
수정된 부분 없이**(`git diff`로 확인) `send_frame()` 함수만 새로 추가됐습니다.

## 12. 결과를 화면에 순서대로 재생하기 (`play_segments.py`)

`cloud_client.py`가 `output/processed/` 폴더에 결과 영상을 쌓아가면, 이
스크립트가 그 폴더를 감시하면서 `segment_0001.mp4`부터 순서대로 화면에
재생합니다. 아직 처리되지 않은 조각은 "처리 대기 중" 화면을 보여주며 기다렸다가,
파일이 생기는 즉시 이어서 재생합니다 (몇 초 지연은 자연스럽게 흡수됩니다).

```
python scripts/play_segments.py
```

- 다른 키를 누르면 현재 조각을 건너뛰고 다음 조각으로 넘어갑니다.
- `q`를 누르면 종료합니다.
- `--input-dir`로 감시할 폴더를, `--start-index`로 시작 번호를 바꿀 수 있습니다.

실제 촬영 파이프라인에서는 4개 스크립트를 아래처럼 각자 계속 돌려두면 됩니다
(터미널 4개, 또는 다른 방식의 자동화):

```
터미널 1: python scripts/capture_segments.py                     # 카메라 → segments/
터미널 2: (segments/에 새 조각이 생길 때마다) extract_pose_points.py 실행
터미널 3: (JSON이 생길 때마다) cloud_client.py 실행 → output/processed/
터미널 4: python scripts/play_segments.py                        # output/processed/ 재생
```

> 터미널 2, 3을 매번 손으로 실행하는 대신 자동으로 돌리는 부분(새 파일이 생기면
> 자동 실행)은 아직 만들지 않았습니다. 지금은 4개 스크립트 각각의 기능이
> 준비된 단계이고, 필요하시면 이 부분을 감시 자동화 스크립트로 이어서
> 만들어드릴 수 있습니다.

## 13. 문제 해결 (Troubleshooting)

**`python` 명령을 찾을 수 없다는 오류가 날 때**
→ 1번(Python 설치)에서 "Add python.exe to PATH" 체크를 빠뜨렸을 가능성이 큽니다.
Python을 다시 설치하면서 체크박스를 확인하세요.

**`pip install` 도중 빨간 글씨의 `ERROR`가 날 때**
→ 회사 네트워크의 방화벽/프록시 문제일 수 있습니다. IT 담당자에게 "pypi.org 접속을
허용해달라"고 요청하거나, 개인 네트워크(핫스팟 등)에서 한 번 시도해 보세요.

**`capture_segments.py` 실행 시 "N번 장치를 열 수 없습니다" 라고 나올 때**
→ 다음을 순서대로 확인해 보세요.
1. 카메라/캡처카드가 실제로 컴퓨터에 USB로 연결되어 있는지
2. 화상회의 프로그램(Zoom, Teams 등)이나 다른 캡처 소프트웨어가 이미 그 장치를
   쓰고 있지 않은지 — 열려 있다면 종료 후 다시 시도
3. `--list-devices`로 지금 컴퓨터가 인식하는 장치 번호를 다시 확인하고, 그
   번호로 `--source`를 지정 (캡처카드를 나중에 꽂으면 번호가 바뀔 수 있습니다)

**`capture_segments.py`에서 장치 목록에 이름이 안 보이고 번호만 나올 때**
→ Windows/macOS에서 장치 이름까지 보려면 `ffmpeg`가 설치되어 있어야 합니다.
[ffmpeg 공식 사이트](https://ffmpeg.org/download.html)에서 받아 설치한 뒤
다시 실행해 보세요 (설치 안 해도 번호 선택과 녹화 자체는 그대로 됩니다).
Linux는 `sudo apt-get install v4l-utils`로 `v4l2-ctl`을 설치하면 됩니다.

**FX9(캡처카드)를 연결했는데 해상도가 요청한 것보다 낮게 나올 때**
→ `[주의] ... 다운컨버전 ...` 경고가 뜬다면, 캡처카드가 실제로 그 해상도/FPS를
지원하지 않는다는 뜻입니다. `--no-probe` 없이 실행해서 나오는 "①번 지원 모드
목록"을 보고 그 캡처카드가 실제로 어떤 최대 해상도/FPS/픽셀 포맷까지 지원하는지
확인하세요. 목록에도 UHD 30fps가 안 보인다면 캡처카드 자체의 사양 한계이고,
목록에는 있는데 실제 적용은 안 된다면 캡처카드 제조사의 드라이버/전용 소프트웨어
쪽 설정(입력 신호 포맷을 수동으로 맞춰야 하는 캡처카드도 있습니다)을 확인해
보시는 걸 권합니다.

**"첫 프레임에서 사람을 찾지 못했습니다" 라고 나올 때**
→ 영상의 첫 프레임에 사람이 온전히 보이지 않는 경우입니다 (너무 어둡거나, 화면 밖으로
나가 있거나, 뒷모습이라 관절 인식이 어려운 경우). 사람이 잘 보이는 다른 영상으로
먼저 테스트해 보세요.

**모델 파일 다운로드가 실패할 때 (`[오류] 모델 파일 다운로드에 실패했습니다`)**
→ 회사 네트워크가 `storage.googleapis.com` 접속을 막고 있을 수 있습니다. 오류 메시지에
나온 주소를 다른 네트워크에서 내려받은 뒤, 오류 메시지에 나온 저장 경로
(`models/pose_landmarker_lite.task`)에 파일을 직접 복사해 넣고 다시 실행하면 됩니다.

**리눅스(회사 리눅스 서버 등)에서 `libEGL.so.1` 또는 `libGLESv2.so.2` 관련 오류가 날 때**
→ 이 스크립트는 CPU로만 동작하지만, 사용 중인 mediapipe 버전에 따라 화면 출력용
그래픽 라이브러리를 찾는 경우가 있습니다. 아래 명령으로 관련 라이브러리를 설치하면
해결됩니다.
```
sudo apt-get update && sudo apt-get install -y libegl1 libgl1
```
(Windows/macOS에서는 이 문제가 발생하지 않습니다.)

**`cloud_client.py` 실행 시 "ComfyUI 서버에 연결할 수 없습니다" 라고 나올 때**
→ 다음을 확인해 보세요.
1. ComfyUI가 실제로 실행 중인지 (ComfyUI를 실행하면 보통 터미널에 "Starting server"와
   함께 주소가 표시됩니다)
2. `--server` 값이 ComfyUI가 실제로 뜬 주소와 일치하는지 (기본값은
   `http://127.0.0.1:8188`이며, 같은 컴퓨터에서 기본 설정으로 띄웠다면 보통 맞습니다)
3. ComfyUI가 다른 컴퓨터에서 돌고 있다면, 그 컴퓨터의 IP 주소로 `--server`를
   지정해야 합니다 (예: `--server http://192.168.0.10:8188`)

**`cloud_client.py` 실행 시 "워크플로우에 노드 ID '...'가 없습니다" 라고 나올 때**
→ `--pose-node-id` 또는 `--video-node-id`로 지정한 번호가 실제 워크플로우 JSON
파일 안의 노드 ID와 다릅니다. 워크플로우 JSON 파일을 텍스트 편집기로 열어서
해당 노드(`Sam2VideoSegmentationAddPoints` 등)를 찾고, 그 노드를 감싸는 큰따옴표
숫자 키를 다시 확인하세요.

**`play_segments.py` 실행 시 화면 창이 안 뜨거나 바로 꺼질 때**
→ 원격 데스크톱/SSH로 접속해서 실행 중이라면, 화면 출력(그래픽) 세션이 연결되어
있는지 확인하세요. 컴퓨터에 직접 앉아서 실행하는 경우라면 보통 문제가 없습니다.

---

## 참고: 검출 대상 관절

MediaPipe Pose는 사람의 관절 33개를 인식하는데, 이 스크립트는 그중 배경 합성용
사람 영역을 지정하는 데 충분한 5개만 사용합니다.

| 이름 | 설명 |
|---|---|
| nose | 코 |
| left_shoulder / right_shoulder | 왼쪽 / 오른쪽 어깨 |
| left_hip / right_hip | 왼쪽 / 오른쪽 골반 |

필요하면 `scripts/extract_pose_points.py`의 `LANDMARK_INDEXES` 딕셔너리에 다른
관절(손목, 무릎 등)을 추가할 수 있습니다. 전체 33개 관절 번호는
[MediaPipe 공식 문서](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker#models)에서
확인할 수 있습니다.
