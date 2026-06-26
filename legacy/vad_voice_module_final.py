#!/usr/bin/env python3
"""
ROS2 Industrial Whisper Microphone Transcriber (VAD-gated Wake → VAD-segment Command)
-----------------------------------------------------------------------------------
Upgrade over RMS-gating:
- Uses WebRTC VAD (if installed) to detect speech frames robustly in noise.
- LISTEN:
    - maintain a ring buffer of recent audio
    - run wake-word probing only when VAD says "speech recently"
- CAPTURE_CMD:
    - record a command segment after wake
    - stop after VAD sees trailing non-speech for N frames OR max duration

Install WebRTC VAD:
    pip install webrtcvad

Notes:
- WebRTC VAD expects 16-bit PCM audio in 10/20/30ms frames.
- We keep the sounddevice callback at a convenient frame size (default 20ms).
- Whisper expects float32 in [-1, 1], we convert back for transcription.
"""

import argparse
import os
import queue
import threading
import time
import re
from difflib import SequenceMatcher
from collections import deque
from typing import Deque, List, Optional, Tuple

# ROS2
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32

# Audio / DSP
import numpy as np
import sounddevice as sd
import soundfile as sf
import whisper
import noisereduce as nr
from scipy import signal

# YAML
import yaml

# Optional VAD
try:
    import webrtcvad  # type: ignore
    _HAS_WEBRTCVAD = True
except Exception:
    webrtcvad = None
    _HAS_WEBRTCVAD = False


# =========================================================================================
# CONFIGURATION LOADING (config.yaml beside this script)
# =========================================================================================
script_dir = os.path.dirname(os.path.realpath(__file__))
yaml_full_path = os.path.join(script_dir, "config.yaml")

