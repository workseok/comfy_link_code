# 개발/유지보수 참고 문서

설치·사용법은 [`docs/SETUP_WINDOWS.md`](./SETUP_WINDOWS.md) 또는
[`docs/SETUP_MAC.md`](./SETUP_MAC.md)를 보세요. 이 문서는 그 두 문서에 넣기엔
너무 상세하거나 개발자/유지보수자에게만 필요한 내용을 모아둔 곳입니다.

## 저장소 구조

```
capture_segments.py            extract_pose_points.py          comfyui_client/               play_segments.py
(웹캠/캡처카드 → 3초 조각)  →  (조각 첫 프레임 → 사람 위치 JSON)  →  (JSON+워크플로우 → ComfyUI → 결과 영상) →  (결과 조각을 화면에 순서대로 재생)
segments/segment_0001.mp4      output/segment_0001_points.json     output/processed/segment_0001.mp4
```

```
scripts/capture_segments.py      ① 웹캠/HDMI 캡처카드 → 3~5초 단위 영상 조각
scripts/extract_pose_points.py   ② 조각 첫 프레임 → MediaPipe Pose → 사람 위치 JSON
comfyui_client/
  cloud_client.py                 ③ ComfyUI Cloud(https://cloud.comfy.org) 전송기
  local_client.py                 ③ 로컬 ComfyUI(http://127.0.0.1:8188) 전송기 — 아직 미구현
main.py                           ③ cloud/local 공용 진입점 (--backend, 기본값 cloud)
scripts/play_segments.py         ④ 결과 조각을 순서대로 화면에 재생
scripts/dev/mock_comfyui_server.py  개발용 — 실제 ComfyUI 서버 없이 ③번 검증
workflows/                        ComfyUI 워크플로우 JSON (git에서 제외, 직접 채워 넣는 폴더)
segments/, output/, samples/      실행 산출물 (git에서 제외)
```

## `comfyui_client/` — cloud/local 분리 구조

`comfyui_client/cloud_client.py`와 `comfyui_client/local_client.py`는 같은
이름의 `send_frame(frame, prompt_point, ...)` 함수를 제공합니다. `main.py`는
`--backend cloud`(기본값) 또는 `--backend local`에 따라 둘 중 하나를 골라
호출하며, 호출부 코드는 백엔드에 따라 달라지지 않습니다.

- **`cloud_client.py`**는 예전 `scripts/send_to_comfyui.py`를 이름/위치만
  바꿔 그대로 옮긴 것입니다 (git 이력상 rename으로 추적되며, `git diff`로
  기존 로직이 한 줄도 바뀌지 않았음을 확인할 수 있습니다). ComfyUI Cloud
  전용 엔드포인트(`/api/prompt`, `/api/jobs/{id}`, `/api/view`)와 `X-API-Key`
  헤더 인증을 씁니다.
- **`local_client.py`**는 아직 미구현입니다 (`send_frame()`이
  `NotImplementedError`를 던짐). 로컬 ComfyUI는 클라우드와 다음이 다르므로,
  실제 로컬 서버로 검증한 뒤 새로 작성해야 합니다:
  - 인증 불필요 (`X-API-Key` 없음)
  - 엔드포인트가 다름: `POST /prompt`, `GET /history/{prompt_id}`,
    `GET /view` (표준 ComfyUI REST API)
  - 응답 처리(동기/비동기) 방식을 실제 서버로 확인 필요 — 표준 ComfyUI는
    `POST /prompt`가 `prompt_id`만 즉시 돌려주고 실제 처리는 백그라운드에서
    진행되는 비동기 방식이며, `GET /history/{id}` 폴링이나 WebSocket(`/ws`)으로
    진행 상황을 받는 것이 일반적이지만, 실제 로컬 ComfyUI가 설치·실행된
    뒤에 다시 확인해야 합니다.

## 워크플로우(`workflows/background_composite.json`) 참고사항

이 파일은 회사 내부 워크플로우라 git에서 제외되어 있고, 로컬에만 있습니다.
각자 ComfyUI 화면에서 **"Save (API Format)"**(또는 "Export (API)")로 내보낸
파일을 이 폴더에 넣어야 합니다 — 화면에 보이는 일반 저장(`{"nodes": [...],
"links": [...]}`)과는 다른 형식(`{"1": {"class_type": ..., "inputs": {...}}}`)
이며, 확장자는 둘 다 `.json`이라 파일 내용을 열어서 구분해야 합니다.

