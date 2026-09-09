"""
extract_pose_points.py

영상 파일의 첫 프레임에서 사람의 위치(코 / 양쪽 어깨 / 양쪽 골반)를 MediaPipe Pose로
자동 인식하고, ComfyUI의 Sam2VideoSegmentationAddPoints 노드가 요구하는 형식의
JSON으로 저장하는 스크립트입니다.

사용법 (터미널에서):
    python scripts/extract_pose_points.py --video 내영상.mp4

옵션:
    --video       (필수) 첫 프레임을 추출할 영상 파일 경로
    --output      결과 JSON 저장 경로 (기본값: output/pose_points.json)
    --preview     검출된 점을 프레임 위에 그려서 저장할 이미지 경로
                  (기본값: output/pose_preview.jpg)
    --model       MediaPipe pose landmarker 모델(.task) 파일 경로
                  (기본값: models/pose_landmarker_lite.task, 없으면 자동 다운로드)
    --frame-index ComfyUI 노드에 넘길 frame_index 값 (기본값: 0, 첫 프레임이므로 보통 0)
    --object-index ComfyUI 노드에 넘길 object_index 값 (기본값: 0, 사람이 한 명일 때 0)

이 스크립트가 하는 일:
    1) --video로 지정한 영상 파일을 열어서 첫 번째 프레임만 읽는다.
    2) MediaPipe Pose(Tasks API, PoseLandmarker)로 사람의 33개 관절 좌표를 검출한다.
    3) 그중 코(NOSE), 왼쪽/오른쪽 어깨(SHOULDER), 왼쪽/오른쪽 골반(HIP) 5개 점을
       이미지 픽셀 좌표(x, y)로 변환한다.
    4) 5개 점을 ComfyUI Sam2VideoSegmentationAddPoints 노드의
       coordinates_positive 입력 형식({"x":.., "y":..} 객체의 리스트를 JSON 문자열로
       직렬화한 것)에 맞춰 JSON 파일로 저장한다.
    5) 눈으로 확인할 수 있도록, 검출된 점을 프레임 위에 그려서 미리보기 이미지도 저장한다.
"""

import argparse
import json
import os
import sys
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

# MediaPipe Pose 모델(공식 배포본)을 자동 다운로드할 때 사용하는 주소.
# lite 모델은 속도가 빠르고 용량이 작아서(약 5MB) 첫 프레임 1장을 처리하는
# 이 작업에는 충분합니다.
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

# MediaPipe Pose가 반환하는 33개 관절 중, 이 작업에서 필요한 5개 관절의 인덱스.
# (전체 33개 인덱스 목록은 MediaPipe 공식 문서의 "Pose landmark model" 참고)
LANDMARK_INDEXES = {
    "nose": 0,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_hip": 23,
    "right_hip": 24,
}


def ensure_model_file(model_path: str) -> str:
    """모델(.task) 파일이 없으면 공식 배포 서버에서 내려받는다."""
    if os.path.exists(model_path):
        return model_path

    os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
    print(f"[안내] Pose 모델 파일이 없어서 자동으로 다운로드합니다: {model_path}")
    print(f"       출처: {POSE_MODEL_URL}")
    try:
        urllib.request.urlretrieve(POSE_MODEL_URL, model_path)
    except Exception as exc:  # noqa: BLE001 - 사용자에게 원인을 그대로 보여주기 위함
        print(
            "[오류] 모델 파일 다운로드에 실패했습니다. 회사 네트워크가 외부 접속을 "
            "막고 있을 수 있습니다. 아래 주소를 다른 방법(다른 네트워크, 수동 다운로드 "
            "후 파일 복사 등)으로 내려받아 다음 경로에 저장한 뒤 다시 실행해 주세요:\n"
            f"  저장 경로: {os.path.abspath(model_path)}\n"
            f"  다운로드 주소: {POSE_MODEL_URL}\n"
            f"  원본 오류: {exc}"
        )
        sys.exit(1)
    print("[안내] 모델 다운로드 완료.")
    return model_path


def read_first_frame(video_path: str):
    """영상 파일에서 첫 번째 프레임을 읽어 반환한다 (OpenCV BGR 이미지)."""
    if not os.path.exists(video_path):
        print(f"[오류] 영상 파일을 찾을 수 없습니다: {video_path}")
        sys.exit(1)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[오류] 영상 파일을 열 수 없습니다(코덱 문제일 수 있음): {video_path}")
        sys.exit(1)

    ok, frame = cap.read()
    cap.release()

    if not ok or frame is None:
        print(f"[오류] 영상에서 첫 프레임을 읽지 못했습니다: {video_path}")
        sys.exit(1)

    return frame


