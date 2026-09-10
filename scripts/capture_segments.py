"""
capture_segments.py

웹캠, 또는 웹캠처럼 인식되는 HDMI 캡처카드(예: FX9 등 카메라를 HDMI로 연결한 캡처카드)
에서 영상을 받아, 지정한 초(기본 3초) 단위로 끊어서 segments 폴더에 순서 번호를 붙여
저장하는 스크립트입니다.

사용법 (터미널에서):
    python scripts/capture_segments.py

--source를 지정하지 않고 실행하면, 컴퓨터에 연결된 영상 장치 목록을 보여주고
번호를 입력해서 고를 수 있습니다. 장치를 선택하면 그 장치가 실제로 어떤
해상도/FPS로 들어오는지 확인해서 화면에 출력한 뒤 녹화를 시작합니다.
중지하려면 터미널에서 Ctrl+C 를 누르면 됩니다. (현재 녹화 중이던 조각은 끊긴 지점까지
정상적으로 저장됩니다.)

옵션:
    --source           카메라/캡처카드 번호(0, 1, ...) 또는 영상 파일 경로.
                        지정하지 않으면 장치 목록을 보여주고 직접 고르게 합니다.
    --list-devices      연결된 영상 장치 목록만 보여주고 종료합니다.
    --output-dir        세그먼트를 저장할 폴더 (기본값: segments)
    --segment-seconds   한 조각의 길이(초) (기본값: 3)
    --fps               저장할 영상의 초당 프레임 수. 지정하지 않으면 카메라가
                        보고하는 값을 사용하고, 그마저도 알 수 없으면 30으로 처리합니다.
    --width, --height   카메라/캡처카드에 요청할 해상도 (지정하지 않으면 장치 기본값 사용).
                        캡처카드가 이 값을 그대로 받아주지 않고 다운컨버전할 수 있으므로,
                        실제로 적용된 값을 다시 확인해서 출력합니다.
    --num-segments      지정한 개수만큼 세그먼트를 저장하고 자동 종료
                        (지정하지 않으면 Ctrl+C 로 직접 멈출 때까지 계속 녹화)
    --no-probe          장치가 실제로 지원하는 전체 해상도/FPS 목록 조회(ffmpeg/v4l2-ctl
                        이용)를 건너뜁니다. 기본적으로는 카메라 장치를 선택하면 자동으로
                        조회해서 보여줍니다.

동작 방식:
    - 카메라에서 프레임을 계속 읽으면서, 현재 조각을 녹화하기 시작한 시점부터
      벽시계 기준으로 --segment-seconds 초가 지나면 파일을 닫고 다음 번호의
      새 파일을 시작합니다. (프레임 개수가 아니라 실제 경과 시간 기준이라,
      카메라가 보고하는 FPS 값이 정확하지 않아도 각 조각의 길이가 크게
      틀어지지 않습니다.)
    - 다음 단계(사람 위치 인식 → ComfyUI 배경 합성)에서는 여기서 만들어진
      segment_XXXX.mp4 파일을 하나씩 순서대로 extract_pose_points.py에
      넘기면 됩니다.

★ 캡처카드 관련 중요 안내 ★
OpenCV(이 스크립트가 쓰는 라이브러리)로 확인할 수 있는 것은 해상도와 FPS까지입니다.
10bit 여부나 4:2:2/4:2:0 같은 색상 서브샘플링까지는 OpenCV만으로 확정하기 어렵습니다
(운영체제의 표준 카메라 인터페이스(DirectShow 등)를 거치면서 캡처카드 드라이버가
내부적으로 8bit로 변환해서 넘겨주는 경우가 흔합니다). 그래서 ffmpeg가 설치되어
있으면, 장치가 스스로 보고하는 픽셀 포맷 문자열까지 포함한 전체 지원 모드 목록을
추가로 보여줍니다 (--no-probe로 끌 수 있음). 정확한 10bit 4:2:2 캡처가 꼭
필요하다면, 캡처카드 제조사가 제공하는 전용 캡처 소프트웨어나 ffmpeg를 직접
사용하는 방법도 함께 고려해 보시길 권합니다.
"""

from __future__ import annotations

import argparse
import glob
import os
import platform
import re
import shutil
import subprocess
import sys
import time

import cv2

