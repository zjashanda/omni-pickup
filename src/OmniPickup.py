#!/usr/bin/env python3
"""Record raw PCM audio from a selectable PortAudio host API device."""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import pyaudio
except ImportError as exc:  # Keep --help usable when the audio dependency is absent.
    pyaudio = None  # type: ignore[assignment]
    PYAUDIO_IMPORT_ERROR: Optional[ImportError] = exc
else:
    PYAUDIO_IMPORT_ERROR = None


DEFAULT_DEVICE_NAME = ""
DEFAULT_HOST_API = "wasapi"
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_CHANNELS = 8
DEFAULT_BIT_DEPTH = 16
DEFAULT_FRAMES_PER_BUFFER = 4800
DEFAULT_OUTPUT_DIR = "."
DEVICE_RECHECK_INTERVAL_SECONDS = 1.0
STATUS_UPDATE_INTERVAL_SECONDS = 1.0

BIT_DEPTH_FORMAT_NAMES = {
    8: "paUInt8",
    16: "paInt16",
    24: "paInt24",
    32: "paInt32",
}

# PyAudio reports Windows host APIs with names such as "Windows WASAPI".
HOST_API_ALIASES = {
    "asio": ("asio",),
    "directsound": ("directsound", "windowsdirectsound"),
    "wasapi": ("wasapi", "windowswasapi"),
    "wdmks": ("wdmks", "windowswdmks"),
}
HOST_API_LABELS = {
    "asio": "ASIO",
    "directsound": "DirectSound",
    "wasapi": "WASAPI",
    "wdmks": "WDM-KS",
}


class RecorderError(RuntimeError):
    """A controlled setup or recording failure."""


@dataclass(frozen=True)
class DeviceSelection:
    index: int
    name: str
    host_api_index: int
    host_api_name: str
    max_input_channels: int


def configure_console() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def normalize_name(value: str) -> str:
    """Normalize device/API names while retaining non-ASCII letters and digits."""

    return "".join(ch for ch in value.casefold() if ch.isalnum())


def canonical_host_api(value: str) -> str:
    normalized = normalize_name(value)
    for canonical, aliases in HOST_API_ALIASES.items():
        if normalized == canonical or normalized in aliases:
            return canonical
    valid = ", ".join(("asio", "directsound", "wasapi", "wdm-ks"))
    raise argparse.ArgumentTypeError(
        f"unknown host API {value!r}; choose one of: {valid}"
    )


def host_api_matches(host_api_name: str, requested_host_api: str) -> bool:
    canonical = canonical_host_api(requested_host_api)
    normalized = normalize_name(host_api_name)
    return normalized == canonical or normalized in HOST_API_ALIASES[canonical]


def format_byte_count(byte_count: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(byte_count)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{byte_count} B"


def format_elapsed_time(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    if minutes > 0:
        return f"{minutes:02d}:{secs:02d}"
    return f"{secs:02d}s"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Record raw PCM audio from an input device through ASIO, "
            "DirectSound, WASAPI, or WDM-KS."
        ),
        epilog=(
            "The output is headerless interleaved PCM. Playback tools must be "
            "given the same sample rate, channel count, and bit depth."
        ),
    )
    parser.add_argument(
        "--host-api",
        "--api",
        dest="host_api",
        type=canonical_host_api,
        default=None,
        metavar="{asio,directsound,wasapi,wdm-ks}",
        help=(
            "Host API used for recording. Default: wasapi. "
            "Aliases Windows DirectSound/WASAPI/WDM-KS names."
        ),
    )
    parser.add_argument(
        "--device-name",
        default=DEFAULT_DEVICE_NAME,
        help="Device name or substring. Default: first matching input device.",
    )
    parser.add_argument(
        "--device-index",
        type=int,
        help="Use a specific PortAudio device index within the selected host API.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
        help=f"Sample rate in Hz. Default: {DEFAULT_SAMPLE_RATE}",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=DEFAULT_CHANNELS,
        help=f"Input channel count. Default: {DEFAULT_CHANNELS}",
    )
    parser.add_argument(
        "--bit-depth",
        type=int,
        choices=sorted(BIT_DEPTH_FORMAT_NAMES),
        default=DEFAULT_BIT_DEPTH,
        help=f"PCM bit depth. Default: {DEFAULT_BIT_DEPTH}",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="Recording duration in seconds. Omit or use 0 for continuous recording.",
    )
    parser.add_argument(
        "-o",
        "--output",
        "--name",
        dest="output",
        help="Output path. Default: start timestamp with .pcm suffix.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for the default timestamp file. Default: {DEFAULT_OUTPUT_DIR!r}",
    )
    parser.add_argument(
        "--frames-per-buffer",
        type=int,
        default=DEFAULT_FRAMES_PER_BUFFER,
        help=f"Frames per read. Default: {DEFAULT_FRAMES_PER_BUFFER}",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List all input devices; pass --host-api to filter the list.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the target device and format, then exit without recording.",
    )
    return parser


