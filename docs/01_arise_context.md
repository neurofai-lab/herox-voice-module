# ARISE context

This repository packages the HERoX voice interaction capability as a reusable HRI module. It extracts the voice-command recognition part of the demonstrator into an open ROS 2 package that can be inspected, built, launched, and adapted independently of the full HERoX system.

The module contributes to ARISE by providing a speech-based operator interface for human-robot interaction. It converts spoken operator commands into structured ROS 2 outputs and ROS4HRI-style voice topics that can be consumed by robot-control, task-assistance, or human-aware orchestration components.
