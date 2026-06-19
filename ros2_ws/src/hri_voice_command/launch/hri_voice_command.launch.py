from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value='small'),
        DeclareLaunchArgument('wake_model', default_value='tiny'),
        DeclareLaunchArgument('language', default_value='en'),
        DeclareLaunchArgument('wake_threshold', default_value='0.70'),
        DeclareLaunchArgument('cmd_threshold', default_value='0.70'),
        DeclareLaunchArgument('cmd_max', default_value='4.0'),
        DeclareLaunchArgument('text_topic', default_value='/transcribed_text'),
        DeclareLaunchArgument('cmd_topic', default_value='/voice_command'),
        DeclareLaunchArgument('cmd_id_topic', default_value='/voice_command_id'),
        DeclareLaunchArgument('hri_voice_id', default_value='anonymous_speaker'),
        DeclareLaunchArgument('hri_locale', default_value='en_US'),

        Node(
            package='hri_voice_command',
            executable='hri_voice_command',
            name='hri_voice_command',
            output='screen',
            emulate_tty=True,
            arguments=[
                '--use-vad',
                '--model', LaunchConfiguration('model'),
                '--wake-model', LaunchConfiguration('wake_model'),
                '--lang', LaunchConfiguration('language'),
                '--wake-threshold', LaunchConfiguration('wake_threshold'),
                '--cmd-threshold', LaunchConfiguration('cmd_threshold'),
                '--cmd-max', LaunchConfiguration('cmd_max'),
                '--text-topic', LaunchConfiguration('text_topic'),
                '--cmd-topic', LaunchConfiguration('cmd_topic'),
                '--cmd-id-topic', LaunchConfiguration('cmd_id_topic'),
                '--hri-voice-id', LaunchConfiguration('hri_voice_id'),
                '--hri-locale', LaunchConfiguration('hri_locale'),
            ],
        ),
    ])
