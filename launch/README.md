# Launch files

The functional ROS 2 launch files are kept inside the ROS 2 package to avoid changing the original package behaviour:

`ros2_ws/src/hri_voice_command/launch/`

After building the workspace, launch the module with:

```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch hri_voice_command hri_voice_command.launch.py
```
