# AI 배경 합성 프로토타입

촬영 현장에서 카메라 영상에 AI로 배경을 합성하는 시스템입니다. 4단계 전체가 이
저장소에 있습니다.

| 단계 | 내용 | 파일 |
|---|---|---|
| ① | 웹캠/HDMI 캡처카드 영상을 3~5초 단위로 저장 | `scripts/capture_segments.py` |
| ② | 각 조각의 첫 프레임에서 사람 위치 자동 인식 | `scripts/extract_pose_points.py` |
| ③ | ComfyUI(클라우드 또는 로컬)로 보내서 배경 합성 | `main.py`, `comfyui_client/` |
| ④ | 합성된 조각을 순서대로 화면에 재생 | `scripts/play_segments.py` |

## 설치 및 사용법

사용 중인 운영체제에 맞는 문서 하나만 보면, 설치부터 실행까지 끝낼 수
있습니다.

- 🪟 **Windows** → [`docs/SETUP_WINDOWS.md`](./docs/SETUP_WINDOWS.md)
- 🍎 **macOS** → [`docs/SETUP_MAC.md`](./docs/SETUP_MAC.md)

코드는 두 운영체제 모두 동일합니다(저장소나 브랜치가 OS별로 나뉘어 있지
않습니다) — 두 문서는 같은 코드를 각 OS 기준으로 설치·실행하는 방법만
따로 설명합니다.

## 더 자세한 내용이 필요하다면

워크플로우 노드 구성, ComfyUI Cloud API 관련 참고사항, mock 서버로
개발/검증하는 방법 등 개발·유지보수용 세부 내용은
[`docs/DEVELOPMENT.md`](./docs/DEVELOPMENT.md)에 있습니다.