def sanitize_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> argparse.Namespace:
    if args.device_index is not None and args.device_index < 0:
        parser.error("--device-index must be >= 0")
    if args.sample_rate <= 0:
        parser.error("--sample-rate must be > 0")
    if args.channels <= 0:
        parser.error("--channels must be > 0")
    if args.frames_per_buffer <= 0:
        parser.error("--frames-per-buffer must be > 0")
    if args.duration is not None:
        if not math.isfinite(args.duration) or args.duration < 0:
            parser.error("--duration must be a finite number >= 0")
        if args.duration == 0:
            args.duration = None
    return args


def require_pyaudio():
    if pyaudio is None:
        detail = "PyAudio is not installed or could not be imported."
        if PYAUDIO_IMPORT_ERROR is not None:
            detail += f" Import error: {PYAUDIO_IMPORT_ERROR}"
        raise RecorderError(detail)
    return pyaudio


def create_pyaudio():
    module = require_pyaudio()
    try:
        return module.PyAudio()
    except Exception as exc:
        raise RecorderError(f"Could not initialize PyAudio/PortAudio: {exc}") from exc


def get_audio_format(bit_depth: int) -> int:
    module = require_pyaudio()
    format_name = BIT_DEPTH_FORMAT_NAMES[bit_depth]
    try:
        return int(getattr(module, format_name))
    except AttributeError as exc:
        raise RecorderError(
            f"This PyAudio build does not expose the {bit_depth}-bit format."
        ) from exc


def get_host_api_name(pa, host_api_index: int) -> str:
    return str(pa.get_host_api_info_by_index(host_api_index)["name"])


def format_supported(
    pa,
    device_index: int,
    channels: int,
    sample_rate: int,
    audio_format: int,
) -> None:
    try:
        pa.is_format_supported(
            sample_rate,
            input_device=device_index,
            input_channels=channels,
            input_format=audio_format,
        )
    except Exception as exc:
        raise RecorderError(
            "Requested format is not supported by the device: "
            f"{sample_rate} Hz, {channels} channels, {exc}."
        ) from exc


def select_device(
    pa,
    requested_host_api: str,
    device_name: str,
    device_index: Optional[int],
) -> DeviceSelection:
    requested_name = normalize_name(device_name)
    candidates: list[tuple[int, DeviceSelection]] = []

    for index in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(index)
        host_api_name = get_host_api_name(pa, int(info["hostApi"]))
        if not host_api_matches(host_api_name, requested_host_api):
            continue
        if int(info["maxInputChannels"]) <= 0:
            continue

        selection = DeviceSelection(
            index=index,
            name=str(info["name"]),
            host_api_index=int(info["hostApi"]),
            host_api_name=host_api_name,
            max_input_channels=int(info["maxInputChannels"]),
        )

        if device_index is not None:
            if index == device_index:
                return selection
            continue

        current_name = normalize_name(selection.name)
        if not requested_name:
            candidates.append((2, selection))
        elif current_name == requested_name:
            candidates.append((0, selection))
        elif requested_name in current_name or current_name in requested_name:
            candidates.append((1, selection))

    host_label = HOST_API_LABELS[canonical_host_api(requested_host_api)]
    if device_index is not None:
        raise RecorderError(
            f"{host_label} input device index {device_index} was not found. "
            "Use --list-devices --host-api to inspect available inputs."
        )
    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1].index))
        return candidates[0][1]
    raise RecorderError(
        f"No {host_label} input device matched {device_name!r}. "
        "Use --list-devices --host-api to inspect available inputs."
    )


