# Interfaces

## ROS 2 / Vulcanexus interface

| Element | Name | Type | Description |
|---|---|---|---|
| Node | `/hri_voice_command` | ROS 2 node | Runs wake-word detection, VAD-gated recording, Whisper transcription, and command matching. |
| Publishes | `/transcribed_text` | `std_msgs/String` | Full recognized speech text. |
| Publishes | `/voice_command` | `std_msgs/String` | Best matched command phrase. |
| Publishes | `/voice_command_id` | `std_msgs/Int32` | Integer ID of the matched command. |
| Publishes | `/humans/voices/tracked` | `hri_msgs/IdsList` | Active voice/speaker ID list. |
| Publishes | `/humans/voices/<voice_id>/is_speaking` | `std_msgs/Bool` | Speaking state. |
| Publishes | `/humans/voices/<voice_id>/speech` | `hri_msgs/LiveSpeech` | ROS4HRI-style speech output. |
| Publishes | `/humans/voices/<voice_id>/command` | `std_msgs/String` | Application-specific command text extension. |
| Publishes | `/humans/voices/<voice_id>/command_id` | `std_msgs/Int32` | Application-specific command ID extension. |
| Launch file | `hri_voice_command.launch.py` | ROS 2 launch | Starts the voice-command node with configurable model, language, wake-word and topic arguments. |

## ROS4HRI / ROS4RI alignment

The module aligns with ROS4HRI voice concepts through `/humans/voices/...` topics for tracked voices, speech, and speaking state. Command and command ID topics are application-specific extensions under the same voice namespace.

## FIWARE / NGSI-LD mapping

A full Context Broker integration is not included in the current open package. The ROS outputs can be mapped to NGSI-LD entities representing recognized speech, command text, command ID, confidence/matching status, and speaker state. Example mapping files should be placed in `config/` before final D4 submission.

## DDS NGSI-LD integration

DDS Enabler configuration is not included in the current code package. If required for D4, add a mapping file in `config/` and reference the ROS 2 topics listed above.
