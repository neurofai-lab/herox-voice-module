"""Minimal repository checks for the HEROX voice module."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE_FILE = ROOT / "hri_voice_command" / "node_voice_command.py"
SETUP_FILE = ROOT / "setup.py"
CONFIG_FILE = ROOT / "config" / "config.yaml"


def test_node_source_is_valid_python():
    """Check that the main node contains valid Python syntax."""
    source = NODE_FILE.read_text(encoding="utf-8")
    compile(source, str(NODE_FILE), "exec")


def test_expected_output_topics_are_declared():
    """Check that the documented ROS 2 output topics exist in the code."""
    source = NODE_FILE.read_text(encoding="utf-8")

    expected_topics = [
        "/transcribed_text",
        "/voice_command",
        "/voice_command_id",
        "/humans/voices/tracked",
        "/humans/voices/<voice_id>/speech",
        "/humans/voices/<voice_id>/is_speaking",
        "/humans/voices/<voice_id>/command",
        "/humans/voices/<voice_id>/command_id",
    ]

    for topic in expected_topics:
        assert topic in source


def test_command_configuration_exists():
    """Check that command and wake-word configuration is included."""
    assert CONFIG_FILE.is_file()

    config_text = CONFIG_FILE.read_text(encoding="utf-8")

    assert "VOICE_COMMANDS:" in config_text
    assert "WAKE_WORDS:" in config_text


def test_console_entry_point_is_declared():
    """Check that the ROS 2 executable is registered."""
    source = SETUP_FILE.read_text(encoding="utf-8")

    assert (
        "hri_voice_command = "
        "hri_voice_command.node_voice_command:main"
    ) in source