def validate_device(
    pa,
    selection: DeviceSelection,
    channels: int,
    sample_rate: int,
    audio_format: int,
) -> None:
    info = pa.get_device_info_by_index(selection.index)
    if int(info["maxInputChannels"]) < channels:
        raise RecorderError(
            f"Device {selection.name!r} only exposes "
            f"{int(info['maxInputChannels'])} input channels, but {channels} were requested."
        )

    host_api_name = get_host_api_name(pa, int(info["hostApi"]))
    if not host_api_matches(host_api_name, selection.host_api_name):
        raise RecorderError(f"Device {selection.name!r} changed host API during validation.")
    format_supported(
        pa=pa,
        device_index=selection.index,
        channels=channels,
        sample_rate=sample_rate,
        audio_format=audio_format,
    )


def device_available(pa, selection: DeviceSelection) -> bool:
    target_name = normalize_name(selection.name)
    for index in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(index)
        if int(info["maxInputChannels"]) <= 0:
            continue
        host_api_name = get_host_api_name(pa, int(info["hostApi"]))
        if not host_api_matches(host_api_name, selection.host_api_name):
            continue
        if normalize_name(str(info["name"])) == target_name:
            return True
    return False


def build_output_path(output: Optional[str], output_dir: str, started_at: datetime) -> Path:
    if output:
        path = Path(output)
    else:
        filename = f"{started_at.strftime('%Y%m%d_%H%M%S')}.pcm"
        path = Path(output_dir) / filename
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def classify_host_api(host_api_name: str) -> str:
    try:
        return canonical_host_api(host_api_name)
    except argparse.ArgumentTypeError:
        return "other"


def list_devices(pa, requested_host_api: Optional[str]) -> None:
    groups: dict[str, list[tuple[int, dict, str]]] = {
        "asio": [],
        "directsound": [],
        "wasapi": [],
        "wdmks": [],
        "other": [],
    }
    for index in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(index)
        if int(info["maxInputChannels"]) <= 0:
            continue
        host_api_name = get_host_api_name(pa, int(info["hostApi"]))
        if requested_host_api and not host_api_matches(host_api_name, requested_host_api):
            continue
        group_name = classify_host_api(host_api_name)
        groups[group_name].append((index, info, host_api_name))

    print("Input devices visible to PortAudio/PyAudio:")
    ordered_groups = (
        ("asio", "ASIO"),
        ("directsound", "DirectSound"),
        ("wasapi", "WASAPI"),
        ("wdmks", "WDM-KS"),
        ("other", "Other"),
    )
    printed = False
    for group_name, group_label in ordered_groups:
        entries = groups[group_name]
        if not entries:
            continue
        printed = True
        print(f"\n=== {group_label} ===")
        for index, info, host_api_name in entries:
            print(f"    --{index}")
            print(f"      {info['name']}")
            print(
                f"        host_api={host_api_name} "
                f"inputs={int(info['maxInputChannels'])} "
                f"outputs={int(info['maxOutputChannels'])} "
                f"default_rate={float(info['defaultSampleRate']):g}"
            )
    if not printed:
        if requested_host_api:
            label = HOST_API_LABELS[canonical_host_api(requested_host_api)]
            print(f"No input devices found for {label}.")
        else:
            print("No input devices found.")


def open_stream(pa, selection: DeviceSelection, args: argparse.Namespace, audio_format: int):
    try:
        return pa.open(
            format=audio_format,
            channels=args.channels,
            rate=args.sample_rate,
            input=True,
            input_device_index=selection.index,
            frames_per_buffer=args.frames_per_buffer,
        )
    except Exception as exc:
        raise RecorderError(
            f"Could not open input device {selection.name!r} "
            f"through {selection.host_api_name}: {exc}"
        ) from exc


