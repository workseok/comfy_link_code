"""
capture_segments.py

웹캠(또는 영상 파일)에서 영상을 받아, 지정한 초(기본 3초) 단위로 끊어서
segments 폴더에 순서 번호를 붙여 저장하는 스크립트입니다.

사용법 (터미널에서):
    python scripts/capture_segments.py

기본값으로 실행하면 0번 카메라(보통 컴퓨터에 연결된 첫 번째 웹캠)에서 영상을 받아
segments/ 폴더에 segment_0001.mp4, segment_0002.mp4 ... 순서로 3초씩 저장합니다.
중지하려면 터미널에서 Ctrl+C 를 누르면 됩니다. (현재 녹화 중이던 조각은 끊긴 지점까지
정상적으로 저장됩니다.)

옵션:
    --source           카메라 번호(0, 1, ...) 또는 영상 파일 경로 (기본값: 0)
    --output-dir       세그먼트를 저장할 폴더 (기본값: segments)
    --segment-seconds  한 조각의 길이(초) (기본값: 3)
    --fps              저장할 영상의 초당 프레임 수. 지정하지 않으면 카메라가
                        보고하는 값을 사용하고, 그마저도 알 수 없으면 30으로 처리합니다.
    --width, --height  카메라 해상도 지정 (지정하지 않으면 카메라 기본값 사용)
    --num-segments     지정한 개수만큼 세그먼트를 저장하고 자동 종료
                        (지정하지 않으면 Ctrl+C 로 직접 멈출 때까지 계속 녹화)

동작 방식:
    - 카메라에서 프레임을 계속 읽으면서, 현재 조각을 녹화하기 시작한 시점부터
      벽시계 기준으로 --segment-seconds 초가 지나면 파일을 닫고 다음 번호의
      새 파일을 시작합니다. (프레임 개수가 아니라 실제 경과 시간 기준이라,
      카메라가 보고하는 FPS 값이 정확하지 않아도 각 조각의 길이가 크게
      틀어지지 않습니다.)
    - 다음 단계(사람 위치 인식 → ComfyUI 배경 합성)에서는 여기서 만들어진
      segment_XXXX.mp4 파일을 하나씩 순서대로 extract_pose_points.py에
      넘기면 됩니다.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import cv2


def parse_source(value: str):
    """--source 값을 카메라 번호(int)나 파일 경로(str)로 해석한다."""
    try:
        return int(value)
    except ValueError:
        return value


def open_capture(source, width: int | None, height: int | None) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(source)

    if width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    if not cap.isOpened():
        if isinstance(source, int):
            print(
                f"[오류] {source}번 카메라를 열 수 없습니다. 카메라가 연결되어 있는지, "
                "다른 프로그램(화상회의 앱 등)이 이미 카메라를 쓰고 있지는 않은지 "
                "확인해 주세요. 카메라가 여러 대라면 --source 1, --source 2 처럼 "
                "다른 번호도 시도해 보세요."
            )
        else:
            print(f"[오류] 영상 파일을 열 수 없습니다: {source}")
        sys.exit(1)

    return cap


def resolve_fps(cap: cv2.VideoCapture, fps_arg: float | None) -> float:
    if fps_arg:
        return fps_arg

    reported = cap.get(cv2.CAP_PROP_FPS)
    # 일부 웹캠/드라이버는 FPS를 0이나 비정상적인 값으로 보고하기도 하므로
    # 상식적인 범위(1~120)를 벗어나면 기본값 30을 사용한다.
    if reported and 1 <= reported <= 120:
        return reported

    print("[안내] 카메라가 FPS 정보를 정확히 알려주지 않아 기본값(30fps)으로 저장합니다.")
    return 30.0


def make_writer(output_dir: str, index: int, fps: float, frame_size: tuple[int, int]):
    filename = os.path.join(output_dir, f"segment_{index:04d}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(filename, fourcc, fps, frame_size)
    return writer, filename


def parse_args():
    parser = argparse.ArgumentParser(
        description="웹캠(또는 영상 파일)을 지정한 초 단위로 끊어서 순서대로 저장합니다."
    )
    parser.add_argument(
        "--source",
        default="0",
        help="카메라 번호(0, 1, ...) 또는 영상 파일 경로 (기본값: 0)",
    )
    parser.add_argument(
        "--output-dir",
        default="segments",
        help="세그먼트를 저장할 폴더 (기본값: segments)",
    )
    parser.add_argument(
        "--segment-seconds",
        type=float,
        default=3.0,
        help="한 조각의 길이(초) (기본값: 3)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="저장할 영상의 초당 프레임 수 (기본값: 카메라가 보고하는 값, 없으면 30)",
    )
    parser.add_argument("--width", type=int, default=None, help="카메라 해상도(가로)")
    parser.add_argument("--height", type=int, default=None, help="카메라 해상도(세로)")
    parser.add_argument(
        "--num-segments",
        type=int,
        default=None,
        help="지정한 개수만큼만 저장하고 자동 종료 (기본값: 계속 녹화, Ctrl+C로 종료)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    source = parse_source(args.source)

    os.makedirs(args.output_dir, exist_ok=True)

    cap = open_capture(source, args.width, args.height)
    fps = resolve_fps(cap, args.fps)

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if frame_width <= 0 or frame_height <= 0:
        print("[오류] 카메라에서 해상도를 읽어올 수 없습니다.")
        cap.release()
        sys.exit(1)

    print(
        f"[시작] 소스: {source} / 해상도: {frame_width}x{frame_height} / "
        f"{fps:.1f}fps / {args.segment_seconds}초 단위로 저장 → '{args.output_dir}/' "
        "(중지하려면 Ctrl+C)"
    )

    segment_index = 1
    saved_segments = 0
    writer = None
    segment_start_time = None
    frames_in_segment = 0
    frame_interval = 1.0 / fps
    last_read_time = None

    try:
        while True:
            # 실제 웹캠은 cap.read()가 다음 프레임이 준비될 때까지 자동으로 기다려주지만,
            # 영상 파일을 소스로 쓰면(테스트용) 파일을 훨씬 빠르게 읽어버려서 "3초 단위"
            # 분할을 실제 촬영처럼 검증할 수 없다. 그래서 목표 fps 간격보다 빨리 읽었으면
            # 그 차이만큼 대기해서, 파일 소스도 실제 카메라처럼 시간이 흐르게 만든다.
            if last_read_time is not None:
                remaining = frame_interval - (time.time() - last_read_time)
                if remaining > 0:
                    time.sleep(remaining)

            ok, frame = cap.read()
            last_read_time = time.time()
            if not ok or frame is None:
                # 영상 파일을 소스로 쓴 경우 여기서 자연스럽게 끝난다(파일 재생 완료).
                # 실제 웹캠이라면 카메라 연결이 끊긴 것이므로 오류로 안내한다.
                if isinstance(source, int):
                    print("[오류] 카메라로부터 더 이상 프레임을 받을 수 없습니다. 연결을 확인해 주세요.")
                break

            if writer is None:
                writer, filename = make_writer(
                    args.output_dir, segment_index, fps, (frame_width, frame_height)
                )
                segment_start_time = time.time()
                frames_in_segment = 0

            writer.write(frame)
            frames_in_segment += 1

            elapsed = time.time() - segment_start_time
            if elapsed >= args.segment_seconds:
                writer.release()
                print(
                    f"[저장됨] {filename} "
                    f"(약 {elapsed:.1f}초, {frames_in_segment}프레임)"
                )
                writer = None
                saved_segments += 1
                segment_index += 1

                if args.num_segments and saved_segments >= args.num_segments:
                    break

    except KeyboardInterrupt:
        print("\n[안내] 사용자가 중지했습니다 (Ctrl+C).")

    finally:
        # 녹화 도중 중단되었다면, 마지막으로 진행 중이던 조각도 끊긴 지점까지 저장한다.
        if writer is not None:
            writer.release()
            elapsed = time.time() - segment_start_time
            print(
                f"[저장됨] {filename} "
                f"(약 {elapsed:.1f}초, {frames_in_segment}프레임 — {args.segment_seconds}초가 "
                "채워지기 전에 종료되어 이보다 짧게 저장되었습니다)"
            )
            saved_segments += 1
        cap.release()

    print(f"\n[완료] 총 {saved_segments}개 조각을 '{args.output_dir}/' 폴더에 저장했습니다.")


if __name__ == "__main__":
    main()
