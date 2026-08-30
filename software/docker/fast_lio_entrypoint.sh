#!/usr/bin/env bash
set -e

source "/opt/ros/${ROS_DISTRO}/setup.bash"
source /opt/fast_lio_ws/install/setup.bash

exec "$@"