현재 이 프로젝트가 쓰는 워크플로우의 노드 ID:

| 역할 | 노드 ID | 노드 종류 |
|---|---|---|
| 원본 영상 입력 | `1` | `VHS_LoadVideo` |
| 사람 위치 지정 | `11` | `Sam2VideoSegmentationAddPoints` |
| 결과 영상 저장 | `8` | `VHS_VideoCombine` |
| 배경 이미지 반복 | `6` | `RepeatImageBatch` |

이 워크플로우 자체의 설계에 대해 확인한 참고사항 (스크립트 문제가 아님):

- **배경은 매번 새로 생성되는 정지 이미지 1장**입니다. `CLIPTextEncode` 노드에
  고정된 프롬프트로 SDXL이 이미지를 만들고, 그 이미지 한 장을 세그먼트
  길이만큼 반복(`RepeatImageBatch`)한 뒤 그 위에 SAM2로 뽑은 사람 마스크를
  합성합니다. 영상 배경이 아니라 고정된 그림입니다.
- **`KSampler`의 negative 프롬프트가 positive와 같은 `CLIPTextEncode` 노드를
  참조**하고 있습니다. 보통은 negative용 별도 노드(빈 텍스트나 "low quality"
  등)를 쓰는데, 지금은 negative 프롬프트가 사실상 없는 것과 같은 효과입니다.
  배경 이미지 품질에 영향을 줄 수 있으니 확인해 볼 가치가 있습니다.
- **`seed`가 고정값**입니다. ComfyUI 화면에는 "randomize" 옵션이 붙어있지만,
  API로 실행하면 그 옵션은 적용되지 않고 항상 같은 시드로 실행됩니다. 매
  세그먼트마다 똑같은 배경 이미지가 나온다는 뜻인데, 배경이 계속 같은
  그림이어야 자연스러우니 오히려 의도에 맞을 수도 있습니다. 다만 세그먼트마다
  SDXL 이미지 생성을 매번 새로 돌리는 구조라 처리 시간이 걸릴 수 있고,
  "배경 이미지는 한 번만 생성해서 재사용" 식으로 최적화할 여지가 있습니다.
- `Sam2VideoSegmentationAddPoints`(노드 11)의 `coordinates_negative` 입력은
  `PointsEditor`(노드 12)에 저장된 값을 그대로 사용합니다.
  `extract_pose_points.py`는 negative 좌표를 만들지 않으므로,
  `cloud_client.py`는 `coordinates_positive`/`frame_index`/`object_index`만
  덮어쓰고 `coordinates_negative`는 건드리지 않습니다.

## ComfyUI Cloud API 스펙에 대한 미확인 사항

`https://cloud.comfy.org`의 정확한 API 응답 형식 — 특히 작업 ID 필드 이름이
`job_id`인지, `GET /api/jobs/{id}` 응답의 완료 상태 문자열이 정확히
무엇인지 — 는 공식 문서(`docs.comfy.org`)에 대한 직접 접근이 이 저장소를
개발한 환경에서 네트워크 정책으로 막혀 있어(egress 차단), 검색 결과 스니펫으로만
확인했고 100% 확정하지 못했습니다. `cloud_client.py`는 `job_id`/`prompt_id`/
`id`, `completed`/`success`/`succeeded` 등 후보를 여러 개 함께 확인하도록
방어적으로 만들어 두었지만, 실제 응답이 이 가정과 다르면 원문 오류 메시지를
그대로 출력하게 되어 있으니 실제 계정으로 처음 실행할 때 로그를 확인해 주세요.

또한 `cloud.comfy.org`로 나가는 네트워크 자체가 이 저장소를 개발한 환경에서
조직 정책으로 차단되어 있어서, 실제 전송까지는 이 환경에서 확인하지
못했습니다. 요청/응답 로직(작업 제출 → 인증 → 상태 폴링 → 파일 다운로드 →
`--frame-load-cap`/`--repeat-node-id` 값 주입)은 아래 mock 서버로 왕복
테스트를 마쳤습니다.

## mock 서버로 ③번(ComfyUI 전송)을 실제 ComfyUI 없이 검증하기