def detect_pose_points(frame_bgr, model_path: str):
    """첫 프레임에서 5개 관절(코/양쪽 어깨/양쪽 골반) 픽셀 좌표를 검출한다."""
    height, width = frame_bgr.shape[:2]

    base_options = mp_tasks.BaseOptions(model_asset_path=model_path)
    options = mp_vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.IMAGE,
        num_poses=1,  # 현장에는 배우/출연자 1명이 있다고 가정. 여러 명이면 늘리세요.
    )

    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

    with mp_vision.PoseLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp_image)

    if not result.pose_landmarks:
        print(
            "[오류] 첫 프레임에서 사람을 찾지 못했습니다. 사람이 잘 보이는 프레임인지, "
            "영상이 너무 어둡거나 사람이 화면 밖에 있지 않은지 확인해 주세요."
        )
        sys.exit(1)

    # num_poses=1 이므로 첫 번째(유일한) 사람의 랜드마크만 사용한다.
    landmarks = result.pose_landmarks[0]

    points = {}
    for name, idx in LANDMARK_INDEXES.items():
        lm = landmarks[idx]
        points[name] = {
            # MediaPipe는 좌표를 0~1 사이 비율로 주므로, 실제 픽셀 좌표로 환산한다.
            "x": round(lm.x * width),
            "y": round(lm.y * height),
            "visibility": round(lm.visibility, 3),
        }

    return points, (width, height)


def build_comfyui_payload(points: dict, frame_index: int, object_index: int) -> dict:
    """ComfyUI Sam2VideoSegmentationAddPoints 노드에 넣을 JSON 구조를 만든다."""
    # 노드가 실제로 요구하는 형식: [{"x": .., "y": ..}, ...] 를 JSON 문자열로 만든 것.
    # (coordinates_positive 입력은 STRING 타입이며, 노드 내부에서
    #  json.loads(...) 로 다시 파싱한 뒤 [(x, y), ...] 좌표 목록으로 사용합니다.)
    coordinate_list = [
        {"x": p["x"], "y": p["y"]} for p in points.values()
    ]
    coordinates_positive_str = json.dumps(coordinate_list)

    return {
        # --- 이 아래 3개 필드를 ComfyUI 노드 입력값에 그대로 붙여넣으면 됩니다 ---
        "coordinates_positive": coordinates_positive_str,
        "frame_index": frame_index,
        "object_index": object_index,
        # --- 여기부터는 사람이 확인하기 위한 참고용 정보(노드 입력값 아님) ---
        "_debug_points": points,
    }


def draw_preview(frame_bgr, points: dict, preview_path: str):
    """검출된 점을 프레임 위에 그려서 눈으로 확인할 수 있는 이미지로 저장한다."""
    preview = frame_bgr.copy()
    for name, p in points.items():
        cv2.circle(preview, (p["x"], p["y"]), 6, (0, 255, 0), thickness=-1)
        cv2.putText(
            preview,
            name,
            (p["x"] + 8, p["y"] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
    os.makedirs(os.path.dirname(preview_path) or ".", exist_ok=True)
    cv2.imwrite(preview_path, preview)


def parse_args():
    parser = argparse.ArgumentParser(
        description="영상 첫 프레임에서 사람 위치(코/어깨/골반)를 찾아 "
        "ComfyUI Sam2VideoSegmentationAddPoints용 JSON으로 출력합니다."
    )
    parser.add_argument("--video", required=True, help="입력 영상 파일 경로")
    parser.add_argument(
        "--output",
        default=os.path.join("output", "pose_points.json"),
        help="결과 JSON 저장 경로 (기본값: output/pose_points.json)",
    )
    parser.add_argument(
        "--preview",
        default=os.path.join("output", "pose_preview.jpg"),
        help="검출 결과 미리보기 이미지 저장 경로 (기본값: output/pose_preview.jpg)",
    )
    parser.add_argument(
        "--model",
        default=os.path.join("models", "pose_landmarker_lite.task"),
        help="MediaPipe pose landmarker 모델 파일 경로 (없으면 자동 다운로드)",
    )
    parser.add_argument(
        "--frame-index",
        type=int,
        default=0,
        help="ComfyUI 노드에 넘길 frame_index (기본값: 0)",
    )
    parser.add_argument(
        "--object-index",
        type=int,
        default=0,
        help="ComfyUI 노드에 넘길 object_index (기본값: 0)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    model_path = ensure_model_file(args.model)
    frame = read_first_frame(args.video)
    points, (width, height) = detect_pose_points(frame, model_path)

    payload = build_comfyui_payload(points, args.frame_index, args.object_index)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    draw_preview(frame, points, args.preview)

    print("\n[완료] 사람 위치 검출 결과")
    print(f"  - 프레임 크기: {width}x{height}")
    for name, p in points.items():
        print(f"  - {name}: x={p['x']}, y={p['y']} (visibility={p['visibility']})")
    print(f"\n[저장됨] ComfyUI용 JSON: {args.output}")
    print(f"[저장됨] 확인용 미리보기 이미지: {args.preview}")
    print("\nComfyUI Sam2VideoSegmentationAddPoints 노드에 넣을 값:")
    print(f"  coordinates_positive = {payload['coordinates_positive']}")
    print(f"  frame_index = {payload['frame_index']}")
    print(f"  object_index = {payload['object_index']}")


if __name__ == "__main__":
    main()