# ---------------------------------------------------------------------------
# 영상 장치 목록 조회
# ---------------------------------------------------------------------------


def parse_v4l2ctl_list_devices(text: str) -> list[dict]:
    """`v4l2-ctl --list-devices` 출력(Linux)을 파싱한다.

    출력 형식 예시:
        HD Webcam (usb-0000:00:14.0-1):
        \t/dev/video0
        \t/dev/video1

        다른 장치:
        \t/dev/video2
    """
    devices = []
    current_name = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            # 헤더 줄은 항상 맨 끝이 ':'로 끝나는 형식이다. 장치 이름 자체에 콜론이
            # 들어있는 경우(예: USB 버스 주소 "usb-0000:00:14.0-1")가 있으므로 첫
            # 번째 ':'가 아니라 마지막 ':' 기준으로 잘라야 이름이 안 잘린다.
            current_name = line.rstrip(":").strip() if line.rstrip().endswith(":") else line.strip()
            continue
        path = line.strip()
        match = re.search(r"video(\d+)$", path)
        if match and current_name:
            devices.append({"index": int(match.group(1)), "name": current_name, "path": path})
    return devices


def parse_dshow_device_list(text: str) -> list[dict]:
    """`ffmpeg -f dshow -list_devices true -i dummy` 출력(Windows)을 파싱한다.

    ffmpeg는 이 목록을 stderr에 출력하며, 형식은 대략 다음과 같다:
        ...DirectShow video devices (some may be both video and audio devices)
        ...  "USB Capture HDMI 4K+"
        ...     Alternative name "@device_pnp_\\?\\usb#vid_...."
        ...  "Integrated Camera"
        ...DirectShow audio devices
        ...
    """
    devices = []
    in_video_section = False
    index = 0
    for line in text.splitlines():
        if "DirectShow video devices" in line:
            in_video_section = True
            continue
        if "DirectShow audio devices" in line:
            in_video_section = False
            continue
        if not in_video_section:
            continue
        if "Alternative name" in line:
            continue
        match = re.search(r'"([^"]+)"', line)
        if match:
            devices.append({"index": index, "name": match.group(1)})
            index += 1
    return devices


def parse_avfoundation_device_list(text: str) -> list[dict]:
    """`ffmpeg -f avfoundation -list_devices true -i ""` 출력(macOS)을 파싱한다.

    형식 예시:
        ...AVFoundation video devices:
        ...[0] FaceTime HD Camera
        ...[1] USB Capture HDMI+
        ...AVFoundation audio devices:
        ...[0] MacBook Pro Microphone
    """
    devices = []
    in_video_section = False
    for line in text.splitlines():
        if "AVFoundation video devices" in line:
            in_video_section = True
            continue
        if "AVFoundation audio devices" in line:
            in_video_section = False
            continue
        if not in_video_section:
            continue
        match = re.search(r"\[(\d+)\]\s+(.*)", line)
        if match:
            devices.append({"index": int(match.group(1)), "name": match.group(2).strip()})
    return devices


def _list_devices_opencv_fallback(max_index: int = 10) -> list[dict]:
    """ffmpeg/v4l2-ctl이 없을 때 쓰는 최후의 수단.

    장치 이름은 알 수 없지만, 인덱스 0부터 순서대로 열어봐서 실제로 열리는
    번호만 골라 보여준다.
    """
    devices = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            devices.append({"index": i, "name": f"(이름 확인 불가 — 열었을 때 해상도 {w}x{h})"})
        cap.release()
    return devices


