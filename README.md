# HEROX Voice Module

ROS2 package for VAD-gated wake-word and voice-command recognition using Whisper.

The package follows the same general layout used by ROS4HRI Repos:

```text
hri_voice_command/
├── config/
├── hri_voice_command/
├── launch/
├── module/
├── resource/
├── test/
├── package.xml
├── setup.cfg
├── setup.py
├── requirements.txt
└── requirements_voice.sh
```

## Docker usage

From the parent folder containing this repo:

```bash
docker run -it --rm --gpus all --device /dev/snd --group-add audio   -v $(pwd)/hri_voice_command_repo:/workspace   eprosima/vulcanexus:humble-desktop bash
```

Inside the container:

```bash
cd /workspace
./requirements_voice.sh
colcon build --symlink-install
source install/setup.bash
ros2 launch hri_voice_command hri_voice_command.launch.py
```


## Compatibility with the original command

The old single-script command is still supported from the repository root:

```bash
python3 vad_voice_module_final.py
```

This wrapper calls the packaged ROS2 node implementation in:

```text
hri_voice_command/node_voice_command.py
```

## Direct run without launch

```bash
cd /workspace
./requirements_voice.sh
python3 -m hri_voice_command.node_voice_command --use-vad
```

Or after building:

```bash
ros2 run hri_voice_command hri_voice_command --use-vad
```

## Useful launch arguments

```bash
ros2 launch hri_voice_command hri_voice_command.launch.py model:=small wake_model:=tiny language:=en
```

Published topics:

- `/transcribed_text` (`std_msgs/String`)
- `/voice_command` (`std_msgs/String`)
- `/voice_command_id` (`std_msgs/Int32`)

Command phrases and wake words are configured in:

```text
config/config.yaml
```

You can also override the config path with:

```bash
export HRI_VOICE_COMMAND_CONFIG=/absolute/path/to/config.yaml
```


## ROS4HRI voice topics

In addition to the legacy topics, this node publishes ROS4HRI-compatible voice topics:

- `/humans/voices/tracked` (`hri_msgs/IdsList`)
- `/humans/voices/anonymous_speaker/is_speaking` (`std_msgs/Bool`)
- `/humans/voices/anonymous_speaker/speech` (`hri_msgs/LiveSpeech`)

Application-specific command extension topics are also published under the same voice namespace:

- `/humans/voices/anonymous_speaker/command` (`std_msgs/String`)
- `/humans/voices/anonymous_speaker/command_id` (`std_msgs/Int32`)

The legacy topics `/transcribed_text`, `/voice_command`, and `/voice_command_id` are preserved for backward compatibility.

# ROS 2 Interfaces and Configuration

This section documents the inputs, outputs, message types, and configurable runtime options of the HEROX voice module.

## Input interface

The module receives live mono audio directly from a system microphone through the Python `sounddevice` library. It does not subscribe to a ROS 2 audio topic.

| Input | Type | Description |
|---|---|---|
| System microphone | Mono PCM audio at `16 kHz` | Audio used for voice-activity, wake-word, and command recognition |
| `config/config.yaml` | YAML file | Defines accepted wake words, command phrases, and command IDs |

A different command configuration file can be selected with:

```bash
export HRI_VOICE_COMMAND_CONFIG=/absolute/path/to/config.yaml
```

## Output topics

### Application topics

| Topic | Message type | Description |
|---|---|---|
| `/transcribed_text` | `std_msgs/msg/String` | Full transcription of an accepted command utterance |
| `/voice_command` | `std_msgs/msg/String` | Recognized command text |
| `/voice_command_id` | `std_msgs/msg/Int32` | Numeric ID assigned to the recognized command |

These outputs are published when the transcription matches a configured command.

### ROS4HRI topics

| Topic | Message type | Description |
|---|---|---|
| `/humans/voices/tracked` | `hri_msgs/msg/IdsList` | Publishes the configured voice ID once per second |
| `/humans/voices/<voice_id>/is_speaking` | `std_msgs/msg/Bool` | Indicates whether command audio is being captured |
| `/humans/voices/<voice_id>/speech` | `hri_msgs/msg/LiveSpeech` | Publishes the final accepted transcription |
| `/humans/voices/<voice_id>/command` | `std_msgs/msg/String` | HEROX-specific command text output |
| `/humans/voices/<voice_id>/command_id` | `std_msgs/msg/Int32` | HEROX-specific command ID output |

The default voice ID is `anonymous_speaker`. Therefore, the default speech topic is:

```text
/humans/voices/anonymous_speaker/speech
```

In `hri_msgs/msg/LiveSpeech`, the `final` field contains the transcription, `locale` contains the configured language locale, and `confidence` contains the command-matching similarity score.

## Configurable parameters

The following options are exposed by the launch file.

| Option | Type | Default | Description |
|---|---|---|---|
| `model` | string | `small` | Whisper model used for command transcription |
| `wake_model` | string | `tiny` | Whisper model used for wake-word detection |
| `language` | string | `en` | Whisper language code |
| `wake_threshold` | float | `0.70` | Minimum wake-word similarity score |
| `cmd_threshold` | float | `0.70` | Minimum command similarity score |
| `cmd_max` | float | `4.0` | Maximum command recording duration in seconds |
| `text_topic` | string | `/transcribed_text` | Transcription output topic |
| `cmd_topic` | string | `/voice_command` | Command text output topic |
| `cmd_id_topic` | string | `/voice_command_id` | Command ID output topic |
| `hri_voice_id` | string | `anonymous_speaker` | Voice ID used in ROS4HRI topic names |
| `hri_locale` | string | `en_US` | Locale used in `hri_msgs/msg/LiveSpeech` |

Additional executable options include:

| Option | Default | Description |
|---|---|---|
| `--device` | automatic | Microphone device index |
| `--vad-aggressiveness` | `2` | WebRTC VAD aggressiveness from `0` to `3` |
| `--vad-frame-ms` | `20` | VAD frame size in milliseconds |
| `--wake-words` | values from YAML | Accepted wake words |
| `--cmd-end-silence-ms` | `600` | Trailing silence used to end command capture |
| `--no-enhancement` | disabled | Disables audio enhancement and noise reduction |

## Interface verification

```bash
ros2 topic type /transcribed_text
ros2 topic type /voice_command_id
ros2 topic type /humans/voices/tracked

ros2 topic echo /voice_command
ros2 topic echo /voice_command_id
```

