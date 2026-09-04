#pragma once

#include <QSet>
#include <QVector3D>

#include <cstddef>
#include <optional>
#include <vector>

namespace drone_agricole::core {

class AdaptivePointMap final {
 public:
  AdaptivePointMap(float initialVoxelSizeMeters, std::size_t maximumPointCount);

  void clear();
  void insert(const std::vector<QVector3D>& points);

  [[nodiscard]] const std::vector<QVector3D>& points() const noexcept;
  [[nodiscard]] std::size_t size() const noexcept;
  [[nodiscard]] std::size_t capacity() const noexcept;
  [[nodiscard]] float voxelSizeMeters() const noexcept;
  [[nodiscard]] std::size_t compactionCount() const noexcept;

 private:
  float initialVoxelSizeMeters_;
  float voxelSizeMeters_;
  std::size_t maximumPointCount_;
  std::size_t compactionCount_{0};
  std::vector<QVector3D> points_;
  QSet<quint64> voxels_;

  [[nodiscard]] std::optional<quint64> voxelKey(const QVector3D& point) const;
  void compact();
};

}  // namespace drone_agricole::core
