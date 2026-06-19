# Role in the HERoX demonstrator

The voice module provides the spoken operator-command interface of the HERoX demonstrator. It enables an operator to activate the system through wake-word detection, speak commands, and receive structured command IDs that can be consumed by downstream task execution or robot-assistance components.

The reusable extraction keeps the voice-command node, command configuration, launch file, ROS 2 outputs, and ROS4HRI-style voice topics. Demonstrator-specific command sets can be edited in the configuration file without changing the main node implementation.
