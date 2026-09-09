"""
send_to_comfyui.py

extract_pose_points.py가 만든 "사람 위치 JSON"을 ComfyUI 워크플로우에 끼워 넣어
ComfyUI 서버의 API로 전송하고, 배경 합성이 끝난 결과 영상을 받아서
저장하는 스크립트입니다.

★★★ 중요 — 아직 채워지지 않은 부분 ★★★
이 스크립트는 "배경 합성을 수행하는 ComfyUI 워크플로우 JSON 파일"이 있어야 동작합니다.
ComfyUI 화면에서 메뉴 → "Save (API Format)"(또는 "Export (API)")로 저장한 파일을
이 저장소의 workflows/ 폴더에 넣고, --workflow 옵션으로 그 경로를 넘겨주세요.

또한 워크플로우 안에서
  - Sam2VideoSegmentationAddPoints 노드의 ID
  - 원본 영상(세그먼트 파일)을 넣는 노드의 ID
  - 최종 결과 영상을 저장하는 노드의 ID
가 워크플로우마다 다르므로, --pose-node-id / --video-node-id 옵션으로 알려줘야 합니다.
(ComfyUI 화면에서 노드를 클릭하면 우측 정보 창이나, API 형식 JSON을 열어서 텍스트
검색으로 "Sam2VideoSegmentationAddPoints" 를 찾으면 그 노드의 ID(예: "6")를 알 수 있습니다.)

사용법 (터미널에서):
    python scripts/send_to_comfyui.py \\
        --workflow workflows/background_composite.json \\
        --pose-json output/segment_0001_points.json \\
        --video segments/segment_0001.mp4 \\
        --pose-node-id 6 \\
        --video-node-id 3 \\
        --segment-index 1

옵션:
    --workflow          ComfyUI에서 "API 형식"으로 내보낸 워크플로우 JSON 파일 경로 (필수)
    --pose-json          extract_pose_points.py가 만든 JSON 파일 경로 (필수)
    --video               처리할 원본 영상(세그먼트) 파일 경로 (선택. --video-node-id와 함께
                          지정하면 워크플로우에 이 영상 경로를 자동으로 넣어줌)
    --pose-node-id        워크플로우 안에서 Sam2VideoSegmentationAddPoints 노드의 ID (필수)
    --video-node-id       워크플로우 안에서 원본 영상을 입력받는 노드의 ID (선택)
    --video-input-key     위 노드에서 영상 경로를 받는 입력 필드 이름 (기본값: video)
    --server              ComfyUI 서버 주소 (기본값: http://127.0.0.1:8188)
    --output-dir          결과 영상을 저장할 폴더 (기본값: output/processed,
                          play_segments.py가 감시하는 폴더와 동일)
    --segment-index       결과 파일 이름에 쓸 순서 번호 (예: 1 → segment_0001.mp4)
    --timeout-seconds     ComfyUI 처리 완료를 기다리는 최대 시간(초) (기본값: 300)
    --poll-seconds        처리 상태를 확인하는 간격(초) (기본값: 2)

동작 방식:
    1) 워크플로우 JSON을 읽는다.
    2) --pose-node-id로 지정한 노드의 입력값을 pose-json 파일 내용
       (coordinates_positive / frame_index / object_index)으로 덮어쓴다.
    3) --video-node-id를 지정했다면, 그 노드의 입력값도 --video 경로로 덮어쓴다.
    4) 완성된 워크플로우를 ComfyUI 서버의 POST /prompt 로 전송한다.
    5) GET /history/{prompt_id} 를 주기적으로 확인해서 처리가 끝날 때까지 기다린다.
    6) 처리 결과로 나온 영상을 GET /view 로 내려받아 --output-dir에
       segment_XXXX.mp4 형식으로 저장한다. (다운로드는 임시 파일에 먼저 받고 나서
       마지막에 정식 이름으로 바꾸는 방식이라, play_segments.py가 "아직 다 받지도
       않은 파일"을 먼저 읽어버리는 사고를 방지한다.)
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


def find_output_file(result: dict) -> dict | None:
    """history 결과에서 저장된 영상/이미지 파일 정보를 찾는다.

    ComfyUI는 노드 종류에 따라 outputs[node_id]["gifs"], ["videos"], ["images"] 등
    다양한 키 아래에 {"filename", "subfolder", "type"} 형식으로 결과를 담아 돌려준다.
    워크플로우가 아직 정해지지 않았으므로, 특정 키에 의존하지 않고 그런 모양의
    항목을 찾아서 그중 영상 파일처럼 보이는 것을 우선한다.
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


def download_output(server: str, file_info: dict, output_path: str) -> None:
    params = {
        "filename": file_info["filename"],
        "subfolder": file_info.get("subfolder", ""),
        "type": file_info.get("type", "output"),
    }
    url = f"{server.rstrip('/')}/view?{urllib.parse.urlencode(params)}"

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    tmp_path = output_path + ".downloading"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="사람 위치 JSON을 ComfyUI 워크플로우에 넣어 전송하고 결과 영상을 받습니다."
    )
    parser.add_argument("--workflow", required=True, help="ComfyUI API 형식 워크플로우 JSON 경로")
    parser.add_argument("--pose-json", required=True, help="extract_pose_points.py가 만든 JSON 경로")
    parser.add_argument("--video", default=None, help="처리할 원본 영상(세그먼트) 파일 경로")
    parser.add_argument("--pose-node-id", required=True, help="Sam2VideoSegmentationAddPoints 노드 ID")
    parser.add_argument("--video-node-id", default=None, help="원본 영상을 입력받는 노드 ID")
    parser.add_argument("--video-input-key", default="video", help="영상 경로를 받는 입력 필드 이름")
    parser.add_argument("--server", default="http://127.0.0.1:8188", help="ComfyUI 서버 주소")
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

    output_path = os.path.join(args.output_dir, f"segment_{args.segment_index:04d}.mp4")
    download_output(args.server, file_info, output_path)

    print(f"[완료] 결과 영상을 저장했습니다: {output_path}")


if __name__ == "__main__":
    main()