try:
    with open(yaml_full_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
        VOICE_COMMANDS = config.get("VOICE_COMMANDS", {})
        WAKE_WORDS = config.get("WAKE_WORDS", ["kuka"])
except Exception as e:
    print(f"⚠️ Error loading config.yaml: {e}")
    VOICE_COMMANDS = {"start system": 0, "stop system": 8}
    WAKE_WORDS = ["kuka"]

VOICE_COMMANDS = {str(k).lower().strip(): int(v) for k, v in (VOICE_COMMANDS or {}).items()}
WAKE_WORDS = [str(w).lower().strip() for w in (WAKE_WORDS or ["kuka"]) if str(w).strip()]


# =========================================================================================
# ANSI Color Codes for Logs
# =========================================================================================
COLOR_RESET = "\033[0m"
COLOR_GRAY = "\033[90m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_MAGENTA = "\033[35m"
COLOR_CYAN = "\033[36m"


# =========================================================================================
# AUDIO DIAGNOSTICS / HELPERS
# =========================================================================================
def check_audio_devices():
    print(f"\n{COLOR_MAGENTA}--- Checking Audio Devices ---{COLOR_RESET}")
    devs = sd.query_devices()
    print(devs)

    print(f"\n{COLOR_MAGENTA}--- Checking 16kHz Support ---{COLOR_RESET}")
    for dev in devs:
        if dev.get("max_input_channels", 0) > 0:
            try:
                sd.check_input_settings(device=dev["index"], samplerate=16000, channels=1)
                print(f"Device {dev['index']} ({dev['name']}): {COLOR_GREEN}OK (16kHz){COLOR_RESET}")
            except Exception:
                print(f"Device {dev['index']} ({dev['name']}): {COLOR_RED}Incompatible with 16kHz{COLOR_RESET}")
    print("\n")
    
def check_audio_devices_orig() -> sd.DeviceList:

    print(f"\n\033[35mCheck available devices and sample rates, manually fix them in WhisperMicNode.__init__()\033[0m")
    devs:sd.DeviceList = sd.query_devices()
    print(devs)
    devs_indexes = [dev["index"] for dev in devs]
    for device in devs_indexes:
        for samplerate in [16000, 44100, 48000]:
            for channels in [1,2,3,4]:
                print(f"\nDevice {device}, samplerate {samplerate}, channels {channels}")
                try:
                    sd.check_input_settings(device=device, samplerate=samplerate, channels=channels)
                    print("\033[32mSUPPORTED\033[0m")
                except Exception as e:
                    print(f"\033[31mNOT SUPPORTED: {e}\033[0m")
    print('Final Devs are :', devs)
    print('Devs Done')
    return devs

def preemphasis(audio: np.ndarray, coef: float = 0.97) -> np.ndarray:
    if audio.size == 0:
        return audio
    return np.append(audio[0], audio[1:] - coef * audio[:-1])


def apply_bandpass_filter(
    audio: np.ndarray, lowcut: float = 300, highcut: float = 3400, fs: int = 16000, order: int = 5
) -> np.ndarray:
    if audio.size == 0:
        return audio
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = signal.butter(order, [low, high], btype="band")
    return signal.filtfilt(b, a, audio)


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    if audio.size == 0:
        return audio
    max_val = float(np.max(np.abs(audio)))
    if max_val > 0:
        return audio / max_val * 0.9
    return audio


# =========================================================================================
# TEXT / MATCHING HELPERS
# =========================================================================================
def normalize_cmd_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[,\.?!]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def similarity_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def fuzzy_match_wake_word(text: str, wake_words: List[str], threshold: float = 0.75) -> Tuple[bool, float, Optional[str]]:
    text_lower = text.lower().strip()

    for ww in wake_words:
        if ww and ww in text_lower:
            return True, 1.0, ww

    words = text_lower.split()
    for word in words:
        for ww in wake_words:
            if not ww:
                continue
            sim = SequenceMatcher(None, word, ww).ratio()
            if sim >= threshold:
                return True, sim, ww

    common_misrecognitions = {
        "kuka": ["kuka", "cooka", "kukka", "cuca", "kuca", "kooka", "cookie", "coca"],
    }
    for ww in wake_words:
        for v in common_misrecognitions.get(ww, []):
            if v in text_lower:
                return True, 0.9, ww

    return False, 0.0, None


def find_best_command_match(command_text: str) -> Tuple[Optional[int], Optional[str], float]:
    best_cmd_id = None
    best_phrase = None
    best_score = 0.0
    for phrase, cmd_id in VOICE_COMMANDS.items():
        score = similarity_ratio(command_text, phrase)
        if score > best_score:
            best_score = score
            best_cmd_id = cmd_id
            best_phrase = phrase
    return best_cmd_id, best_phrase, best_score


# =========================================================================================
# VAD HELPERS
# =========================================================================================
def float_to_pcm16_bytes(x: np.ndarray) -> bytes:
    """x is float32 in [-1, 1]. Returns PCM16 little-endian bytes."""
    x = np.clip(x, -1.0, 1.0)
    pcm16 = (x * 32767.0).astype(np.int16)
    return pcm16.tobytes()


def rms_energy(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(x * x)))


# =========================================================================================
# ROS2 NODE
# =========================================================================================
class WhisperROS2Node(Node):
    def __init__(self, args: argparse.Namespace):
        super().__init__("whisper_industrial_node_vad")
        self.args = args

        # ROS2 Publishers
        self.text_pub = self.create_publisher(String, args.text_topic, 10)
        self.cmd_pub_text = self.create_publisher(String, args.cmd_topic, 10)
        self.cmd_pub_id = self.create_publisher(Int32, args.cmd_id_topic, 10)

        # Audio settings
        self.sample_rate = 16000
        self.channels = 1
        self.device = args.device

        # VAD settings
        self.use_vad = bool(args.use_vad) and _HAS_WEBRTCVAD
        self.vad_aggressiveness = int(args.vad_aggressiveness)
        self.vad_frame_ms = int(args.vad_frame_ms)  # 10/20/30 only for webrtcvad
        self.vad = webrtcvad.Vad(self.vad_aggressiveness) if self.use_vad else None

        # callback frame size must match vad_frame_ms for clean framing (recommended)
        self.frame_ms = self.vad_frame_ms if self.use_vad else int(args.frame_ms)
        self.frame_s = self.frame_ms / 1000.0
        self.frame_samples = int(self.sample_rate * self.frame_s)

        # fallback RMS gate if no VAD
        self.energy_thresh = float(args.energy_thresh)

        # Wake + command logic
        self.wake_words = [w.lower().strip() for w in args.wake_words]
        self.enable_enhancement = not args.no_enhancement

        self.wake_window_s = float(args.wake_window)
        self.wake_hop_s = float(args.wake_hop)
        self.cmd_max_s = float(args.cmd_max)

        # Command end: trailing non-speech frames count
        self.cmd_end_silence_ms = int(args.cmd_end_silence_ms)
        self.end_silence_frames = max(1, int(self.cmd_end_silence_ms / self.frame_ms))

        # For LISTEN gating: require N speech frames in last M frames
        self.listen_speech_hold_ms = int(args.listen_speech_hold_ms)
        self.listen_hold_frames = max(1, int(self.listen_speech_hold_ms / self.frame_ms))
        self.speech_hist: Deque[bool] = deque(maxlen=self.listen_hold_frames)

        # Audio queue
        self.audio_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=int(args.queue_max))

        # Debug buffer for saving raw audio
        self.audio_record_buffer: List[np.ndarray] = []

        # Stats
        self.total_transcriptions = 0
        self.wake_word_detections = 0
        self.command_matches = 0

        # State machine
        self.state = "LISTEN"
        self.last_wake_probe_t = 0.0

        # CAPTURE_CMD buffers
        self.cmd_buf: List[np.ndarray] = []
        self.trailing_nonspeech_frames = 0

        # Ring buffer for LISTEN mode
        self.ring_max_s = max(2.0, self.wake_window_s * 2.0)
        self.ring: Deque[np.ndarray] = deque()
        self.ring_len_samples = 0

        # Diagnostics
        if args.print_devices:
            check_audio_devices()

        if args.use_vad and not _HAS_WEBRTCVAD:
            self.get_logger().warn(
                f"{COLOR_YELLOW}⚠️ webrtcvad not installed, falling back to RMS gating. "
                f"Install with: pip install webrtcvad{COLOR_RESET}"
            )

        # Load models
        self.get_logger().info(f"{COLOR_CYAN}Loading Whisper model ({args.model})...{COLOR_RESET}")
        self.model = whisper.load_model(args.model)
        self.get_logger().info(f"{COLOR_GREEN}✅ Main model loaded successfully.{COLOR_RESET}")

        self.get_logger().info(f"{COLOR_CYAN}Loading wake Whisper model ({args.wake_model})...{COLOR_RESET}")
        self.wake_model = whisper.load_model(args.wake_model)
        self.get_logger().info(f"{COLOR_GREEN}✅ Wake model loaded successfully.{COLOR_RESET}")

        # Banner
        self.get_logger().info(f"\n{COLOR_CYAN}{'='*78}{COLOR_RESET}")
        self.get_logger().info(f"{COLOR_CYAN}🎤 WHISPER (VAD-gated Wake → VAD-segment Command){COLOR_RESET}")
        self.get_logger().info(f"{COLOR_CYAN}{'='*78}{COLOR_RESET}")
        self.get_logger().info(f"   Device: {self.device if self.device is not None else 'Default'}")
        self.get_logger().info(f"   Sample Rate: {self.sample_rate} Hz")
        self.get_logger().info(f"   Frame: {self.frame_ms}ms ({self.frame_samples} samples)")
        self.get_logger().info(f"   VAD: {'ON' if self.use_vad else 'OFF'} "
                               f"(aggr={self.vad_aggressiveness if self.use_vad else 'n/a'})")
        self.get_logger().info(f"   Wake window/hop: {self.wake_window_s:.2f}s / {self.wake_hop_s:.2f}s")
        self.get_logger().info(f"   Command max: {self.cmd_max_s:.2f}s")
        self.get_logger().info(f"   Command end silence: {self.cmd_end_silence_ms}ms "
                               f"({self.end_silence_frames} frames)")
        self.get_logger().info(f"   LISTEN speech hold: {self.listen_speech_hold_ms}ms "
                               f"({self.listen_hold_frames} frames)")
        if not self.use_vad:
            self.get_logger().info(f"   RMS energy threshold: {self.energy_thresh:.5f}")
        self.get_logger().info(
            f"{COLOR_GREEN}🎧 Listening for wake word: {', '.join([w.upper() for w in self.wake_words])}{COLOR_RESET}\n"
        )

        # Start audio stream
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                device=self.device,
                callback=self.audio_callback,
                blocksize=self.frame_samples,
                latency=args.latency,
            )
            self.stream.start()
        except Exception as e:
            self.get_logger().error(f"{COLOR_RED}❌ Failed to start audio stream: {e}{COLOR_RESET}")
            raise

        # Start processing thread
        threading.Thread(target=self.process_audio_loop, daemon=True).start()

    # -------------------------
    # Ring buffer ops
    # -------------------------
    def _ring_push(self, x: np.ndarray) -> None:
        self.ring.append(x)
        self.ring_len_samples += int(x.shape[0])

        max_samples = int(self.ring_max_s * self.sample_rate)
        while self.ring_len_samples > max_samples and self.ring:
            y = self.ring.popleft()
            self.ring_len_samples -= int(y.shape[0])

    def _ring_last_seconds(self, sec: float) -> np.ndarray:
        need = int(sec * self.sample_rate)
        if need <= 0 or self.ring_len_samples <= 0:
            return np.zeros((0,), dtype=np.float32)

        out_chunks: List[np.ndarray] = []
        got = 0
        for chunk in reversed(self.ring):
            out_chunks.append(chunk)
            got += int(chunk.shape[0])
            if got >= need:
                break

        if not out_chunks:
            return np.zeros((0,), dtype=np.float32)

        out = np.concatenate(list(reversed(out_chunks)), axis=0)
        if out.shape[0] > need:
            out = out[-need:]
        return np.squeeze(out).astype(np.float32)

    # -------------------------
    # Speech decision (VAD or RMS fallback)
    # -------------------------
    def _is_speech_frame(self, frame_1d: np.ndarray) -> bool:
        if frame_1d.size == 0:
            return False

        if self.use_vad and self.vad is not None:
            # WebRTC VAD requires PCM16 bytes of exact frame size (10/20/30ms).
            pcm = float_to_pcm16_bytes(frame_1d.astype(np.float32))
            try:
                return bool(self.vad.is_speech(pcm, self.sample_rate))
            except Exception:
                # If something weird happens, fall back to RMS for this frame
                return rms_energy(frame_1d) >= self.energy_thresh

        # RMS fallback
        return rms_energy(frame_1d) >= self.energy_thresh

    def _listen_gate_open(self) -> bool:
        """
        LISTEN gating: only probe wake word if we've seen speech recently.
        """
        if len(self.speech_hist) == 0:
            return False
        # open if any speech frame in the recent window
        return any(self.speech_hist)

    # -------------------------
    # Sounddevice callback
    # -------------------------
    def audio_callback(self, indata, frames, time_info, status):
        if status:
            self.get_logger().warn(f"Audio status: {status}")

        try:
            self.audio_queue.put_nowait(indata.copy())
        except queue.Full:
            # drop oldest to keep realtime
            try:
                _ = self.audio_queue.get_nowait()
                self.audio_queue.put_nowait(indata.copy())
            except Exception:
                pass

        if self.args.save_last_chunk:
            self.audio_record_buffer.append(indata.copy())

    # -------------------------
    # Wake probe transcription
    # -------------------------
    def _transcribe_wake_probe(self, audio_np: np.ndarray) -> str:
        try:
            audio_np = audio_np.astype(np.float32)
            if audio_np.size == 0:
                return ""
            if float(np.max(np.abs(audio_np))) < 0.005:
                return ""

            res = self.wake_model.transcribe(
                audio_np,
                language=self.args.lang,
                fp16=False,
                condition_on_previous_text=False,
                beam_size=1,
                temperature=0.0,
            )
            text = (res.get("text") or "").strip()
            if text and self.args.print_wake_probe:
                self.get_logger().info(f"{COLOR_GRAY}🔎 WAKE PROBE: {text}{COLOR_RESET}")
            return text
        except Exception:
            return ""

    # -------------------------
    # Publish helpers
    # -------------------------
    def publish_command(self, full_text: str, command_text: str, cmd_id: int, matched_phrase: str, score: float):
        if matched_phrase == command_text:
            self.get_logger().info(
                f"{COLOR_GREEN}✅ COMMAND{COLOR_RESET} "
                f"ID={COLOR_YELLOW}{cmd_id}{COLOR_RESET} | "
                f"TEXT='{COLOR_CYAN}{command_text}{COLOR_RESET}'"
            )
        else:
            self.get_logger().info(
                f"{COLOR_GREEN}✅ FUZZY COMMAND{COLOR_RESET} "
                f"ID={COLOR_YELLOW}{cmd_id}{COLOR_RESET} | "
                f"score={COLOR_MAGENTA}{score:.2f}{COLOR_RESET} | "
                f"heard='{COLOR_CYAN}{command_text}{COLOR_RESET}' | "
                f"matched='{COLOR_CYAN}{matched_phrase}{COLOR_RESET}'"
            )

        tmsg = String()
        tmsg.data = full_text
        self.text_pub.publish(tmsg)

        cmsg = String()
        cmsg.data = command_text
        self.cmd_pub_text.publish(cmsg)

        imsg = Int32()
        imsg.data = int(cmd_id)
        self.cmd_pub_id.publish(imsg)

        self.command_matches += 1

    def _save_wake_audio(self, audio_np: np.ndarray):
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"wake_word_{timestamp}.wav"
            sf.write(filename, audio_np.astype(np.float32), self.sample_rate)
        except Exception:
            pass

    # -------------------------
    # Full command transcription + matching
    # -------------------------
    def transcribe_command(self, audio_np: np.ndarray):
        try:
            audio_np = audio_np.astype(np.float32)
            if audio_np.size == 0:
                return
            if float(np.max(np.abs(audio_np))) < 0.005:
                return

            audio_clean = audio_np.copy()

            if self.enable_enhancement:
                audio_clean = nr.reduce_noise(
                    y=audio_clean, sr=self.sample_rate,
                    stationary=True, prop_decrease=0.85, n_fft=1024
                )
                audio_clean = nr.reduce_noise(
                    y=audio_clean, sr=self.sample_rate,
                    stationary=False, prop_decrease=0.6, n_fft=512
                )
                audio_clean = apply_bandpass_filter(audio_clean, lowcut=300, highcut=3400, fs=self.sample_rate)
                audio_clean = preemphasis(audio_clean, coef=0.97)
                audio_clean = normalize_audio(audio_clean)

            audio_clean = audio_clean.astype(np.float32)

            result = self.model.transcribe(
                audio_clean,
                language=self.args.lang,
                fp16=False,
                condition_on_previous_text=False,
            )
            text = (result.get("text") or "").strip()
            self.total_transcriptions += 1

            if not text:
                return

            self.get_logger().info(f"{COLOR_GRAY}📝 TRANSCRIBED: {text}{COLOR_RESET}")

            has_wake, sim, matched_wake = fuzzy_match_wake_word(text, self.wake_words, threshold=self.args.wake_threshold)

            text_lower = text.lower().strip()
            command_text = text_lower

            # Often, command segment starts after wake; but if wake appears, strip it
            if has_wake and matched_wake and matched_wake in text_lower:
                command_text = text_lower.replace(matched_wake, "", 1).strip()

            command_text = normalize_cmd_text(command_text)

            if not command_text:
                self.get_logger().info(f"{COLOR_YELLOW}⚠️ Empty/unclear command segment{COLOR_RESET}")
                return

            # Exact
            cmd_id = VOICE_COMMANDS.get(command_text)
            if cmd_id is not None:
                self.publish_command(text, command_text, cmd_id, matched_phrase=command_text, score=1.0)
                if self.args.save_wake_audio:
                    self._save_wake_audio(audio_np)
                return

            # Fuzzy
            best_id, best_phrase, best_score = find_best_command_match(command_text)

            if best_phrase is not None and self.args.print_best_match:
                self.get_logger().info(
                    f"{COLOR_MAGENTA}🤔 BEST MATCH{COLOR_RESET} "
                    f"ID={COLOR_YELLOW}{best_id}{COLOR_RESET} | "
                    f"score={COLOR_MAGENTA}{best_score:.2f}{COLOR_RESET} | "
                    f"heard='{COLOR_CYAN}{command_text}{COLOR_RESET}' | "
                    f"matched='{COLOR_CYAN}{best_phrase}{COLOR_RESET}'"
                )

            if best_phrase is not None and best_score >= self.args.cmd_threshold and best_id is not None:
                self.publish_command(text, command_text, best_id, matched_phrase=best_phrase, score=best_score)
                if self.args.save_wake_audio:
                    self._save_wake_audio(audio_np)
            else:
                self.get_logger().warn(
                    f"{COLOR_YELLOW}⚠️ Unrecognized command{COLOR_RESET} "
                    f"(best_score={best_score:.2f}): '{command_text}'"
                )

        except Exception as e:
            self.get_logger().error(f"{COLOR_RED}❌ Processing error: {e}{COLOR_RESET}")
            import traceback
            traceback.print_exc()

    # -------------------------
    # Core processing loop (VAD upgraded)
    # -------------------------
    def process_audio_loop(self):
        """
        LISTEN:
          - update ring + speech_hist using VAD decisions
          - probe wake only if speech_hist says "speech recently" AND wake_hop elapsed
        CAPTURE_CMD:
          - collect frames after wake
          - stop when trailing non-speech frames >= end_silence_frames OR cmd_max reached
        """
        while rclpy.ok():
            try:
                data = self.audio_queue.get(timeout=0.5)  # (N,1)
            except queue.Empty:
                continue

            data = data.astype(np.float32)
            self._ring_push(data)

            frame_1d = np.squeeze(data)
            is_speech = self._is_speech_frame(frame_1d)
            self.speech_hist.append(is_speech)

            now = time.time()

            if self.state == "LISTEN":
                if (now - self.last_wake_probe_t) >= self.wake_hop_s and self._listen_gate_open():
                    self.last_wake_probe_t = now

                    probe = self._ring_last_seconds(self.wake_window_s)
                    if probe.size == 0:
                        continue

                    text = self._transcribe_wake_probe(probe)
                    if not text:
                        continue

                    has_wake, sim, matched_wake = fuzzy_match_wake_word(
                        text, self.wake_words, threshold=self.args.wake_threshold
                    )
                    if has_wake:
                        self.wake_word_detections += 1
                        self.get_logger().info(
                            f"{COLOR_GREEN}🎯 WAKE DETECTED{COLOR_RESET} "
                            f"({matched_wake}, sim={sim:.2f}) → {COLOR_CYAN}CAPTURE_CMD{COLOR_RESET}"
                        )
                        self.state = "CAPTURE_CMD"
                        self.cmd_buf = []
                        self.trailing_nonspeech_frames = 0

                        # Start capture right away with current frame (post-wake)
                        self.cmd_buf.append(data.copy())

            else:  # CAPTURE_CMD
                self.cmd_buf.append(data.copy())

                if is_speech:
                    self.trailing_nonspeech_frames = 0
                else:
                    self.trailing_nonspeech_frames += 1

                cmd_len_s = float(sum(x.shape[0] for x in self.cmd_buf) / self.sample_rate)
                stop_on_silence = self.trailing_nonspeech_frames >= self.end_silence_frames
                stop_on_max = cmd_len_s >= self.cmd_max_s

                if stop_on_silence or stop_on_max:
                    cmd_audio = np.squeeze(np.concatenate(self.cmd_buf, axis=0)).astype(np.float32)

                    if self.args.save_last_chunk:
                        try:
                            raw_to_save = np.concatenate(self.audio_record_buffer, axis=0)
                            sf.write("last_chunk.wav", raw_to_save, self.sample_rate)
                        except Exception:
                            pass
                        self.audio_record_buffer = []

                    self.transcribe_command(cmd_audio)

                    self.state = "LISTEN"
                    self.cmd_buf = []
                    self.trailing_nonspeech_frames = 0


