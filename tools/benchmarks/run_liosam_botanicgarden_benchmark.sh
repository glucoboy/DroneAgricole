#!/usr/bin/env bash
set -euo pipefail

bag_path="${1:-datasets/derived/botanicgarden/1006-03/smoke/velodyne_xsens_fastlio2_5s_ros2}"
run_dir="${2:-results/benchmarks/lio_sam/botanicgarden_1006-03/smoke_$(date -u +%Y%m%dT%H%M%SZ)}"
config_path="${3:-configs/lio/lio_sam/botanicgarden_velodyne_xsens.yaml}"
playback_rate="${4:-1.0}"
playback_delay_s="${LIOSAM_PLAYBACK_DELAY_S:-1.0}"
pipeline_drain_timeout_s="${LIOSAM_PIPELINE_DRAIN_TIMEOUT_S:-15.0}"
pipeline_stable_s="${LIOSAM_PIPELINE_STABLE_S:-1.0}"

if [[ ! -d "${bag_path}" ]]; then
  echo "Bag ROS 2 introuvable: ${bag_path}" >&2
  exit 2
fi
if [[ ! -f "${config_path}" ]]; then
  echo "Configuration LIO-SAM introuvable: ${config_path}" >&2
  exit 2
fi
if [[ -e "${run_dir}" ]]; then
  echo "Le dossier de résultat existe déjà: ${run_dir}" >&2
  exit 2
fi

mkdir -p "${run_dir}"
effective_config="${run_dir}/effective_config.yaml"
cp -- "${config_path}" "${effective_config}"

liosam_pid=""
monitor_pid=""
recorder_pid=""
playback_pid=""

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
  if [[ -n "${playback_pid}" ]]; then stop_process "${playback_pid}"; fi
  if [[ -n "${recorder_pid}" ]]; then stop_process "${recorder_pid}"; fi
  if [[ -n "${liosam_pid}" ]]; then stop_process "${liosam_pid}"; fi
  if [[ -n "${monitor_pid}" ]]; then stop_process "${monitor_pid}"; fi
}

abort_run() {
  echo "Benchmark LIO-SAM interrompu à la demande de l'utilisateur." >&2
  exit 130
}

trap cleanup EXIT
trap abort_run INT TERM

python3 tools/benchmarks/lio_sam_pipeline_monitor.py \
  >"${run_dir}/pipeline_monitor.log" 2>&1 &
monitor_pid=$!

profile_options=(--output "${run_dir}/resource_profile.json")
if [[ "${LIO_DASHBOARD:-0}" == "1" ]]; then
  profile_options+=(--publish-ros-metrics --benchmark-bag "${bag_path}")
fi

python3 tools/benchmarks/profile_process.py "${profile_options[@]}" \
  -- \
  python3 tools/benchmarks/launch_lio_sam.py --config "${effective_config}" \
  >"${run_dir}/lio_sam.log" 2>&1 &
liosam_pid=$!

for _ in $(seq 1 100); do
  nodes="$(ros2 node list 2>/dev/null || true)"
  if grep -Fxq /lio_sam_imageProjection <<<"${nodes}" \
    && grep -Fxq /lio_sam_featureExtraction <<<"${nodes}" \
    && grep -Fxq /lio_sam_mapOptimization <<<"${nodes}" \
    && grep -Fxq /lio_sam_pipeline_monitor <<<"${nodes}"; then
    break
  fi
  if ! kill -0 "${liosam_pid}" 2>/dev/null; then
    echo "LIO-SAM s'est arrêté pendant son démarrage." >&2
    tail -100 "${run_dir}/lio_sam.log" >&2
    exit 3
  fi
  sleep 0.2
done

nodes="$(ros2 node list 2>/dev/null || true)"
if ! grep -Fxq /lio_sam_imageProjection <<<"${nodes}" \
  || ! grep -Fxq /lio_sam_featureExtraction <<<"${nodes}" \
  || ! grep -Fxq /lio_sam_mapOptimization <<<"${nodes}" \
  || ! grep -Fxq /lio_sam_pipeline_monitor <<<"${nodes}"; then
  echo "Les nœuds LIO-SAM ne sont pas tous apparus." >&2
  exit 3
fi

ros2 bag record \
  --storage mcap \
  --output "${run_dir}/estimate" \
  /Odometry /path /gt_poses /lio_sam/pipeline_counters \
  >"${run_dir}/record.log" 2>&1 &
recorder_pid=$!

sleep 1
playback_start_ns="$(date +%s%N)"
ros2 bag play "${bag_path}" --rate "${playback_rate}" --delay "${playback_delay_s}" >"${run_dir}/playback.log" 2>&1 &
playback_pid=$!
while kill -0 "${playback_pid}" 2>/dev/null; do
  if ! kill -0 "${liosam_pid}" 2>/dev/null; then
    echo "LIO-SAM s'est arrêté pendant le rejeu; le rosbag est interrompu." >&2
    tail -100 "${run_dir}/lio_sam.log" >&2
    stop_process "${playback_pid}"
    playback_pid=""
    exit 4
  fi
  sleep 0.2
done
playback_status=0
wait "${playback_pid}" || playback_status=$?
playback_pid=""
playback_end_ns="$(date +%s%N)"

if (( playback_status != 0 )); then
  echo "Le rejeu du rosbag a échoué avec le code ${playback_status}." >&2
  tail -100 "${run_dir}/playback.log" >&2
  exit 4
fi

if ! kill -0 "${liosam_pid}" 2>/dev/null; then
  echo "LIO-SAM s'est arrêté pendant le rejeu." >&2
  tail -100 "${run_dir}/lio_sam.log" >&2
  exit 4
fi

if ! python3 tools/benchmarks/wait_for_pipeline_drain.py \
  --bag "${bag_path}" \
  --input-topic /velodyne_points \
  --pipeline-topic /lio_sam/pipeline_counters \
  --timeout-s "${pipeline_drain_timeout_s}" \
  --stable-s "${pipeline_stable_s}" \
  --output "${run_dir}/pipeline_drain.json"; then
  echo "Avertissement: la réception complète des scans LIO-SAM n'a pas été confirmée avant le délai maximal." >&2
fi

stop_process "${recorder_pid}"
recorder_pid=""
stop_process "${liosam_pid}"
liosam_pid=""
stop_process "${monitor_pid}"
monitor_pid=""
trap - EXIT INT TERM

ros2 bag info "${run_dir}/estimate" | tee "${run_dir}/bag_info.txt"
python3 tools/benchmarks/summarize_lio_run.py \
  --algorithm lio_sam \
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
  --pipeline-topic /lio_sam/pipeline_counters \
  --output "${run_dir}/metrics.json" \
  >"${run_dir}/analysis.log"
echo "LIOSAM_RUN_DIR=${run_dir}"
