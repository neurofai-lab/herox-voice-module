# Basic demo and how to use

## Demo goal

Demonstrate that the module converts spoken operator commands into ROS 2 and ROS4HRI-style outputs.

## Run

```bash
cd ros2_ws
source install/setup.bash
ros2 launch hri_voice_command hri_voice_command.launch.py
```

## Inspect output topics

```bash
ros2 topic echo /transcribed_text
ros2 topic echo /voice_command
ros2 topic echo /voice_command_id
ros2 topic echo /humans/voices/tracked
```

## D4 note

Add a short demo video, sample command transcript, expected logs, or sample WAV execution before final submission.