# =========================================================================================
# MAIN
# =========================================================================================
def main():
    parser = argparse.ArgumentParser(
        description="ROS2 Industrial Whisper Microphone Transcriber (VAD-gated Wake → VAD-segment Command)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Models / language
    parser.add_argument("--model", type=str, default="small", help="Whisper model size (tiny, base, small, medium, large)")
    parser.add_argument("--wake-model", type=str, default="tiny", help="Whisper model for wake probing (tiny/base recommended)")
    parser.add_argument("--lang", type=str, default="en", help="Language code (en, de, es, fr, etc.)")

    # Audio
    parser.add_argument("--device", type=int, default=None, help="Audio device index (from sounddevice list)")
    parser.add_argument("--latency", type=str, default="high", help="sounddevice latency hint: low|high")
    parser.add_argument("--queue-max", type=int, default=256, help="Max frames buffered in queue before dropping")

    # VAD (upgrade)
    parser.add_argument("--use-vad", action="store_true", help="Use WebRTC VAD (requires `pip install webrtcvad`)")
    parser.add_argument("--vad-aggressiveness", type=int, default=2, choices=[0, 1, 2, 3], help="WebRTC VAD aggressiveness")
    parser.add_argument("--vad-frame-ms", type=int, default=20, choices=[10, 20, 30], help="Frame size for VAD (ms)")
    parser.add_argument("--listen-speech-hold-ms", type=int, default=300, help="Require speech in last N ms to probe wake")

    # If VAD off, you can still choose a callback frame size (ms)
    parser.add_argument("--frame-ms", type=int, default=150, help="Callback frame size if VAD is off (ms)")

    # Wake/command logic
    parser.add_argument("--wake-window", type=float, default=1.2, help="Seconds used for wake probing window")
    parser.add_argument("--wake-hop", type=float, default=0.30, help="How often to run wake probing (seconds)")
    parser.add_argument("--cmd-max", type=float, default=4.0, help="Max seconds to record command after wake word")
    parser.add_argument("--cmd-end-silence-ms", type=int, default=600, help="Stop command after trailing non-speech (ms)")

    # Fallback RMS gate (only used if VAD is off or errors)
    parser.add_argument("--energy-thresh", type=float, default=0.008, help="RMS threshold for speech-energy gating fallback")

    # Wake words + thresholds
    parser.add_argument("--wake-words", type=str, nargs="+", default=WAKE_WORDS, help="Wake words to detect")
    parser.add_argument("--wake-threshold", type=float, default=0.70, help="Wake word fuzzy similarity threshold")
    parser.add_argument("--cmd-threshold", type=float, default=0.70, help="Command fuzzy similarity threshold")

    # Enhancement / debug
    parser.add_argument("--no-enhancement", action="store_true", help="Disable audio enhancement/noise reduction")
    parser.add_argument("--save-last-chunk", action="store_true", help="Save last raw buffer to last_chunk.wav for debugging")
    parser.add_argument("--save-wake-audio", action="store_true", help="Save audio when a command is detected")
    parser.add_argument("--print-devices", action="store_true", help="Print audio device list on start")
    parser.add_argument("--print-wake-probe", action="store_true", help="Print wake-probe transcript")
    parser.add_argument("--print-best-match", action="store_true", help="Print best fuzzy match candidate")

    # ROS topics
    parser.add_argument("--text-topic", type=str, default="/transcribed_text", help="ROS topic for full transcribed text")
    parser.add_argument("--cmd-topic", type=str, default="/voice_command", help="ROS topic for extracted command text")
    parser.add_argument("--cmd-id-topic", type=str, default="/voice_command_id", help="ROS topic for matched command id (Int32)")

    args = parser.parse_args()

    print(f"{COLOR_CYAN}Loaded config from:{COLOR_RESET} {yaml_full_path}")
    print(f"{COLOR_CYAN}VOICE_COMMANDS:{COLOR_RESET} {len(VOICE_COMMANDS)} commands")
    print(f"{COLOR_CYAN}WAKE_WORDS:{COLOR_RESET} {WAKE_WORDS}")
    if args.use_vad:
        print(f"{COLOR_CYAN}VAD requested:{COLOR_RESET} webrtcvad "
              f"{'(FOUND)' if _HAS_WEBRTCVAD else '(NOT INSTALLED - fallback to RMS)'}")

    rclpy.init()
    node = WhisperROS2Node(args)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print(f"\n{COLOR_CYAN}{'='*78}{COLOR_RESET}")
        print(f"{COLOR_CYAN}📊 SESSION STATISTICS{COLOR_RESET}")
        print(f"{COLOR_CYAN}{'='*78}{COLOR_RESET}")
        print(f"   Total command transcriptions: {node.total_transcriptions}")
        print(f"   Wake detections (probe):      {node.wake_word_detections}")
        print(f"   Command matches:             {node.command_matches}")
        if node.total_transcriptions > 0:
            rate = (node.command_matches / node.total_transcriptions) * 100
            print(f"   Match rate:                  {rate:.1f}%")
        print(f"{COLOR_GREEN}✅ Stopped successfully{COLOR_RESET}\n")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