def list_video_devices() -> tuple[list[dict], str]:
    """현재 컴퓨터에 연결된 영상 장치 목록을 조회한다.

    반환값: (장치 목록, 조회에 사용한 방법을 설명하는 문자열)
    """
    system = platform.system()

    if system == "Linux":
        if shutil.which("v4l2-ctl"):
            try:
                result = subprocess.run(
                    ["v4l2-ctl", "--list-devices"], capture_output=True, text=True, timeout=10
                )
                devices = parse_v4l2ctl_list_devices(result.stdout)
                if devices:
                    return devices, "v4l2-ctl --list-devices"
            except (subprocess.SubprocessError, OSError):
                pass
        # v4l2-ctl이 없거나 실패했다면 /dev/video* 를 직접 나열한다 (이름 정보는 없음).
        devices = []
        for path in sorted(glob.glob("/dev/video*")):
            match = re.search(r"video(\d+)$", path)
            if match:
                devices.append({"index": int(match.group(1)), "name": f"(이름 확인 불가, {path})"})
        if devices:
            return devices, "/dev/video* 직접 확인"
        return _list_devices_opencv_fallback(), "OpenCV로 순서대로 열어보기 (장치 이름 확인 불가)"

    if system == "Windows":
        if shutil.which("ffmpeg"):
            try:
                result = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                devices = parse_dshow_device_list(result.stderr)
                if devices:
                    return devices, "ffmpeg -f dshow -list_devices"
            except (subprocess.SubprocessError, OSError):
                pass
        return (
            _list_devices_opencv_fallback(),
            "OpenCV로 순서대로 열어보기 (장치 이름 확인 불가 — ffmpeg를 설치하면 이름까지 보입니다)",
        )

    if system == "Darwin":
        if shutil.which("ffmpeg"):
            try:
                result = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "avfoundation", "-i", ""],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                devices = parse_avfoundation_device_list(result.stderr)
                if devices:
                    return devices, "ffmpeg -f avfoundation -list_devices"
            except (subprocess.SubprocessError, OSError):
                pass
        return (
            _list_devices_opencv_fallback(),
            "OpenCV로 순서대로 열어보기 (장치 이름 확인 불가 — ffmpeg를 설치하면 이름까지 보입니다)",
        )

    return _list_devices_opencv_fallback(), "OpenCV로 순서대로 열어보기"


def print_device_list(devices: list[dict], method: str) -> None:
    print(f"[안내] 영상 장치 목록 ({method}):")
    if not devices:
        print("  (연결된 영상 장치를 찾지 못했습니다)")
        return
    for device in devices:
        print(f"  [{device['index']}] {device['name']}")


def choose_device_interactively(devices: list[dict]) -> int:
    """(목록은 이미 출력되었다고 가정하고) 사용자에게 장치 번호를 입력받는다."""
    if not devices:
        print("[오류] 선택할 수 있는 영상 장치가 없습니다. 캡처카드/카메라 연결을 확인해 주세요.")
        sys.exit(1)

    valid_indexes = {d["index"] for d in devices}
    while True:
        try:
            raw = input(f"사용할 장치 번호를 입력하세요 {sorted(valid_indexes)}: ").strip()
        except EOFError:
            print("[오류] 입력을 받을 수 없는 환경입니다. --source 옵션으로 장치 번호를 직접 지정해 주세요.")
            sys.exit(1)
        if not raw.isdigit() or int(raw) not in valid_indexes:
            print("[안내] 목록에 있는 번호를 다시 입력해 주세요.")
            continue
        return int(raw)


# ---------------------------------------------------------------------------
# 장치가 실제로 지원하는 해상도/FPS/픽셀 포맷 조회 ("probe")
# ---------------------------------------------------------------------------


