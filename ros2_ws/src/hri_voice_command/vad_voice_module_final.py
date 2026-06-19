#!/usr/bin/env python3
"""Compatibility entry point for the original single-file runner.

This keeps the old command working from the repository root:

    python3 vad_voice_module_final.py

The implementation lives in hri_voice_command/node_voice_command.py.
"""

from hri_voice_command.node_voice_command import main


if __name__ == "__main__":
    main()
