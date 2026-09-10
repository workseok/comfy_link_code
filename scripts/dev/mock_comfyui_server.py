"""
mock_comfyui_server.py (개발/테스트용)

실제 ComfyUI 서버 없이 send_to_comfyui.py의 동작(요청 구성, 결과 대기, 파일 다운로드)을
검증하기 위한 가짜 ComfyUI 서버입니다. 로컬 ComfyUI 표준 API와 ComfyUI Cloud API
두 가지 경로를 모두 흉내 냅니다.

로컬(표준 ComfyUI) 경로:
    POST /prompt          → 받은 워크플로우를 파일로 저장하고 즉시 완료 처리
    GET  /history/<id>    → 처리 결과(가짜 출력 영상 정보)를 돌려줌
    GET  /view?filename=..&subfolder=..&type=..
                          → --sample-video로 지정한 영상 파일 내용을 그대로 돌려줌

ComfyUI Cloud 경로 (send_to_comfyui.py --platform cloud 검증용):
    POST /api/prompt      → 위와 동일하지만 X-API-Key 헤더를 확인하고 job_id를 돌려줌
    GET  /api/jobs/<id>   → execution_status/outputs 형태로 처리 결과를 돌려줌
    GET  /api/view?filename=..
                          → 위와 동일 (X-API-Key 헤더 확인)
    --require-api-key로 지정한 값과 다른 키가 오면 401을 돌려줘서, 실제 클라우드처럼
    인증 실패 상황도 재현해볼 수 있습니다.

실제 ComfyUI처럼 "워크플로우를 진짜로 실행해서 배경을 합성"하지는 않습니다.
send_to_comfyui.py가 서버와 정확히 어떻게 대화하는지(요청 형식, 폴링, 다운로드,
원자적 파일 저장, 인증 헤더)를 실제 서버 없이도 검증하기 위한 용도입니다.

사용법:
    python scripts/dev/mock_comfyui_server.py --sample-video samples/test_video.mp4

--port으로 포트를 바꿀 수 있습니다 (기본값: 8188, 실제 ComfyUI 기본 포트와 동일).
--delay-seconds로 "처리 시간"을 흉내 낼 수 있습니다 (기본값: 2초 뒤에 완료로 처리).
--require-api-key로 클라우드 경로에서 요구할 API 키 값을 지정할 수 있습니다
(지정하지 않으면 어떤 키가 와도 통과시킵니다).
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# 제출된 prompt_id -> 완료 여부/결과 를 저장하는 아주 단순한 메모리 저장소.
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()

_SAMPLE_VIDEO_PATH = None
_PROCESSING_DELAY_SECONDS = 2.0
_RECEIVED_WORKFLOWS_DIR = None
_REQUIRED_API_KEY = None


def _make_outputs(job_id: str) -> dict:
    return {
        # 실제 VHS_VideoCombine류 노드가 돌려주는 모양을 흉내 냄
        "9": {
            "gifs": [
                {
                    "filename": f"mock_output_{job_id}.mp4",
                    "subfolder": "",
                    "type": "output",
                    "format": "video/h264-mp4",
                }
            ]
        }
    }


def _finish_job_later(job_id: str, delay_seconds: float):
    def worker():
        time.sleep(delay_seconds)
        with _JOBS_LOCK:
            _JOBS[job_id] = {"outputs": _make_outputs(job_id)}
        print(f"[mock 서버] job_id={job_id} 처리 완료로 표시함")

    threading.Thread(target=worker, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 기본 접속 로그를 조금 더 보기 좋게
        print(f"[mock 서버] {self.address_string()} - {fmt % args}")

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_api_key(self) -> bool:
        """cloud 경로 전용: --require-api-key로 지정한 값과 X-API-Key 헤더를 비교한다."""
        if _REQUIRED_API_KEY is None:
            return True
        provided = self.headers.get("X-API-Key")
        if provided == _REQUIRED_API_KEY:
            return True
        self._send_json(401, {"error": "invalid or missing X-API-Key"})
        return False

    def _handle_submit(self, respond_key: str):
        """POST /prompt(로컬) 또는 POST /api/prompt(cloud) 공통 처리."""
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return

        job_id = str(uuid.uuid4())

        if _RECEIVED_WORKFLOWS_DIR:
            os.makedirs(_RECEIVED_WORKFLOWS_DIR, exist_ok=True)
            with open(
                os.path.join(_RECEIVED_WORKFLOWS_DIR, f"{job_id}.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        with _JOBS_LOCK:
            _JOBS[job_id] = None  # 아직 처리 중

        print(f"[mock 서버] 새 작업 접수: {respond_key}={job_id}")
        _finish_job_later(job_id, _PROCESSING_DELAY_SECONDS)

        self._send_json(200, {respond_key: job_id, "number": 1, "node_errors": {}})

    def _serve_sample_video(self, filename: str):
        if not _SAMPLE_VIDEO_PATH or not os.path.exists(_SAMPLE_VIDEO_PATH):
            self._send_json(500, {"error": "mock 서버에 --sample-video가 설정되지 않았습니다"})
            return
        with open(_SAMPLE_VIDEO_PATH, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/prompt":
            self._handle_submit(respond_key="prompt_id")
            return

        if self.path == "/api/prompt":
            if not self._check_api_key():
                return
            self._handle_submit(respond_key="job_id")
            return

        self._send_json(404, {"error": "not found"})

    def do_GET(self):
        parsed = urlparse(self.path)

        # --- 로컬(표준 ComfyUI) 경로 ---
        if parsed.path.startswith("/history/"):
            prompt_id = parsed.path.rsplit("/", 1)[-1]
            with _JOBS_LOCK:
                result = _JOBS.get(prompt_id)
            if result is None:
                self._send_json(200, {})  # 아직 처리 중이면 빈 객체 (실제 ComfyUI와 동일)
            else:
                self._send_json(200, {prompt_id: result})
            return

        if parsed.path == "/view":
            qs = parse_qs(parsed.query)
            self._serve_sample_video(qs.get("filename", [""])[0])
            return

        # --- ComfyUI Cloud 경로 ---
        if parsed.path.startswith("/api/jobs/"):
            if not self._check_api_key():
                return
            job_id = parsed.path.rsplit("/", 1)[-1]
            with _JOBS_LOCK:
                result = _JOBS.get(job_id)
            if job_id not in _JOBS:
                self._send_json(404, {"error": f"unknown job_id {job_id}"})
            elif result is None:
                self._send_json(200, {"id": job_id, "execution_status": "running", "outputs": None})
            else:
                self._send_json(
                    200,
                    {"id": job_id, "execution_status": "completed", "outputs": result["outputs"]},
                )
            return

        if parsed.path == "/api/view":
            if not self._check_api_key():
                return
            qs = parse_qs(parsed.query)
            self._serve_sample_video(qs.get("filename", [""])[0])
            return

        self._send_json(404, {"error": "not found"})


def main():
    global _SAMPLE_VIDEO_PATH, _PROCESSING_DELAY_SECONDS, _RECEIVED_WORKFLOWS_DIR, _REQUIRED_API_KEY

    parser = argparse.ArgumentParser(description="send_to_comfyui.py 검증용 가짜 ComfyUI 서버")
    parser.add_argument("--port", type=int, default=8188)
    parser.add_argument(
        "--sample-video",
        required=True,
        help="/view (또는 /api/view) 요청에 실제로 돌려줄 영상 파일 (결과 영상 흉내)",
    )
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument(
        "--save-received-workflows-to",
        default=None,
        help="전송받은 워크플로우 JSON을 저장해둘 폴더 (검증용, 선택)",
    )
    parser.add_argument(
        "--require-api-key",
        default=None,
        help="/api/* 경로(cloud 흉내)에서 요구할 X-API-Key 값. 지정하지 않으면 아무 키나 통과시킵니다.",
    )
    args = parser.parse_args()

    _SAMPLE_VIDEO_PATH = args.sample_video
    _REQUIRED_API_KEY = args.require_api_key
    _PROCESSING_DELAY_SECONDS = args.delay_seconds
    _RECEIVED_WORKFLOWS_DIR = args.save_received_workflows_to

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[mock 서버] http://127.0.0.1:{args.port} 에서 대기 중 (Ctrl+C로 종료)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
