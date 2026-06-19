# HERoX Voice Command Recognition Module

Reusable ROS 2/Vulcanexus-compatible HRI voice module extracted from the HERoX demonstrator. The module listens for wake words, records operator commands, transcribes speech using Whisper, matches configurable command phrases, and publishes command outputs through ROS 2 and ROS4HRI-style voice topics.

## Repository layout

```text
herox-voice-module/
  README.md
  LICENSE
  docs/
    01_arise_context.md
    02_interfaces.md
    03_installation_and_hello_world.md
    04_basic_demo_how_to_use.md
    05_role_in_demonstrator.md
  ros2_ws/src/hri_voice_command/
    hri_voice_command/
    launch/
    config/
    legacy/
    package.xml
    setup.py
  examples/
  launch/
  config/
  media/
    architecture_diagram.png
    screenshots/
    video_link.md
  docker/
```

## Quick start

```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch hri_voice_command hri_voice_command.launch.py
```

The functional ROS 2 package is located in `ros2_ws/src/hri_voice_command`. The code was moved into the recommended ARISE repository structure without changing the core voice-command implementation.
