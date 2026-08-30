#!/usr/bin/env bash
set -eo pipefail

source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u

talker_log="$(mktemp)"
ros2 run demo_nodes_cpp talker >"${talker_log}" 2>&1 &
talker_pid=$!

cleanup() {
  kill "${talker_pid}" 2>/dev/null || true
  wait "${talker_pid}" 2>/dev/null || true
  rm -f "${talker_log}"
}
trap cleanup EXIT

message=""
for _ in $(seq 1 15); do
  if message="$(timeout 3s ros2 topic echo --once /chatter std_msgs/msg/String 2>/dev/null)"; then
    break
  fi
  sleep 1
done

if [[ "${message}" != *"Hello World"* ]]; then
  echo "ROS 2 validation failed. Talker output:" >&2
  cat "${talker_log}" >&2
  exit 1
fi

printf 'ROS_DISTRO=%s\n' "${ROS_DISTRO}"
printf 'ROS_DOMAIN_ID=%s\n' "${ROS_DOMAIN_ID:-unset}"
printf '%s\n' "${message}"
