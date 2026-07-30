from argparse import Namespace

import rclpy
import pytest

from hri_msgs.msg import IdsList, LiveSpeech
from std_msgs.msg import Bool, Int32, String

import hri_voice_command.node_voice_command as voice_module
from hri_voice_command.node_voice_command import WhisperROS2Node


class FakeWhisperModel:
    def transcribe(self, *_args, **_kwargs):
        return {"text": ""}


class FakeInputStream:
    """Replacement for the physical microphone stream."""

    def __init__(self, *args, **kwargs):
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        pass


class FakeThread:
    """Prevent the infinite audio-processing loop from starting."""

    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass


def make_args():
    """Return the arguments required by WhisperROS2Node."""

    return Namespace(
        text_topic="/transcribed_text",
        cmd_topic="/voice_command",
        cmd_id_topic="/voice_command_id",
        hri_voice_id="anonymous_speaker",
        hri_tracked_voices_topic="/humans/voices/tracked",
        hri_speech_topic=None,
        hri_is_speaking_topic=None,
        hri_command_topic=None,
        hri_command_id_topic=None,
        hri_locale="en_US",
        device=None,
        use_vad=False,
        vad_aggressiveness=2,
        vad_frame_ms=20,
        frame_ms=150,
        energy_thresh=0.008,
        wake_words=["kuka"],
        no_enhancement=True,
        wake_window=1.2,
        wake_hop=0.30,
        cmd_max=4.0,
        cmd_end_silence_ms=600,
        listen_speech_hold_ms=300,
        queue_max=32,
        print_devices=False,
        model="small",
        wake_model="tiny",
        latency="high",
        lang="en",
        wake_threshold=0.70,
        cmd_threshold=0.70,
        save_last_chunk=False,
        save_wake_audio=False,
        print_wake_probe=False,
        print_best_match=False,
    )


@pytest.fixture
def voice_node(monkeypatch):
    """Create the voice node without models or microphone hardware."""

    monkeypatch.setattr(
        voice_module.whisper,
        "load_model",
        lambda _name: FakeWhisperModel(),
    )
    monkeypatch.setattr(
        voice_module.sd,
        "InputStream",
        FakeInputStream,
    )
    monkeypatch.setattr(
        voice_module.threading,
        "Thread",
        FakeThread,
    )

    if not rclpy.ok():
        rclpy.init()

    node = WhisperROS2Node(make_args())

    yield node

    if hasattr(node, "stream"):
        node.stream.stop()
        node.stream.close()

    node.destroy_node()

    if rclpy.ok():
        rclpy.shutdown()


def test_node_starts(voice_node):
    """Verify that the ROS 2 node can be constructed."""

    assert voice_node.get_name() == "hri_voice_command"


def test_application_publishers_exist(voice_node):
    """Verify the application-level output interfaces."""

    assert voice_node.text_pub.topic_name == "/transcribed_text"
    assert voice_node.text_pub.msg_type is String

    assert voice_node.cmd_pub_text.topic_name == "/voice_command"
    assert voice_node.cmd_pub_text.msg_type is String

    assert voice_node.cmd_pub_id.topic_name == "/voice_command_id"
    assert voice_node.cmd_pub_id.msg_type is Int32


def test_ros4hri_publishers_exist(voice_node):
    """Verify the ROS4HRI-compatible output interfaces."""

    assert (
        voice_node.hri_voice_tracked_pub.topic_name
        == "/humans/voices/tracked"
    )
    assert voice_node.hri_voice_tracked_pub.msg_type is IdsList

    assert (
        voice_node.hri_speech_pub.topic_name
        == "/humans/voices/anonymous_speaker/speech"
    )
    assert voice_node.hri_speech_pub.msg_type is LiveSpeech

    assert (
        voice_node.hri_is_speaking_pub.topic_name
        == "/humans/voices/anonymous_speaker/is_speaking"
    )
    assert voice_node.hri_is_speaking_pub.msg_type is Bool

    assert (
        voice_node.hri_command_pub.topic_name
        == "/humans/voices/anonymous_speaker/command"
    )
    assert voice_node.hri_command_pub.msg_type is String

    assert (
        voice_node.hri_command_id_pub.topic_name
        == "/humans/voices/anonymous_speaker/command_id"
    )
    assert voice_node.hri_command_id_pub.msg_type is Int32


def test_tracked_voice_message_is_published(voice_node, monkeypatch):
    """Verify the content of the periodic tracked-voice message."""

    published_messages = []

    monkeypatch.setattr(
        voice_node.hri_voice_tracked_pub,
        "publish",
        published_messages.append,
    )

    voice_node.publish_hri_tracked_voice()

    assert len(published_messages) == 1
    assert published_messages[0].ids == ["anonymous_speaker"]
