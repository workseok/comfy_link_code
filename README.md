# AI 배경 합성 프로토타입

촬영 현장에서 카메라 영상에 AI로 배경을 합성하는 시스템입니다. 4단계 전체가 이
저장소에 있습니다.

| 단계 | 내용 | 스크립트 |
|---|---|---|
| 1 | 카메라 영상을 3~5초 단위로 저장 | `scripts/capture_segments.py` ✅ |
| 2 | 영상 첫 프레임에서 사람 위치 자동 인식 | `scripts/extract_pose_points.py` ✅ |
| 3 | ComfyUI API로 배경 합성 자동 전송 | `scripts/send_to_comfyui.py` ✅ |
| 4 | 처리된 결과 영상을 순서대로 화면에 재생 | `scripts/play_segments.py` ✅ |

**전체 흐름**: 카메라 → ①3초 조각 저장 → ②조각 첫 프레임에서 사람 위치 검출 →
③ComfyUI에 전송해서 배경 합성 → ④합성된 조각을 순서대로 화면에 재생.

```
capture_segments.py            extract_pose_points.py          send_to_comfyui.py                play_segments.py
(웹캠 → 3초 조각)      →      (조각 첫 프레임 → 사람 위치 JSON)  →  (JSON+워크플로우 → ComfyUI → 결과 영상) →  (결과 조각을 화면에 순서대로 재생)
segments/segment_0001.mp4      output/segment_0001_points.json     output/processed/segment_0001.mp4
```

> **3번 단계에 대한 중요한 전제**: `send_to_comfyui.py`는 배경 합성을 실제로
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

(`send_to_comfyui.py`는 파이썬에 기본 내장된 기능만 사용해서 별도 패키지가
필요 없습니다.)

버전을 정확히 고정해 두었으니 (`requirements.txt` 참고) 그대로 설치하면 이 문서에서
검증한 것과 동일하게 동작합니다.

설치 중 `WARNING: Running pip as ...` 같은 노란색 경고는 무시해도 됩니다. 빨간색
`ERROR`가 나오면 아래 "문제 해결" 항목을 참고하세요.

## 6. 웹캠으로 3초 단위 영상 저장하기 (`capture_segments.py`)

가장 간단한 사용법: 아무 옵션 없이 실행하면 컴퓨터의 첫 번째 웹캠에서 영상을 받아
3초 단위로 잘라 `segments/` 폴더에 저장합니다.

```
python scripts/capture_segments.py
```

실행하면 아래처럼 출력되면서 계속 녹화됩니다. **멈추려면 터미널에서 `Ctrl+C`를
누르면 됩니다.** (그 순간까지 녹화 중이던 조각도 끊긴 지점까지 정상적으로
저장되니 파일이 깨지는 것을 걱정하지 않아도 됩니다.)

```
[시작] 소스: 0 / 해상도: 1280x720 / 30.0fps / 3.0초 단위로 저장 → 'segments/' (중지하려면 Ctrl+C)
[저장됨] segments/segment_0001.mp4 (약 3.0초, 90프레임)
[저장됨] segments/segment_0002.mp4 (약 3.0초, 90프레임)
...
```

자주 쓰는 옵션:

- `--num-segments 5` : 5개 조각만 저장하고 자동으로 종료 (테스트할 때 유용)
- `--segment-seconds 5` : 3초 대신 5초 단위로 저장
- `--source 1` : 웹캠이 여러 대일 때 다른 카메라 사용 (0번이 안 되면 1, 2 순서로 시도)
- `--width 1280 --height 720` : 카메라 해상도 지정

예:
```
python scripts/capture_segments.py --num-segments 5 --segment-seconds 3
```

> **참고**: 이 컴퓨터에 연결된 카메라가 없거나 다른 프로그램(화상회의 앱 등)이
> 카메라를 이미 쓰고 있으면 `[오류] 0번 카메라를 열 수 없습니다` 라는 안내와 함께
> 종료됩니다. 카메라 연결 상태를 확인하거나 다른 프로그램을 먼저 종료해 보세요.
>
> 이 스크립트는 실제 웹캠이 없는 개발 환경에서 검증했기 때문에, 웹캠 대신 영상
> 파일을 `--source`로 넣어 "3초 단위로 정확히 잘리는지 / Ctrl+C로 중단해도
> 안전하게 저장되는지"를 실제로 테스트했습니다(12초 분량 영상 → 3초, 3초, 3초,
> 2.7초 조각 4개로 정확히 분할됨을 확인). 실제 웹캠으로 실행할 때의 동작도 코드
> 로직상 동일하며, 위 예시 로그의 해상도/FPS 값은 카메라마다 달라집니다.

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
바로 다음 단계인 `send_to_comfyui.py`가 그대로 읽어서 API 요청에 자동으로
넣어줍니다 (직접 복사/붙여넣기 하지 않아도 됩니다).

