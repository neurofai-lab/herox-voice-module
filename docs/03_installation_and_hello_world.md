# Installation and hello world

## Native ROS 2/Vulcanexus workspace

```bash
cd ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
ros2 launch hri_voice_command hri_voice_command.launch.py
```

## Expected result

The node starts as `/hri_voice_command`, initializes the configured Whisper model, listens to the selected audio device, publishes speaking state, and publishes recognized command outputs after wake-word detection and command matching.

## Hardware note

The normal execution path requires a microphone/audio input device. For D4 reproducibility without live audio, add a sample WAV path or mock publisher/test script under `examples/`.
