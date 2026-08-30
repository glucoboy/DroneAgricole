#!/usr/bin/env bash
set -e

source "/opt/ros/${ROS_DISTRO}/setup.bash"
if [[ -f /opt/fast_lio_ws/install/setup.bash ]]; then
  source /opt/fast_lio_ws/install/setup.bash
fi
if [[ -f /opt/point_lio_ws/install/setup.bash ]]; then
  source /opt/point_lio_ws/install/setup.bash
fi
if [[ -f /opt/lio_sam_ws/install/setup.bash ]]; then
  source /opt/lio_sam_ws/install/setup.bash
fi

exec "$@"