## 11. ComfyUI로 배경 합성 전송하기 (`send_to_comfyui.py`)

이 스크립트는 ①번이 만든 사람 위치 JSON을 ComfyUI **워크플로우**(배경을 어떻게
합성할지 정의한 노드 그래프)에 끼워 넣어서 ComfyUI 서버로 전송하고, 처리가
끝난 결과 영상을 받아옵니다.

### 11-1. 준비물: 워크플로우 JSON과 노드 ID

1. ComfyUI 화면에서 배경 합성 워크플로우를 연 상태에서, 메뉴의
   **"Save (API Format)"**(또는 "Export (API)")로 저장합니다. (화면에 보이는
   일반 저장과는 다른 파일입니다 — 반드시 "API" 표시가 있는 저장 메뉴를
   사용해야 합니다.)
2. 저장된 파일을 이 저장소의 `workflows/` 폴더에 넣습니다 (예: `workflows/background_composite.json`).
   이 폴더는 회사 내부 워크플로우가 실수로 GitHub에 올라가지 않도록 git에서
   제외되어 있습니다.
3. 저장된 JSON 파일을 텍스트 편집기로 열어서 `"Sam2VideoSegmentationAddPoints"`
   문자열을 찾습니다. 그 앞에 있는 숫자(예: `"6": { "class_type": "Sam2VideoSegmentationAddPoints", ...`
   의 `"6"`)가 **노드 ID**입니다. 원본 영상을 입력받는 노드(보통 "Load Video"
   계열)도 같은 방식으로 노드 ID를 찾아둡니다.

### 11-2. 실행

```
python scripts/send_to_comfyui.py \
    --workflow workflows/background_composite.json \
    --pose-json output/segment_0001_points.json \
    --video segments/segment_0001.mp4 \
    --pose-node-id 6 \
    --video-node-id 3 \
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
[안내] 노드 '6'(Sam2VideoSegmentationAddPoints)에 사람 위치 좌표를 넣었습니다.
[전송됨] ComfyUI에 작업을 제출했습니다 (prompt_id=...)
[대기] ComfyUI 처리 완료를 기다리는 중... (prompt_id=...)
[완료] 결과 영상을 저장했습니다: output/processed/segment_0001.mp4
```

### 11-3. 워크플로우 없이 스크립트 동작만 먼저 확인해보기

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
python scripts/send_to_comfyui.py \
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

## 12. 결과를 화면에 순서대로 재생하기 (`play_segments.py`)

`send_to_comfyui.py`가 `output/processed/` 폴더에 결과 영상을 쌓아가면, 이
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
터미널 3: (JSON이 생길 때마다) send_to_comfyui.py 실행 → output/processed/
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

**`capture_segments.py` 실행 시 "0번 카메라를 열 수 없습니다" 라고 나올 때**
→ 다음을 순서대로 확인해 보세요.
1. 웹캠이 실제로 컴퓨터에 연결되어 있는지 (USB 웹캠이면 케이블 확인)
2. 화상회의 프로그램(Zoom, Teams 등)이 이미 카메라를 쓰고 있지 않은지 — 열려 있다면
   종료 후 다시 시도
3. 노트북에 카메라가 여러 개거나 가상 카메라 프로그램이 설치돼 있다면
   `--source 1`, `--source 2` 처럼 다른 번호로 시도

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

**`send_to_comfyui.py` 실행 시 "ComfyUI 서버에 연결할 수 없습니다" 라고 나올 때**
→ 다음을 확인해 보세요.
1. ComfyUI가 실제로 실행 중인지 (ComfyUI를 실행하면 보통 터미널에 "Starting server"와
   함께 주소가 표시됩니다)
2. `--server` 값이 ComfyUI가 실제로 뜬 주소와 일치하는지 (기본값은
   `http://127.0.0.1:8188`이며, 같은 컴퓨터에서 기본 설정으로 띄웠다면 보통 맞습니다)
3. ComfyUI가 다른 컴퓨터에서 돌고 있다면, 그 컴퓨터의 IP 주소로 `--server`를
   지정해야 합니다 (예: `--server http://192.168.0.10:8188`)

**`send_to_comfyui.py` 실행 시 "워크플로우에 노드 ID '...'가 없습니다" 라고 나올 때**
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
