#!/usr/bin/env bash
set -euo pipefail

campaign_root="${1:-results/benchmarks/fast_lio2/botanicgarden_1006-03/qualification_08x_v01}"
phase="${2:-all}"
dynamic_bag="datasets/derived/botanicgarden/1006-03/dynamic/velodyne_xsens_fastlio2_30s_offset60_ros2"
full_bag="datasets/derived/botanicgarden/1006-03/full/velodyne_xsens_fastlio2_full_ros2"
baseline_config="configs/lio/fast_lio2/botanicgarden_velodyne_xsens.yaml"
playback_rate="0.8"

if [[ "${phase}" != "qualification" && "${phase}" != "repeats" && "${phase}" != "all" ]]; then
  echo "Phase invalide: ${phase} (qualification, repeats ou all)" >&2
  exit 2
fi

run_case() {
  local scope="$1"
  local variant="$2"
  local repeat="$3"
  local bag="$4"
  local config="$5"
  local run_dir="${campaign_root}/${scope}/${variant}/repeat_${repeat}"

  if [[ -f "${run_dir}/run_manifest.json" && -f "${run_dir}/metrics.json" ]]; then
    echo "CAMPAIGN_SKIP scope=${scope} variant=${variant} repeat=${repeat}"
    return 0
  fi
  if [[ -e "${run_dir}" ]]; then
    echo "Essai incomplet déjà présent: ${run_dir}" >&2
    exit 3
  fi

  echo "CAMPAIGN_START scope=${scope} variant=${variant} repeat=${repeat} rate=${playback_rate}"
  bash tools/benchmarks/run_fastlio2_botanicgarden_benchmark.sh \
    "${bag}" \
    "${run_dir}" \
    "${config}" \
    "${playback_rate}"
  python3 tools/benchmarks/analyze_lio_trajectory.py \
    "${run_dir}/estimate" \
    --output "${run_dir}/metrics.json" \
    >"${run_dir}/analysis.log"
  echo "CAMPAIGN_DONE scope=${scope} variant=${variant} repeat=${repeat}"
}

mkdir -p "${campaign_root}"

if [[ "${phase}" == "qualification" || "${phase}" == "all" ]]; then
  run_case dynamic baseline 01 "${dynamic_bag}" "${baseline_config}"
  run_case full baseline 01 "${full_bag}" "${baseline_config}"
fi

if [[ "${phase}" == "repeats" || "${phase}" == "all" ]]; then
  run_case dynamic baseline 02 "${dynamic_bag}" "${baseline_config}"
  run_case dynamic baseline 03 "${dynamic_bag}" "${baseline_config}"

  variants=(
    "voxel_fine_025m:configs/lio/fast_lio2/sensitivity/voxel_fine_025m.yaml"
    "voxel_coarse_100m:configs/lio/fast_lio2/sensitivity/voxel_coarse_100m.yaml"
    "extrinsic_translation_x_plus_5cm:configs/lio/fast_lio2/sensitivity/extrinsic_translation_x_plus_5cm.yaml"
    "extrinsic_yaw_plus_2deg:configs/lio/fast_lio2/sensitivity/extrinsic_yaw_plus_2deg.yaml"
  )
  for definition in "${variants[@]}"; do
    variant="${definition%%:*}"
    config="${definition#*:}"
    for repeat in 01 02 03; do
      run_case dynamic "${variant}" "${repeat}" "${dynamic_bag}" "${config}"
    done
  done
fi

python3 tools/benchmarks/summarize_fastlio_08x_campaign.py "${campaign_root}" \
  >"${campaign_root}/campaign_summary.log"
echo "CAMPAIGN_ROOT=${campaign_root}"
