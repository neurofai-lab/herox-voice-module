from glob import glob
from setuptools import find_packages, setup

package_name = 'hri_voice_command'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/ament_index/resource_index/pal_system_module', ['module/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml') + glob('config/*.yml')),
        ('share/' + package_name + '/module', glob('module/*.yaml')),
    ],
    package_data={package_name: ['config.yaml']},
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Shino Sam',
    maintainer_email='shino.sam@dfki.de',
    description='ROS2 Whisper VAD-gated wake-word and voice-command recognition node.',
    license='Apache License 2.0',
    entry_points={
        'console_scripts': [
            'hri_voice_command = hri_voice_command.node_voice_command:main',
            'vad_voice_module_final = hri_voice_command.node_voice_command:main',
        ],
    },
)
