"""
local_client.py (아직 미구현 — 다음 단계에서 작성 예정)

로컬 ComfyUI 서버(기본 http://127.0.0.1:8188)를 호출하는 클라이언트가 들어갈
자리입니다. cloud_client.py와 똑같은 send_frame(frame, prompt_point, ...)
인터페이스로 만들어서, main.py --backend local 을 고르면 호출부 코드는 그대로
두고 이 모듈만 쓰이게 할 예정입니다.

로컬은 클라우드와 다음이 다릅니다 (구현 시 반드시 반영해야 함):
    - 인증이 필요 없음 (X-API-Key 헤더 없음)
    - 엔드포인트 경로가 다름: POST /prompt, GET /history/{prompt_id}, GET /view
      (클라우드는 /api/prompt, /api/jobs/{id}, /api/view)
    - 응답 처리 방식(동기/비동기)을 실제 로컬 ComfyUI 서버로 확인해야 함:
      표준 ComfyUI REST API는 POST /prompt가 prompt_id만 즉시 돌려주고 실제
      처리는 백그라운드에서 진행되는 비동기 방식이며, GET /history/{prompt_id}를
      폴링하거나 WebSocket(/ws)으로 진행 상황을 받는 것이 일반적입니다. 다만
      이건 문서/일반적인 동작 기준이고, 로컬 ComfyUI가 실제로 설치·실행된
      뒤에 정말 그렇게 동작하는지 확인이 필요합니다.

지금은 main.py가 --backend local을 선택했을 때 깨지지 않고 "아직 미구현"이라고
명확히 알리기 위한 최소 골격만 있습니다.
"""

from __future__ import annotations


def send_frame(frame: str, prompt_point, **kwargs) -> str:
    raise NotImplementedError(
        "local_client.py는 아직 구현되지 않았습니다. 로컬 ComfyUI 서버(기본값: "
        "http://127.0.0.1:8188)가 설치·실행 중인 환경에서 다음 단계로 작성할 "
        "예정입니다. 지금은 --backend cloud를 사용해 주세요."
    )