`scripts/dev/mock_comfyui_server.py`는 로컬 ComfyUI 표준 API(`/prompt`,
`/history`, `/view`)와 ComfyUI Cloud API(`/api/prompt`, `/api/jobs/{id}`,
`/api/view`, `X-API-Key` 인증) 양쪽을 다 흉내 냅니다. 실제로 배경을 합성하지는
않고, 지정한 샘플 영상을 그대로 "결과"인 것처럼 돌려줍니다.

**터미널 1** (가짜 서버 실행):
```
python scripts/dev/mock_comfyui_server.py --sample-video samples/test_video.mp4 --require-api-key sk-test
```

**터미널 2** (저장소에 포함된 테스트용 워크플로우로 전송):
```
export COMFY_API_KEY=sk-test
python comfyui_client/cloud_client.py \
    --platform cloud \
    --server http://127.0.0.1:8188 \
    --workflow scripts/dev/fixtures/sample_workflow_api.json \
    --pose-json output/pose_points.json \
    --video samples/test_video.mp4 \
    --pose-node-id 6 \
    --video-node-id 3 \
    --segment-index 1
```

`output/processed/segment_0001.mp4`가 생기면 정상입니다. 실제 워크플로우로
바꿔 쓸 때는 `--workflow`와 `--pose-node-id`/`--video-node-id`만 실제 값으로
바꾸면 됩니다.

## 전체 파이프라인을 한 번에 돌리기

지금은 4개 스크립트를 각자 실행해야 합니다 (새 파일이 생기면 다음 단계를
자동 실행하는 감시 자동화는 아직 없습니다):

```
터미널 1: python scripts/capture_segments.py                     # 카메라 → segments/
터미널 2: (segments/에 새 조각이 생길 때마다) extract_pose_points.py 실행
터미널 3: (JSON이 생길 때마다) main.py 실행 → output/processed/
터미널 4: python scripts/play_segments.py                        # output/processed/ 재생
```

## 검출 대상 관절

MediaPipe Pose는 사람의 관절 33개를 인식하는데, `extract_pose_points.py`는
그중 배경 합성용 사람 영역을 지정하는 데 충분한 5개만 사용합니다.

| 이름 | 설명 |
|---|---|
| nose | 코 |
| left_shoulder / right_shoulder | 왼쪽 / 오른쪽 어깨 |
| left_hip / right_hip | 왼쪽 / 오른쪽 골반 |

필요하면 `scripts/extract_pose_points.py`의 `LANDMARK_INDEXES` 딕셔너리에 다른
관절(손목, 무릎 등)을 추가할 수 있습니다. 전체 33개 관절 번호는
[MediaPipe 공식 문서](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker#models)에서
확인할 수 있습니다.

## `capture_segments.py`의 장치 목록/probe 로직 검증 범위

이 스크립트는 실제 웹캠/캡처카드가 없는 원격 개발 환경에서 만들고
검증했습니다.

- 장치 목록 파싱 로직(`v4l2-ctl`/`ffmpeg -f dshow`/`ffmpeg -f avfoundation`
  출력 해석)은 실제 출력 형식을 그대로 본떠 유닛 테스트로 확인했습니다.
- 세그먼트 분할, Ctrl+C 안전 종료, 해상도 다운컨버전 경고 로직은 영상
  파일을 가짜 장치처럼 사용해서 실제로 확인했습니다 (12초 분량 영상 → 3초,
  3초, 3초, 2.7초 조각으로 정확히 분할되는 것, UHD 요청 시 실제 해상도와
  다르면 경고가 뜨는 것 모두 확인).
- **실제 FX9 + 캡처카드 조합으로 진짜 UHD 30fps 10bit 4:2:2 신호를 흘려보내는
  테스트는 하지 못했습니다** — 물리 장치가 없는 환경의 한계입니다. 실제
  장비로 처음 연결할 때 `--list-devices`와 장치 선택 후 나오는 "실제 적용된
  해상도/FPS" 로그를 한 번 확인해 주세요.

## 리눅스 서버/WSL에서 `libEGL.so.1` 관련 오류가 날 때

`extract_pose_points.py`는 CPU로만 동작하지만, 사용 중인 mediapipe 버전에
따라 화면 출력용 그래픽 라이브러리를 찾는 경우가 있습니다. 아래 명령으로
해결됩니다 (Windows/macOS에서는 발생하지 않는 문제입니다):

```
sudo apt-get update && sudo apt-get install -y libegl1 libgl1
```
