"""
main.py

세그먼트 영상 하나를 ComfyUI(로컬 또는 클라우드)로 보내 배경 합성을 요청하는
진입점입니다. 어느 서버로 보낼지는 --backend로 고릅니다.

    --backend cloud (기본값)  → comfyui_client.cloud_client.send_frame() 사용
    --backend local           → comfyui_client.local_client.send_frame() 사용
                                (아직 미구현 — 다음 단계에서 작성 예정)

두 백엔드 모듈은 같은 이름의 send_frame(frame, prompt_point, ...) 함수를
제공하므로, 이 파일의 호출부 코드는 어느 backend를 고르든 동일합니다. 기본값이
cloud이므로, 지금까지처럼 아무 --backend 옵션 없이 실행하면 기존 동작
(comfyui_client/cloud_client.py, 예전 scripts/send_to_comfyui.py)과 똑같이
ComfyUI Cloud로 전송됩니다.

사용법 (클라우드, 기존과 동일한 동작):
    export COMFY_API_KEY="sk-..."
    python main.py \\
        --workflow workflows/background_composite.json \\
        --frame segments/segment_0001.mp4 \\
        --prompt-point output/segment_0001_points.json \\
        --pose-node-id 11 \\
        --video-node-id 1 \\
        --frame-load-cap 30 \\
        --repeat-node-id 6 \\
        --segment-index 1 \\
        --dry-run

사용법 (로컬 ComfyUI — local_client.py 완성 후):
    python main.py --backend local \\
        --workflow workflows/background_composite.json \\
        --frame segments/segment_0001.mp4 \\
        --prompt-point output/segment_0001_points.json \\
        --pose-node-id 11 --video-node-id 1 --segment-index 1

옵션 대부분은 예전 send_to_comfyui.py(현재 comfyui_client/cloud_client.py)의
동명 CLI 옵션과 의미가 같습니다. --server의 기본값은 --backend에 따라
자동으로 정해집니다 (cloud → https://cloud.comfy.org, local →
http://127.0.0.1:8188). 직접 지정하면 그 값을 그대로 씁니다.
"""

from __future__ import annotations

import argparse
import sys

DEFAULT_SERVER = {
    "cloud": "https://cloud.comfy.org",
    "local": "http://127.0.0.1:8188",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="세그먼트 영상을 ComfyUI(로컬 또는 클라우드)로 보내 배경 합성을 요청합니다."
    )
    parser.add_argument(
        "--backend",
        choices=["cloud", "local"],
        default="cloud",
        help="어느 ComfyUI 서버로 보낼지 (기본값: cloud — 기존 동작과 동일)",
    )
    parser.add_argument("--workflow", required=True, help="ComfyUI API 형식 워크플로우 JSON 경로")
    parser.add_argument(
        "--frame", required=True, help="처리할 세그먼트 영상 파일 경로 (예: segments/segment_0001.mp4)"
    )
    parser.add_argument(
        "--prompt-point",
        required=True,
        help="extract_pose_points.py가 만든 pose JSON 파일 경로",
    )
    parser.add_argument("--pose-node-id", required=True, help="Sam2VideoSegmentationAddPoints 노드 ID")
    parser.add_argument("--video-node-id", default=None, help="원본 영상을 입력받는 노드 ID")
    parser.add_argument("--video-input-key", default="video")
    parser.add_argument("--frame-load-cap", type=int, default=None)
    parser.add_argument("--repeat-node-id", default=None)
    parser.add_argument("--repeat-amount-key", default="amount")
    parser.add_argument(
        "--server",
        default=None,
        help="서버 주소 (생략하면 --backend에 맞는 기본값 사용)",
    )
    parser.add_argument("--api-key-env", default="COMFY_API_KEY", help="(cloud 전용) API 키 환경변수 이름")
    parser.add_argument("--comfy-org-api-key-env", default=None)
    parser.add_argument("--output-dir", default="output/processed")
    parser.add_argument("--segment-index", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dry-run-output", default=None)
    return parser.parse_args()


def main():
    args = parse_args()

    if args.backend == "cloud":
        from comfyui_client import cloud_client as client
    else:
        from comfyui_client import local_client as client

    server = args.server or DEFAULT_SERVER[args.backend]

    print(f"[안내] backend = {args.backend} / server = {server}")

    try:
        result_path = client.send_frame(
            args.frame,
            args.prompt_point,
            workflow_path=args.workflow,
            pose_node_id=args.pose_node_id,
            video_node_id=args.video_node_id,
            video_input_key=args.video_input_key,
            frame_load_cap=args.frame_load_cap,
            repeat_node_id=args.repeat_node_id,
            repeat_amount_key=args.repeat_amount_key,
            server=server,
            api_key_env=args.api_key_env,
            comfy_org_api_key_env=args.comfy_org_api_key_env,
            output_dir=args.output_dir,
            segment_index=args.segment_index,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
            dry_run=args.dry_run,
            dry_run_output=args.dry_run_output,
        )
    except NotImplementedError as exc:
        print(f"[오류] {exc}")
        sys.exit(1)

    print(f"[main.py] 결과: {result_path}")


if __name__ == "__main__":
    main()