def probe_device_modes(system: str, source_index: int, device_name: str | None) -> str | None:
    """장치가 실제로 지원하는 모드(해상도/FPS/픽셀 포맷) 전체 목록을 조회한다.

    OpenCV는 "지금 열려있는 상태"의 값만 알려주기 때문에, 캡처카드가 정말로 어떤
    모드까지 지원하는지(예: 10bit 4:2:2 지원 여부)를 확인하려면 v4l2-ctl(Linux)이나
    ffmpeg(Windows/macOS) 같은 별도 도구가 필요하다. 이 도구들이 설치되어 있지
    않으면 None을 반환한다 (오류로 취급하지 않고 조용히 건너뜀).
    """
    if system == "Linux" and shutil.which("v4l2-ctl"):
        device_path = f"/dev/video{source_index}"
        try:
            result = subprocess.run(
                ["v4l2-ctl", f"--device={device_path}", "--list-formats-ext"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.stdout.strip() or None
        except (subprocess.SubprocessError, OSError):
            return None

    if system == "Windows" and shutil.which("ffmpeg") and device_name:
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-list_options", "true",
                    "-f", "dshow", "-i", f"video={device_name}",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.stderr.strip() or None
        except (subprocess.SubprocessError, OSError):
            return None

    # macOS(avfoundation)는 ffmpeg가 장치별 지원 모드를 안정적으로 나열해주는 표준
    # 방법이 마땅치 않아 여기서는 건너뛴다. 필요하면 ffmpeg -f avfoundation
    # 명령으로 직접 캡처를 시도하며 확인하는 방법을 권장한다.
    return None


def summarize_probe_output(system: str, probe_text: str) -> None:
    """probe 결과 원문을 그대로 보여주면서, 10bit/4:2:2 관련 줄이 있으면 강조한다."""
    print("[안내] 이 장치가 실제로 지원한다고 보고하는 전체 모드 목록:")
    for line in probe_text.splitlines():
        print(f"    {line}")

    lowered = probe_text.lower()
    hints = []
    if "10" in lowered and ("bit" in lowered or "p010" in lowered or "bayer" in lowered):
        hints.append("10bit로 보이는 모드가 목록에 있습니다.")
    if "422" in lowered or "4:2:2" in lowered or "yuyv" in lowered or "uyvy" in lowered:
        hints.append("4:2:2 계열로 보이는 픽셀 포맷이 목록에 있습니다 (YUYV/UYVY 등).")
    if hints:
        print("[힌트] " + " ".join(hints))
    print(
        "[주의] 위 목록은 장치가 '지원한다고 보고'하는 모드입니다. 실제로 지금 이 "
        "스크립트(OpenCV)가 여는 모드는 이보다 낮은 사양(다운컨버전)일 수 있으니, "
        "아래 '실제 적용된 값'과 비교해서 확인하세요."
    )


# ---------------------------------------------------------------------------
# 캡처 관련 (기존 로직 + 실제 해상도/FPS 재확인)
# ---------------------------------------------------------------------------


def parse_source(value: str):
    """--source 값을 카메라 번호(int)나 파일 경로(str)로 해석한다."""
    try:
        return int(value)
    except ValueError:
        return value


def decode_fourcc(value: float) -> str:
    code = int(value)
    chars = "".join(chr((code >> (8 * i)) & 0xFF) for i in range(4))
    return chars.strip() or "(알 수 없음)"


def open_capture(source, width: int | None, height: int | None) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(source)

    requested_width, requested_height = width, height
    if width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    if not cap.isOpened():
        if isinstance(source, int):
            print(
                f"[오류] {source}번 장치를 열 수 없습니다. 카메라/캡처카드가 연결되어 있는지, "
                "다른 프로그램(화상회의 앱, 다른 캡처 소프트웨어 등)이 이미 이 장치를 쓰고 "
                "있지는 않은지 확인해 주세요. --list-devices 로 연결된 장치 목록을 다시 "
                "확인해 볼 수 있습니다."
            )
        else:
            print(f"[오류] 영상 파일을 열 수 없습니다: {source}")
        sys.exit(1)

    if requested_width or requested_height:
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        req_w = requested_width or actual_width
        req_h = requested_height or actual_height
        if (req_w, req_h) != (actual_width, actual_height):
            print(
                f"[주의] {req_w}x{req_h}를 요청했지만, 장치는 실제로 {actual_width}x{actual_height}로 "
                "동작하고 있습니다. 캡처카드가 요청한 해상도를 지원하지 않아 다운컨버전(또는 "
                "가장 가까운 지원 해상도로 대체)했을 가능성이 있습니다."
            )

    return cap


def resolve_fps(cap: cv2.VideoCapture, fps_arg: float | None) -> float:
    if fps_arg:
        return fps_arg

    reported = cap.get(cv2.CAP_PROP_FPS)
    # 일부 웹캠/드라이버는 FPS를 0이나 비정상적인 값으로 보고하기도 하므로
    # 상식적인 범위(1~120)를 벗어나면 기본값 30을 사용한다.
    if reported and 1 <= reported <= 120:
        return reported

    print("[안내] 장치가 FPS 정보를 정확히 알려주지 않아 기본값(30fps)으로 저장합니다.")
    return 30.0


def make_writer(output_dir: str, index: int, fps: float, frame_size: tuple[int, int]):
    filename = os.path.join(output_dir, f"segment_{index:04d}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(filename, fourcc, fps, frame_size)
    return writer, filename


def parse_args():
    parser = argparse.ArgumentParser(
        description="웹캠(또는 HDMI 캡처카드, 영상 파일)을 지정한 초 단위로 끊어서 순서대로 저장합니다."
    )
    parser.add_argument(
        "--source",
        default=None,
        help="카메라/캡처카드 번호(0, 1, ...) 또는 영상 파일 경로. "
        "지정하지 않으면 장치 목록을 보여주고 직접 고를 수 있습니다.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="연결된 영상 장치 목록만 보여주고 종료합니다.",
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
        help="저장할 영상의 초당 프레임 수 (기본값: 장치가 보고하는 값, 없으면 30)",
    )
    parser.add_argument("--width", type=int, default=None, help="장치에 요청할 해상도(가로)")
    parser.add_argument("--height", type=int, default=None, help="장치에 요청할 해상도(세로)")
    parser.add_argument(
        "--num-segments",
        type=int,
        default=None,
        help="지정한 개수만큼만 저장하고 자동 종료 (기본값: 계속 녹화, Ctrl+C로 종료)",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="장치가 실제로 지원하는 전체 해상도/FPS/픽셀 포맷 목록 조회를 건너뜁니다.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_devices:
        devices, method = list_video_devices()
        print_device_list(devices, method)
        return

    device_name = None
    if args.source is None:
        devices, method = list_video_devices()
        print_device_list(devices, method)
        chosen_index = choose_device_interactively(devices)
        source = chosen_index
        matched = next((d for d in devices if d["index"] == chosen_index), None)
        if matched:
            device_name = matched["name"]
    else:
        source = parse_source(args.source)

    os.makedirs(args.output_dir, exist_ok=True)

    if isinstance(source, int) and not args.no_probe:
        probe_text = probe_device_modes(platform.system(), source, device_name)
        if probe_text:
            summarize_probe_output(platform.system(), probe_text)
        else:
            print(
                "[안내] 이 장치가 지원하는 전체 모드 목록은 조회하지 못했습니다 "
                "(Linux는 v4l2-ctl, Windows는 ffmpeg가 설치되어 있어야 조회할 수 있습니다). "
                "아래 '실제 적용된 값'만 확인하고 넘어갑니다."
            )

    cap = open_capture(source, args.width, args.height)
    fps = resolve_fps(cap, args.fps)

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if frame_width <= 0 or frame_height <= 0:
        print("[오류] 장치에서 해상도를 읽어올 수 없습니다.")
        cap.release()
        sys.exit(1)

    fourcc_str = decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))

    print(
        f"[시작] 소스: {source} / 실제 적용된 해상도: {frame_width}x{frame_height} / "
        f"{fps:.1f}fps / 픽셀 포맷 코드: {fourcc_str} / {args.segment_seconds}초 단위로 저장 "
        f"→ '{args.output_dir}/' (중지하려면 Ctrl+C)"
    )
    print(
        "[참고] 위 픽셀 포맷 코드와 해상도/FPS는 OpenCV가 실제로 읽고 있는 값입니다. "
        "10bit 여부나 4:2:2 같은 색상 서브샘플링까지는 이 값만으로 확정할 수 없습니다 "
        "(위에 나온 전체 지원 모드 목록과 비교해서 판단해 주세요)."
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
            # 실제 웹캠/캡처카드는 cap.read()가 다음 프레임이 준비될 때까지 자동으로
            # 기다려주지만, 영상 파일을 소스로 쓰면(테스트용) 파일을 훨씬 빠르게
            # 읽어버려서 "3초 단위" 분할을 실제 촬영처럼 검증할 수 없다. 그래서 목표
            # fps 간격보다 빨리 읽었으면 그 차이만큼 대기해서, 파일 소스도 실제
            # 장치처럼 시간이 흐르게 만든다.
            if last_read_time is not None:
                remaining = frame_interval - (time.time() - last_read_time)
                if remaining > 0:
                    time.sleep(remaining)

            ok, frame = cap.read()
            last_read_time = time.time()
            if not ok or frame is None:
                # 영상 파일을 소스로 쓴 경우 여기서 자연스럽게 끝난다(파일 재생 완료).
                # 실제 장치라면 연결이 끊긴 것이므로 오류로 안내한다.
                if isinstance(source, int):
                    print("[오류] 장치로부터 더 이상 프레임을 받을 수 없습니다. 연결을 확인해 주세요.")
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
