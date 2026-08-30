#!/usr/bin/env bash
set -e

source /opt/ros/jazzy/setup.bash
source /opt/px4_ros_ws/install/setup.bash

exec "$@"