def record(args: argparse.Namespace, requested_host_api: str) -> Path:
    pa = create_pyaudio()
    stream = None
    recorded_frames = 0
    started_at = datetime.now()
    try:
        audio_format = get_audio_format(args.bit_depth)
        try:
            sample_width = pa.get_sample_size(audio_format)
        except Exception as exc:
            raise RecorderError(f"Could not determine sample width: {exc}") from exc
        bytes_per_frame = sample_width * args.channels
        selection = select_device(
            pa=pa,
            requested_host_api=requested_host_api,
            device_name=args.device_name,
            device_index=args.device_index,
        )
        validate_device(
            pa=pa,
            selection=selection,
            channels=args.channels,
            sample_rate=args.sample_rate,
            audio_format=audio_format,
        )
        total_frames_target = (
            None
            if args.duration is None
            else int(round(args.duration * args.sample_rate))
        )
        output_path = build_output_path(
            output=args.output,
            output_dir=args.output_dir,
            started_at=started_at,
        )
        stream = open_stream(pa, selection, args, audio_format)

        print(
            f"Recording started: device={selection.name!r}, "
            f"host_api={selection.host_api_name}, sample_rate={args.sample_rate}, "
            f"channels={args.channels}, bit_depth={args.bit_depth}, "
            f"output={str(output_path)!r}"
        )
        if total_frames_target is None:
            print("Mode: continuous recording. Press Ctrl+C to stop.")
        else:
            print(f"Mode: fixed duration {args.duration:.3f} seconds.")

        next_recheck = time.monotonic() + DEVICE_RECHECK_INTERVAL_SECONDS
        next_status_update = time.monotonic()
        progress_line_active = False
        try:
            with output_path.open("wb") as file_obj:
                while True:
                    if total_frames_target is not None:
                        remaining_frames = total_frames_target - recorded_frames
                        if remaining_frames <= 0:
                            break
                        frames_to_read = min(args.frames_per_buffer, remaining_frames)
                    else:
                        frames_to_read = args.frames_per_buffer

                    try:
                        chunk = stream.read(
                            frames_to_read,
                            exception_on_overflow=False,
                        )
                    except KeyboardInterrupt:
                        raise
                    except Exception as exc:
                        raise RecorderError(
                            "Recording stopped because the stream failed. "
                            f"The device may have been disconnected: {exc}"
                        ) from exc

                    expected_bytes = frames_to_read * bytes_per_frame
                    if len(chunk) != expected_bytes:
                        raise RecorderError(
                            "Recording stopped because the stream returned an unexpected "
                            f"chunk size: expected {expected_bytes} bytes, got {len(chunk)} bytes."
                        )

                    file_obj.write(chunk)
                    recorded_frames += frames_to_read
                    now = time.monotonic()
                    if now >= next_status_update:
                        file_obj.flush()
                        written_bytes = recorded_frames * bytes_per_frame
                        recorded_seconds = recorded_frames / args.sample_rate
                        print(
                            "\r"
                            f"Recording... elapsed={format_elapsed_time(recorded_seconds):>8} "
                            f"size={format_byte_count(written_bytes):>10} "
                            f"({written_bytes:,} bytes)",
                            end="",
                            flush=True,
                        )
                        progress_line_active = True
                        next_status_update = now + STATUS_UPDATE_INTERVAL_SECONDS

                    if now >= next_recheck:
                        if not device_available(pa, selection):
                            raise RecorderError(
                                "Recording stopped because the input device is no longer available."
                            )
                        next_recheck = now + DEVICE_RECHECK_INTERVAL_SECONDS
        except OSError as exc:
            raise RecorderError(f"Could not write output file {output_path!r}: {exc}") from exc
        except BaseException:
            if progress_line_active:
                print()
            raise

        if progress_line_active:
            print()
        file_size = output_path.stat().st_size
        recorded_seconds = recorded_frames / args.sample_rate
        print(
            f"Recording finished: frames={recorded_frames}, "
            f"seconds={recorded_seconds:.3f}, bytes={file_size}."
        )
        return output_path
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        pa.terminate()


def resolve_host_api(args: argparse.Namespace) -> str:
    return args.host_api or DEFAULT_HOST_API


def run(args: argparse.Namespace) -> int:
    pa = create_pyaudio()
    try:
        if args.list_devices:
            list_devices(pa, args.host_api)
            return 0

        requested_host_api = resolve_host_api(args)
        audio_format = get_audio_format(args.bit_depth)
        selection = select_device(
            pa=pa,
            requested_host_api=requested_host_api,
            device_name=args.device_name,
            device_index=args.device_index,
        )
        validate_device(
            pa=pa,
            selection=selection,
            channels=args.channels,
            sample_rate=args.sample_rate,
            audio_format=audio_format,
        )
        print(
            f"Device validated: index={selection.index}, name={selection.name!r}, "
            f"host_api={selection.host_api_name}, "
            f"max_inputs={selection.max_input_channels}."
        )
    finally:
        pa.terminate()

    if args.validate_only:
        return 0
    record(args, resolve_host_api(args))
    return 0


def main() -> int:
    configure_console()
    parser = build_parser()
    args = sanitize_args(parser.parse_args(), parser)
    try:
        return run(args)
    except KeyboardInterrupt:
        print("Recording interrupted by user.", file=sys.stderr)
        return 130
    except RecorderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
