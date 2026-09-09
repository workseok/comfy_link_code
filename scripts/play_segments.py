"""
play_segments.py

ComfyUI가 배경 합성을 끝낸 영상 조각들을, 이름에 붙은 순서 번호(0001, 0002, ...)
순서대로 이어서 하나의 화면 창에 재생합니다. 몇 초 지연은 괜찮다는 전제이므로,
다음 조각이 아직 처리되지 않은 상태라면 "처리 대기 중" 화면을 보여주며 기다렸다가,
파일이 생기는 즉시 이어서 재생합니다.

사용법 (터미널에서):
    python scripts/play_segments.py

기본값으로 실행하면 output/processed/ 폴더를 감시하면서
segment_0001.mp4, segment_0002.mp4 ... 순서로 화면에 재생합니다.
재생 중인 창에서 아무 키나 누르면 다음 조각으로 건너뛰고, `q`를 누르면 종료합니다.

옵션:
    --input-dir     재생할 영상이 쌓이는 폴더 (기본값: output/processed)
    --pattern       파일 이름 패턴, {index}는 4자리 숫자로 치환됨
                     (기본값: segment_{index}.mp4 → segment_0001.mp4 형태)
    --start-index   재생을 시작할 순서 번호 (기본값: 1)
    --poll-seconds  다음 조각이 아직 없을 때, 몇 초 간격으로 다시 확인할지 (기본값: 1.0)
    --window-name   화면 창 제목 (기본값: "AI 배경 합성 결과")
    --once          지정한 순서 번호부터 시작해서, 파일이 하나라도 없으면 기다리지 않고
                     바로 종료 (전체 파이프라인을 자동 테스트할 때 사용)

전체 파이프라인에서 이 스크립트의 위치:
    capture_segments.py (카메라→3초 조각)
      → extract_pose_points.py (조각 첫 프레임→사람 위치 JSON)
      → send_to_comfyui.py (JSON+워크플로우→ComfyUI 배경 합성→output/processed/에 저장)
      → play_segments.py (여기, output/processed/ 조각을 순서대로 화면 재생)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import cv2


def parse_args():
    parser = argparse.ArgumentParser(
        description="배경 합성이 끝난 영상 조각을 순서대로 이어서 화면에 재생합니다."
    )
    parser.add_argument(
        "--input-dir",
        default=os.path.join("output", "processed"),
        help="재생할 영상이 쌓이는 폴더 (기본값: output/processed)",
    )
    parser.add_argument(
        "--pattern",
        default="segment_{index}.mp4",
        help="파일 이름 패턴, {index}는 4자리 숫자로 치환됩니다 (기본값: segment_{index}.mp4)",
    )
    parser.add_argument(
        "--start-index", type=int, default=1, help="재생을 시작할 순서 번호 (기본값: 1)"
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        help="다음 조각이 아직 없을 때 재확인 간격(초) (기본값: 1.0)",
    )
    parser.add_argument(
        "--window-name", default="AI 배경 합성 결과", help="화면 창 제목"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="다음 조각이 없으면 기다리지 않고 바로 종료 (자동 테스트용)",
    )
    return parser.parse_args()


def make_waiting_frame(size, index: int, message: str):
    """다음 조각을 기다리는 동안 화면에 보여줄 안내 프레임을 만든다."""
    import numpy as np

    width, height = size
    frame = np.zeros((height, width, 3), dtype="uint8")
    cv2.putText(
        frame,
        f"{index:04d}번 조각 처리 대기 중...",
        (max(20, width // 10), height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        min(width, height) / 500,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        message,
        (max(20, width // 10), height // 2 + 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        min(width, height) / 900,
        (180, 180, 180),
        1,
        cv2.LINE_AA,
    )
    return frame


def is_file_ready(path: str, settle_seconds: float = 0.3) -> bool:
    """파일이 '다 쓰여진' 상태인지 확인한다.

    ComfyUI(또는 다른 프로세스)가 이 파일을 쓰고 있는 도중에 존재만 확인하고 바로
    열면, 아직 mp4 컨테이너가 마무리되지 않아 재생이 깨질 수 있다(실제로 이 스크립트를
    검증하는 과정에서 이 문제가 재현되었다). 그래서 파일 크기가 짧은 간격을 두고
    두 번 연속 똑같을 때만 "다 쓰였다"고 판단한다.
    """
    try:
        size1 = os.path.getsize(path)
        time.sleep(settle_seconds)
        size2 = os.path.getsize(path)
    except OSError:
        return False
    return size1 == size2 and size1 > 0


def wait_for_file(path: str, poll_seconds: float, window_name: str, index: int, once: bool) -> bool:
    """파일이 생기고, 다 쓰여질 때까지 대기 화면을 보여주며 기다린다.

    종료 키가 눌리면 False를 반환한다.
    """
    waiting_size = (960, 540)
    printed = False
    while not (os.path.exists(path) and is_file_ready(path)):
        if once:
            print(f"[안내] {path} 파일이 아직 준비되지 않아서(--once 옵션) 종료합니다.")
            return False

        if not printed:
            print(f"[대기] {os.path.basename(path)} 처리 완료를 기다리는 중...")
            printed = True

        frame = make_waiting_frame(
            waiting_size, index, "ComfyUI 처리가 끝나면 자동으로 이어집니다 ('q'로 종료)"
        )
        cv2.imshow(window_name, frame)
        key = cv2.waitKey(int(poll_seconds * 1000)) & 0xFF
        if key == ord("q"):
            return False
    return True


def play_video(path: str, window_name: str) -> bool:
    """영상 하나를 처음부터 끝까지 재생한다. 'q'가 눌리면 False를 반환해 전체 종료를 알린다."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"[오류] 영상을 열 수 없습니다: {path}")
        return True  # 이 조각만 건너뛰고 다음 조각으로 진행

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    delay_ms = max(1, int(1000 / fps))

    print(f"[재생] {path}")
    keep_going = True
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        cv2.imshow(window_name, frame)
        key = cv2.waitKey(delay_ms) & 0xFF
        if key == ord("q"):
            keep_going = False
            break
        if key != 255 and key != -1:
            # 'q'가 아닌 다른 키: 현재 조각만 건너뛰고 다음 조각으로 넘어간다.
            break

    cap.release()
    return keep_going


def main():
    args = parse_args()
    index = args.start_index

    print(
        f"[시작] '{args.input_dir}/' 폴더를 감시하며 {args.start_index:04d}번부터 순서대로 재생합니다. "
        "('q'로 종료, 다른 키로 다음 조각으로 건너뛰기)"
    )

    # 창 크기를 영상 해상도에 맞게 매번 자동으로 조절하도록 WINDOW_NORMAL로 미리 만들어둔다.
    # (기본 WINDOW_AUTOSIZE로 두면 첫 프레임이 그려지기 전까지 창이 비정상적으로
    # 작게 잡혀서 화면 대부분이 빈 채로 보이는 경우가 있었다.)
    cv2.namedWindow(args.window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(args.window_name, 960, 540)

    try:
        while True:
            filename = args.pattern.format(index=f"{index:04d}")
            path = os.path.join(args.input_dir, filename)

            if not wait_for_file(path, args.poll_seconds, args.window_name, index, args.once):
                break

            if not play_video(path, args.window_name):
                break

            index += 1
    finally:
        cv2.destroyAllWindows()

    print("[종료] 재생을 마쳤습니다.")


if __name__ == "__main__":
    main()
