#pragma once

#include <QColor>
#include <QList>
#include <QVector3D>
#include <array>
#include <vector>

namespace drone_agricole::algorithms {

// Convention explicite : p_camera = R_camera_lidar * p_lidar + t_camera_lidar.
struct ProjectionCamera {
  double focalPixels{0}, principalX{0}, principalY{0};
  std::array<double, 5> distortion{}; // k1, k2, k3, p1, p2
  std::array<double, 3> translation{};
  std::array<double, 4> quaternion{0, 0, 0, 1}; // x, y, z, w
};
struct CameraBand {
  int width{0}, height{0};
  std::vector<quint16> pixels;
  ProjectionCamera camera;
};
struct CameraColorCloud {
  QList<QVector3D> points;
  QList<QColor> colors;
};

// Composition visible à contraste étiré ; ce ne sont pas des réflectances calibrées.
[[nodiscard]] CameraColorCloud fuseCameraRgb(const QList<QVector3D>& points,
                                            const std::array<CameraBand, 3>& rgb);
} // namespace drone_agricole::algorithms
