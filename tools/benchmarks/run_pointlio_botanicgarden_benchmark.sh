#!/usr/bin/env bash
set -euo pipefail

bag_path="${1:-datasets/derived/botanicgarden/1006-03/smoke/velodyne_xsens_fastlio2_5s_ros2}"
run_dir="${2:-results/benchmarks/point_lio/botanicgarden_1006-03/smoke_$(date -u +%Y%m%dT%H%M%SZ)}"
config_path="${3:-configs/lio/point_lio/botanicgarden_velodyne_xsens.yaml}"
playback_rate="${4:-1.0}"
playback_delay_s="${POINTLIO_PLAYBACK_DELAY_S:-1.0}"

if [[ ! -d "${bag_path}" ]]; then
  echo "Bag ROS 2 introuvable: ${bag_path}" >&2
  exit 2
fi
if [[ ! -f "${config_path}" ]]; then
  echo "Configuration Point-LIO introuvable: ${config_path}" >&2
  exit 2
fi
if [[ -e "${run_dir}" ]]; then
  echo "Le dossier de résultat existe déjà: ${run_dir}" >&2
  exit 2
fi

mkdir -p "${run_dir}"
effective_config="${run_dir}/effective_config.yaml"
cp -- "${config_path}" "${effective_config}"

pointlio_pid=""
recorder_pid=""

stop_process() {
  local pid="$1"
  kill -INT "${pid}" 2>/dev/null || return 0
  for _ in $(seq 1 100); do
    if ! kill -0 "${pid}" 2>/dev/null; then
      wait "${pid}" 2>/dev/null || true
      return 0
    fi
    sleep 0.1
  done
  kill -TERM "${pid}" 2>/dev/null || true
  wait "${pid}" 2>/dev/null || true
}

cleanup() {
  set +e
  if [[ -n "${recorder_pid}" ]]; then stop_process "${recorder_pid}"; fi
  if [[ -n "${pointlio_pid}" ]]; then stop_process "${pointlio_pid}"; fi
}
trap cleanup EXIT

profile_options=(--output "${run_dir}/resource_profile.json")
if [[ "${LIO_DASHBOARD:-0}" == "1" ]]; then
  profile_options+=(--publish-ros-metrics --benchmark-bag "${bag_path}")
fi

python3 tools/benchmarks/profile_process.py "${profile_options[@]}" \
  -- \
  /opt/point_lio_ws/install/lib/point_lio/pointlio_mapping \
  --ros-args --params-file "${effective_config}" \
  -r /aft_mapped_to_init:=/Odometry \
  >"${run_dir}/point_lio.log" 2>&1 &
pointlio_pid=$!

for _ in $(seq 1 50); do
  if ros2 topic list 2>/dev/null | grep -Fxq /Odometry; then break; fi
  if ! kill -0 "${pointlio_pid}" 2>/dev/null; then
    echo "Point-LIO s'est arrêté pendant son démarrage." >&2
    tail -100 "${run_dir}/point_lio.log" >&2
    exit 3
  fi
  sleep 0.2
done
if ! ros2 topic list 2>/dev/null | grep -Fxq /Odometry; then
  echo "Le topic /Odometry n'est pas apparu." >&2
  exit 3
fi

ros2 bag record \
  --storage mcap \
  --output "${run_dir}/estimate" \
  /Odometry /path /gt_poses /point_lio/pipeline_counters \
  >"${run_dir}/record.log" 2>&1 &
recorder_pid=$!

sleep 1
playback_start_ns="$(date +%s%N)"
ros2 bag play "${bag_path}" --rate "${playback_rate}" --delay "${playback_delay_s}" >"${run_dir}/playback.log" 2>&1
playback_end_ns="$(date +%s%N)"
sleep 2

stop_process "${recorder_pid}"
recorder_pid=""
stop_process "${pointlio_pid}"
pointlio_pid=""
trap - EXIT

ros2 bag info "${run_dir}/estimate" | tee "${run_dir}/bag_info.txt"
python3 tools/benchmarks/summarize_lio_run.py \
  --algorithm point_lio \
  --bag "${bag_path}" \
  --config "${effective_config}" \
  --profile "${run_dir}/resource_profile.json" \
  --output "${run_dir}/run_manifest.json" \
  --playback-rate "${playback_rate}" \
  --playback-delay-s "${playback_delay_s}" \
  --playback-start-ns "${playback_start_ns}" \
  --playback-end-ns "${playback_end_ns}"
python3 tools/benchmarks/analyze_lio_trajectory.py \
  "${run_dir}/estimate" \
  --pipeline-topic /point_lio/pipeline_counters \
  --output "${run_dir}/metrics.json" \
  >"${run_dir}/analysis.log"
echo "POINTLIO_RUN_DIR=${run_dir}"
