# hri_voice_command

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
