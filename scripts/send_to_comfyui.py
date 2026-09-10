"""
send_to_comfyui.py

extract_pose_points.py가 만든 "사람 위치 JSON"을 ComfyUI 워크플로우에 끼워 넣어
ComfyUI 서버(로컬 또는 ComfyUI Cloud)의 API로 전송하고, 배경 합성이 끝난 결과
영상을 받아서 저장하는 스크립트입니다.

★★★ 준비물 ★★★
- ComfyUI에서 "API 형식"으로 내보낸 워크플로우 JSON 파일 (이 프로젝트는
  workflows/background_composite.json에 이미 저장되어 있습니다)
- Sam2VideoSegmentationAddPoints 노드 ID / 원본 영상 입력 노드 ID
  (이 프로젝트는 각각 11 / 1 입니다)

사용법 — 로컬 ComfyUI 서버:
    python scripts/send_to_comfyui.py \\
        --workflow workflows/background_composite.json \\
        --pose-json output/segment_0001_points.json \\
        --video segments/segment_0001.mp4 \\
        --pose-node-id 11 \\
        --video-node-id 1 \\
        --segment-index 1

사용법 — ComfyUI Cloud (https://cloud.comfy.org):
    export COMFY_API_KEY="sk-..."   # 절대 커맨드라인 인자로 직접 넘기지 말 것 (쉘 히스토리에 남음)
    python scripts/send_to_comfyui.py \\
        --platform cloud \\
        --server https://cloud.comfy.org \\
        --workflow workflows/background_composite.json \\
        --pose-json output/segment_0001_points.json \\
        --video segments/segment_0001.mp4 \\
        --pose-node-id 11 \\
        --video-node-id 1 \\
        --frame-load-cap 30 \\
        --repeat-node-id 6 \\
        --segment-index 1

크레딧이 아까운 클라우드 실행 전에는 먼저 --dry-run으로 최종 워크플로우가
의도대로 만들어졌는지 파일로 저장해서 확인해 보는 것을 권장합니다 (실제 전송은
하지 않음).

옵션:
    --workflow             ComfyUI API 형식 워크플로우 JSON 경로 (필수)
    --pose-json             extract_pose_points.py가 만든 JSON 경로 (필수)
    --video                  처리할 원본 영상(세그먼트) 파일 경로 (선택. --video-node-id와
                             함께 지정하면 워크플로우에 이 영상 경로를 자동으로 넣어줌)
    --pose-node-id           Sam2VideoSegmentationAddPoints 노드 ID (필수)
    --video-node-id          원본 영상을 입력받는 노드 ID (선택)
    --video-input-key        위 노드에서 영상 경로를 받는 입력 필드 이름 (기본값: video)
    --frame-load-cap         원본 영상에서 불러올 최대 프레임 수. 지정하면
                             --video-node-id 노드의 frame_load_cap을 이 값으로 설정한다
                             (크레딧을 아끼려고 프레임 수를 줄일 때 사용).
    --repeat-node-id         배경 이미지를 프레임 수만큼 반복하는 노드 ID (예:
                             RepeatImageBatch). --frame-load-cap과 같은 값으로
                             amount를 맞춰서, 배경 프레임 수와 사람 마스크 프레임 수가
                             어긋나지 않게 한다.
    --repeat-amount-key      위 노드에서 반복 횟수를 받는 입력 필드 이름 (기본값: amount)
    --platform               local(기본값) 또는 cloud. cloud는 ComfyUI Cloud
                             (https://cloud.comfy.org) 전용 API 경로/인증을 사용한다.
    --server                 서버 주소 (기본값: http://127.0.0.1:8188)
    --api-key-env            (cloud 전용) API 키를 읽어올 환경변수 이름 (기본값: COMFY_API_KEY).
                             보안을 위해 API 키는 커맨드라인 인자가 아니라 반드시
                             환경변수로만 받는다.
    --comfy-org-api-key-env  (cloud 전용, 선택) 워크플로우가 Comfy.org 관리형 API 노드를
                             쓸 때 필요한 별도 키의 환경변수 이름. 이 프로젝트의
                             워크플로우(로컬 체크포인트 + SAM2)는 보통 필요 없다.
    --output-dir             결과 영상을 저장할 폴더 (기본값: output/processed,
                             play_segments.py가 감시하는 폴더와 동일)
    --segment-index          결과 파일 이름에 쓸 순서 번호 (예: 1 → segment_0001.mp4)
    --timeout-seconds        처리 완료를 기다리는 최대 시간(초) (기본값: 300)
    --poll-seconds           처리 상태를 확인하는 간격(초) (기본값: 2)
    --dry-run                실제로 전송하지 않고, 최종 주입된 워크플로우 JSON만
                             저장하고 종료한다 (기본 저장 경로: output/dry_run_workflow.json)
    --dry-run-output         --dry-run일 때 저장할 경로

동작 방식 (local/cloud 공통):
    1) 워크플로우 JSON을 읽는다.
    2) --pose-node-id로 지정한 노드의 입력값을 pose-json 파일 내용
       (coordinates_positive / frame_index / object_index)으로 덮어쓴다.
    3) --video-node-id를 지정했다면, 그 노드의 입력값도 --video 경로로 덮어쓴다.
    4) --frame-load-cap을 지정했다면, 해당 프레임 수 제한과(있다면) 반복 노드의
       amount를 함께 맞춘다.
    5) --dry-run이면 여기서 멈추고 파일로 저장한다. 아니라면 서버에 작업을 제출한다.
    6) 처리 상태를 주기적으로 확인해서 끝날 때까지 기다린다.
    7) 결과 영상을 내려받아 --output-dir에 segment_XXXX.mp4로 저장하고(다운로드는
       임시 파일 → 원자적 rename 방식이라 play_segments.py가 미완성 파일을 읽는
       사고를 방지한다), OpenCV로 실제로 열어봐서 프레임 수/해상도를 확인하고
       첫 프레임을 미리보기 이미지로 저장한다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        print(f"[오류] 파일을 찾을 수 없습니다: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def inject_pose_inputs(workflow: dict, pose_node_id: str, pose_data: dict) -> None:
    if pose_node_id not in workflow:
        print(
            f"[오류] 워크플로우에 노드 ID '{pose_node_id}'가 없습니다. "
            "--pose-node-id 값이 맞는지 ComfyUI에서 다시 확인해 주세요."
        )
        sys.exit(1)

    node = workflow[pose_node_id]
    node.setdefault("inputs", {})
    node["inputs"]["coordinates_positive"] = pose_data["coordinates_positive"]
    node["inputs"]["frame_index"] = pose_data["frame_index"]
    node["inputs"]["object_index"] = pose_data["object_index"]
    print(
        f"[안내] 노드 '{pose_node_id}'({node.get('class_type', '?')})에 사람 위치 좌표를 넣었습니다."
    )


def inject_video_input(workflow: dict, video_node_id: str, video_input_key: str, video_path: str) -> None:
    if video_node_id not in workflow:
        print(
            f"[오류] 워크플로우에 노드 ID '{video_node_id}'가 없습니다. "
            "--video-node-id 값이 맞는지 ComfyUI에서 다시 확인해 주세요."
        )
        sys.exit(1)

    node = workflow[video_node_id]
    node.setdefault("inputs", {})
    node["inputs"][video_input_key] = video_path
    print(
        f"[안내] 노드 '{video_node_id}'({node.get('class_type', '?')})의 '{video_input_key}' "
        f"입력에 영상 경로를 넣었습니다: {video_path}"
    )


def inject_frame_cap(
    workflow: dict,
    video_node_id: str | None,
    frame_load_cap: int,
    repeat_node_id: str | None,
    repeat_amount_key: str,
) -> None:
    """크레딧을 아끼기 위해 처리할 프레임 수를 줄인다.

    원본 영상 로드 노드의 frame_load_cap만 줄이고 배경 반복 노드(RepeatImageBatch 등)의
    amount는 그대로 두면, 사람 마스크는 짧은데 배경은 원래 길이만큼 반복되어 합성
    결과가 어긋날 수 있다. 그래서 두 값을 같은 프레임 수로 함께 맞춘다.
    """
    if video_node_id:
        if video_node_id not in workflow:
            print(f"[오류] 워크플로우에 노드 ID '{video_node_id}'가 없습니다.")
            sys.exit(1)
        node = workflow[video_node_id]
        node.setdefault("inputs", {})
        node["inputs"]["frame_load_cap"] = frame_load_cap
        print(f"[안내] 노드 '{video_node_id}'의 frame_load_cap을 {frame_load_cap}으로 줄였습니다.")

    if repeat_node_id:
        if repeat_node_id not in workflow:
            print(
                f"[오류] 워크플로우에 노드 ID '{repeat_node_id}'가 없습니다. "
                "--repeat-node-id 값이 맞는지 확인해 주세요."
            )
            sys.exit(1)
        node = workflow[repeat_node_id]
        node.setdefault("inputs", {})
        node["inputs"][repeat_amount_key] = frame_load_cap
        print(
            f"[안내] 노드 '{repeat_node_id}'({node.get('class_type', '?')})의 "
            f"'{repeat_amount_key}'를 {frame_load_cap}으로 맞췄습니다 "
            "(배경 반복 프레임 수를 원본 프레임 수와 일치시킴)."
        )


# ---------------------------------------------------------------------------
# 로컬 ComfyUI 서버용 (표준 /prompt, /history, /view API)
# ---------------------------------------------------------------------------


def submit_prompt(server: str, workflow: dict, client_id: str) -> str:
    url = f"{server.rstrip('/')}/prompt"
    payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(
            f"[오류] ComfyUI 서버가 요청을 거부했습니다 (HTTP {exc.code}). "
            "워크플로우 노드 ID나 입력값이 잘못되었을 수 있습니다.\n"
            f"서버 응답: {error_body}"
        )
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(
            f"[오류] ComfyUI 서버({server})에 연결할 수 없습니다: {exc.reason}\n"
            "ComfyUI가 실행 중인지, --server 주소가 맞는지 확인해 주세요."
        )
        sys.exit(1)

    prompt_id = body.get("prompt_id")
    if not prompt_id:
        print(f"[오류] 서버 응답에서 prompt_id를 찾지 못했습니다: {body}")
        sys.exit(1)
    return prompt_id


def wait_for_result(server: str, prompt_id: str, timeout_seconds: float, poll_seconds: float) -> dict:
    url = f"{server.rstrip('/')}/history/{prompt_id}"
    deadline = time.time() + timeout_seconds
    print(f"[대기] ComfyUI 처리 완료를 기다리는 중... (prompt_id={prompt_id})")

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                history = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            print(f"[오류] 처리 상태 확인 중 서버 연결에 실패했습니다: {exc}")
            sys.exit(1)

        if prompt_id in history:
            return history[prompt_id]

        time.sleep(poll_seconds)

    print(
        f"[오류] {timeout_seconds}초 동안 처리가 끝나지 않았습니다. ComfyUI가 아직 처리 "
        "중이거나(무거운 워크플로우는 더 오래 걸릴 수 있음), 오류가 났을 수 있습니다. "
        "ComfyUI 화면(또는 콘솔 로그)에서 상태를 확인해 주세요."
    )
    sys.exit(1)


def download_output(server: str, file_info: dict, output_path: str) -> None:
    params = {
        "filename": file_info["filename"],
        "subfolder": file_info.get("subfolder", ""),
        "type": file_info.get("type", "output"),
    }
    url = f"{server.rstrip('/')}/view?{urllib.parse.urlencode(params)}"
    _download_to_path(url, {}, output_path)


# ---------------------------------------------------------------------------
# ComfyUI Cloud 전용 (/api/prompt, /api/jobs/{id}, /api/view, X-API-Key 인증)
#
# 공식 문서(docs.comfy.org)가 이 개발 환경에서는 네트워크 정책상 직접 열람이
# 막혀 있어서, 검색으로 확인한 내용을 바탕으로 만들었다. 특히 아래 두 가지는
# 100% 확정하지 못했으므로 방어적으로 여러 후보를 함께 처리한다:
#   - POST /api/prompt 응답에서 작업 ID 필드 이름 (job_id 또는 prompt_id로 추정)
#   - GET /api/jobs/{id} 응답의 완료 여부 판단 기준 (execution_status 필드의
#     정확한 문자열 값)
# 실제로 처음 실행했을 때 이 가정이 틀렸다면, 원문 응답을 그대로 출력하도록
# 만들어서 바로 확인하고 고칠 수 있게 했다.
# ---------------------------------------------------------------------------


def submit_prompt_cloud(server: str, workflow: dict, api_key: str, comfy_org_api_key: str | None) -> tuple[str, dict]:
    url = f"{server.rstrip('/')}/api/prompt"
    body = {"prompt": workflow}
    if comfy_org_api_key:
        body["extra_data"] = {"api_key_comfy_org": comfy_org_api_key}
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            response_body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(
            f"[오류] ComfyUI Cloud가 요청을 거부했습니다 (HTTP {exc.code}).\n"
            f"서버 응답: {error_body}"
        )
        if exc.code in (401, 403):
            print("[안내] API 키가 잘못됐거나 만료됐을 가능성이 높습니다 (X-API-Key 헤더).")
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(
            f"[오류] ComfyUI Cloud({server})에 연결할 수 없습니다: {exc.reason}\n"
            "--server 주소가 맞는지, 이 컴퓨터에서 외부 인터넷 접속이 되는지 확인해 주세요."
        )
        sys.exit(1)

    job_id = response_body.get("job_id") or response_body.get("prompt_id") or response_body.get("id")
    if not job_id:
        print(
            "[오류] 서버 응답에서 작업 ID(job_id/prompt_id/id)를 찾지 못했습니다. "
            f"전체 응답을 그대로 보여드립니다: {json.dumps(response_body, ensure_ascii=False)}"
        )
        sys.exit(1)
    return job_id, response_body


def wait_for_result_cloud(server: str, job_id: str, api_key: str, timeout_seconds: float, poll_seconds: float) -> dict:
    url = f"{server.rstrip('/')}/api/jobs/{job_id}"
    deadline = time.time() + timeout_seconds
    print(f"[대기] ComfyUI Cloud 처리 완료를 기다리는 중... (job_id={job_id})")

    done_markers = {"completed", "success", "succeeded", "finished", "done"}
    failed_markers = {"failed", "error", "cancelled", "canceled"}
    last_status_shown = None

    while time.time() < deadline:
        request = urllib.request.Request(url, headers={"X-API-Key": api_key}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                job = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            print(f"[오류] 작업 상태 확인이 실패했습니다 (HTTP {exc.code}): {error_body}")
            sys.exit(1)
        except urllib.error.URLError as exc:
            print(f"[오류] 처리 상태 확인 중 서버 연결에 실패했습니다: {exc}")
            sys.exit(1)

        status = job.get("execution_status")
        status_text = status if isinstance(status, str) else json.dumps(status, ensure_ascii=False)
        if status_text != last_status_shown:
            print(f"[진행] 상태: {status_text}")
            last_status_shown = status_text

        execution_error = job.get("execution_error")
        if execution_error:
            print(
                "[오류] ComfyUI Cloud에서 실행 중 오류가 발생했습니다:\n"
                f"{json.dumps(execution_error, ensure_ascii=False, indent=2)}"
            )
            sys.exit(1)

        status_lower = status.lower() if isinstance(status, str) else ""
        if isinstance(status, dict):
            status_lower = str(status.get("status") or status.get("state") or "").lower()
        if status_lower in failed_markers:
            print(f"[오류] 작업이 실패 상태로 끝났습니다. 전체 응답: {json.dumps(job, ensure_ascii=False)[:2000]}")
            sys.exit(1)

        is_done = status_lower in done_markers or bool(job.get("outputs"))
        if is_done:
            return job

        time.sleep(poll_seconds)

    print(
        f"[오류] {timeout_seconds}초 동안 처리가 끝나지 않았습니다. 마지막으로 확인한 상태: "
        f"{last_status_shown}"
    )
    sys.exit(1)


def download_output_cloud(server: str, api_key: str, file_info: dict, output_path: str) -> None:
    params = {"filename": file_info["filename"]}
    if file_info.get("subfolder"):
        params["subfolder"] = file_info["subfolder"]
    if file_info.get("type"):
        params["type"] = file_info["type"]
    url = f"{server.rstrip('/')}/api/view?{urllib.parse.urlencode(params)}"
    _download_to_path(url, {"X-API-Key": api_key}, output_path)


# ---------------------------------------------------------------------------
# 공통
# ---------------------------------------------------------------------------


def find_output_file(result: dict) -> dict | None:
    """작업 결과에서 저장된 영상/이미지 파일 정보를 찾는다.

    ComfyUI는 노드 종류에 따라 outputs[node_id]["gifs"], ["videos"], ["images"] 등
    다양한 키 아래에 {"filename", "subfolder", "type"} 형식으로 결과를 담아 돌려준다.
    워크플로우가 다양할 수 있으므로, 특정 키에 의존하지 않고 그런 모양의 항목을
    찾아서 그중 영상 파일처럼 보이는 것을 우선한다.
    """
    video_extensions = (".mp4", ".avi", ".mov", ".webm", ".mkv")
    candidates = []

    outputs = result.get("outputs", {})
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for value in node_output.values():
            if not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, dict) and "filename" in item:
                    candidates.append(item)

    if not candidates:
        return None

    for item in candidates:
        if str(item["filename"]).lower().endswith(video_extensions):
            return item
    return candidates[0]


def _download_to_path(url: str, headers: dict, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    tmp_path = output_path + ".downloading"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            with open(tmp_path, "wb") as f:
                f.write(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"[오류] 결과 파일 다운로드에 실패했습니다: {exc}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        sys.exit(1)

    # 다운로드가 끝난 뒤에만 정식 파일명으로 바꿔서, 다른 프로그램(play_segments.py 등)이
    # 다운로드 도중의 미완성 파일을 읽어버리는 일이 없게 한다.
    os.replace(tmp_path, output_path)


def verify_downloaded_video(output_path: str) -> None:
    """받은 파일이 실제로 열리는 영상인지, 진짜 합성된 결과처럼 보이는지 확인한다."""
    try:
        import cv2
    except ImportError:
        print("[안내] OpenCV가 없어서 결과 영상을 직접 열어보는 확인은 건너뜁니다.")
        return

    cap = cv2.VideoCapture(output_path)
    if not cap.isOpened():
        print(f"[경고] 다운로드는 됐지만 영상 파일로 열리지 않습니다: {output_path} (파일이 손상됐을 수 있습니다)")
        return

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    ok, frame = cap.read()
    cap.release()

    if not ok:
        print(f"[경고] 영상 파일은 열렸지만 프레임을 하나도 읽지 못했습니다: {output_path}")
        return

    preview_path = output_path.rsplit(".", 1)[0] + "_preview.jpg"
    cv2.imwrite(preview_path, frame)

    print(
        f"[검증] 결과 영상 확인: {width}x{height}, {frame_count}프레임, {fps:.1f}fps "
        f"— 실제로 열리고 재생 가능한 영상입니다."
    )
    print(f"[검증] 첫 프레임을 미리보기 이미지로 저장했습니다: {preview_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="사람 위치 JSON을 ComfyUI 워크플로우에 넣어 전송하고(로컬 또는 ComfyUI Cloud) 결과 영상을 받습니다."
    )
    parser.add_argument("--workflow", required=True, help="ComfyUI API 형식 워크플로우 JSON 경로")
    parser.add_argument("--pose-json", required=True, help="extract_pose_points.py가 만든 JSON 경로")
    parser.add_argument("--video", default=None, help="처리할 원본 영상(세그먼트) 파일 경로")
    parser.add_argument("--pose-node-id", required=True, help="Sam2VideoSegmentationAddPoints 노드 ID")
    parser.add_argument("--video-node-id", default=None, help="원본 영상을 입력받는 노드 ID")
    parser.add_argument("--video-input-key", default="video", help="영상 경로를 받는 입력 필드 이름")
    parser.add_argument(
        "--frame-load-cap",
        type=int,
        default=None,
        help="원본 영상에서 불러올 최대 프레임 수 (크레딧을 아끼려고 줄일 때 사용)",
    )
    parser.add_argument(
        "--repeat-node-id",
        default=None,
        help="배경 이미지를 프레임 수만큼 반복하는 노드 ID (--frame-load-cap과 같이 사용)",
    )
    parser.add_argument("--repeat-amount-key", default="amount", help="반복 노드의 반복 횟수 입력 필드 이름")
    parser.add_argument(
        "--platform",
        choices=["local", "cloud"],
        default="local",
        help="local(기본값): 표준 ComfyUI 서버 API. cloud: ComfyUI Cloud 전용 API/인증 사용",
    )
    parser.add_argument("--server", default="http://127.0.0.1:8188", help="서버 주소")
    parser.add_argument(
        "--api-key-env",
        default="COMFY_API_KEY",
        help="(cloud 전용) API 키를 읽어올 환경변수 이름 (기본값: COMFY_API_KEY). "
        "보안을 위해 API 키 값 자체를 커맨드라인 인자로 넘기지 않는다.",
    )
    parser.add_argument(
        "--comfy-org-api-key-env",
        default=None,
        help="(cloud 전용, 선택) Comfy.org 관리형 API 노드용 별도 키의 환경변수 이름",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join("output", "processed"),
        help="결과 영상을 저장할 폴더 (기본값: output/processed)",
    )
    parser.add_argument(
        "--segment-index",
        type=int,
        required=True,
        help="결과 파일 이름에 쓸 순서 번호 (예: 1 → segment_0001.mp4)",
    )
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제로 전송하지 않고, 최종 주입된 워크플로우 JSON만 저장하고 종료합니다.",
    )
    parser.add_argument(
        "--dry-run-output",
        default=None,
        help="--dry-run일 때 저장할 경로 (기본값: output/dry_run_workflow.json)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.video_node_id and not args.video:
        print("[오류] --video-node-id를 지정했다면 --video 경로도 함께 지정해야 합니다.")
        sys.exit(1)

    workflow = load_json(args.workflow)
    pose_data = load_json(args.pose_json)

    inject_pose_inputs(workflow, args.pose_node_id, pose_data)
    if args.video_node_id:
        inject_video_input(workflow, args.video_node_id, args.video_input_key, args.video)
    if args.frame_load_cap:
        inject_frame_cap(
            workflow, args.video_node_id, args.frame_load_cap, args.repeat_node_id, args.repeat_amount_key
        )

    if args.dry_run:
        dry_run_path = args.dry_run_output or os.path.join("output", "dry_run_workflow.json")
        os.makedirs(os.path.dirname(dry_run_path) or ".", exist_ok=True)
        with open(dry_run_path, "w", encoding="utf-8") as f:
            json.dump(workflow, f, ensure_ascii=False, indent=2)
        print(f"\n[dry-run] 실제로 전송하지 않았습니다. 최종 워크플로우를 저장했습니다: {dry_run_path}")
        print("[dry-run] 내용을 확인한 뒤, --dry-run 옵션을 빼고 다시 실행하면 실제로 전송됩니다.")
        return

    output_path = os.path.join(args.output_dir, f"segment_{args.segment_index:04d}.mp4")

    if args.platform == "cloud":
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            print(
                f"[오류] 환경변수 {args.api_key_env}가 설정되어 있지 않습니다. "
                f"API 키를 발급받은 뒤 터미널에서 `export {args.api_key_env}=sk-...`로 "
                "설정하고 다시 실행해 주세요. (API 키는 커맨드라인 인자로 직접 넘기지 마세요 — "
                "쉘 기록에 남습니다.)"
            )
            sys.exit(1)
        comfy_org_api_key = (
            os.environ.get(args.comfy_org_api_key_env) if args.comfy_org_api_key_env else None
        )

        job_id, _ = submit_prompt_cloud(args.server, workflow, api_key, comfy_org_api_key)
        print(f"[전송됨] ComfyUI Cloud에 작업을 제출했습니다 (job_id={job_id})")

        result = wait_for_result_cloud(args.server, job_id, api_key, args.timeout_seconds, args.poll_seconds)

        file_info = find_output_file(result)
        if file_info is None:
            print(
                "[오류] 처리는 끝났지만 결과 파일을 찾지 못했습니다. "
                f"작업 응답: {json.dumps(result, ensure_ascii=False)[:2000]}"
            )
            sys.exit(1)

        download_output_cloud(args.server, api_key, file_info, output_path)
    else:
        client_id = str(uuid.uuid4())
        prompt_id = submit_prompt(args.server, workflow, client_id)
        print(f"[전송됨] ComfyUI에 작업을 제출했습니다 (prompt_id={prompt_id})")

        result = wait_for_result(args.server, prompt_id, args.timeout_seconds, args.poll_seconds)

        file_info = find_output_file(result)
        if file_info is None:
            print(
                "[오류] ComfyUI가 처리는 끝냈지만 결과 파일을 찾지 못했습니다. "
                f"history 응답: {json.dumps(result, ensure_ascii=False)[:1000]}"
            )
            sys.exit(1)

        download_output(args.server, file_info, output_path)

    print(f"[완료] 결과 영상을 저장했습니다: {output_path}")
    verify_downloaded_video(output_path)


if __name__ == "__main__":
    main()
