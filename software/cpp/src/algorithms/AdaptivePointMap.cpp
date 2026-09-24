#include "drone_agricole/core/AdaptivePointMap.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace drone_agricole::core {
namespace {

constexpr qint64 voxelCoordinateBias = 1LL << 20;
constexpr quint64 voxelCoordinateMask = (1ULL << 21) - 1ULL;

bool finitePoint(const QVector3D& point) {
  return std::isfinite(point.x()) && std::isfinite(point.y()) && std::isfinite(point.z());
}

}  // namespace

AdaptivePointMap::AdaptivePointMap(const float initialVoxelSizeMeters, const std::size_t maximumPointCount)
    : initialVoxelSizeMeters_(initialVoxelSizeMeters),
      voxelSizeMeters_(initialVoxelSizeMeters),
      maximumPointCount_(maximumPointCount) {
  if (!std::isfinite(initialVoxelSizeMeters) || initialVoxelSizeMeters <= 0.0F || maximumPointCount == 0) {
    throw std::invalid_argument("Invalid adaptive point map limits");
  }
  points_.reserve(maximumPointCount_);
  voxels_.reserve(static_cast<qsizetype>(maximumPointCount_));
}

void AdaptivePointMap::clear() {
  points_.clear();
  voxels_.clear();
  voxelSizeMeters_ = initialVoxelSizeMeters_;
  compactionCount_ = 0;
}

void AdaptivePointMap::insert(const std::vector<QVector3D>& points) {
  for (const auto& point : points) {
    if (!finitePoint(point)) {
      continue;
    }
    while (points_.size() >= maximumPointCount_) {
      compact();
    }
    const auto key = voxelKey(point);
    if (!key || voxels_.contains(*key)) {
      continue;
    }
    voxels_.insert(*key);
    points_.push_back(point);
  }
}

const std::vector<QVector3D>& AdaptivePointMap::points() const noexcept { return points_; }

std::size_t AdaptivePointMap::size() const noexcept { return points_.size(); }

std::size_t AdaptivePointMap::capacity() const noexcept { return maximumPointCount_; }

float AdaptivePointMap::voxelSizeMeters() const noexcept { return voxelSizeMeters_; }

std::size_t AdaptivePointMap::compactionCount() const noexcept { return compactionCount_; }

std::optional<quint64> AdaptivePointMap::voxelKey(const QVector3D& point) const {
  const auto coordinate = [this](const float value) {
    return static_cast<qint64>(std::floor(static_cast<double>(value) / voxelSizeMeters_));
  };
  const auto x = coordinate(point.x());
  const auto y = coordinate(point.y());
  const auto z = coordinate(point.z());
  if (x < -voxelCoordinateBias || x >= voxelCoordinateBias || y < -voxelCoordinateBias ||
      y >= voxelCoordinateBias || z < -voxelCoordinateBias || z >= voxelCoordinateBias) {
    return std::nullopt;
  }
  const auto packedX = static_cast<quint64>(x + voxelCoordinateBias) & voxelCoordinateMask;
  const auto packedY = static_cast<quint64>(y + voxelCoordinateBias) & voxelCoordinateMask;
  const auto packedZ = static_cast<quint64>(z + voxelCoordinateBias) & voxelCoordinateMask;
  return (packedX << 42U) | (packedY << 21U) | packedZ;
}

void AdaptivePointMap::compact() {
  voxelSizeMeters_ *= 2.0F;
  ++compactionCount_;
  QSet<quint64> compactedVoxels;
  compactedVoxels.reserve(static_cast<qsizetype>(maximumPointCount_));
  std::vector<QVector3D> compactedPoints;
  compactedPoints.reserve(maximumPointCount_);
  for (const auto& point : points_) {
    const auto key = voxelKey(point);
    if (!key || compactedVoxels.contains(*key)) {
      continue;
    }
    compactedVoxels.insert(*key);
    compactedPoints.push_back(point);
  }
  voxels_ = std::move(compactedVoxels);
  points_ = std::move(compactedPoints);
}

}  // namespace drone_agricole::core
