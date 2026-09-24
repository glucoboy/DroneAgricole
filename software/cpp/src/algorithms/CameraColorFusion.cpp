#include "drone_agricole/algorithms/CameraColorFusion.hpp"
#include <QQuaternion>
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace drone_agricole::algorithms {
namespace {
struct Projection { int pixel{-1}; double depth{0}; };
bool finite(double value) { return std::isfinite(value); }
void validate(const CameraBand& band) {
  const auto& c = band.camera;
  if (band.width <= 0 || band.height <= 0 || band.width > 16384 || band.height > 16384 ||
      band.pixels.size() != static_cast<std::size_t>(band.width) * band.height ||
      !finite(c.focalPixels) || c.focalPixels <= 0 || !finite(c.principalX) || !finite(c.principalY) ||
      !std::all_of(c.translation.begin(), c.translation.end(), finite) ||
      !std::all_of(c.distortion.begin(), c.distortion.end(), finite) ||
      !std::all_of(c.quaternion.begin(), c.quaternion.end(), finite))
    throw std::invalid_argument("Image ou calibration RGB invalide");
  double norm = 0;
  for (const auto q : c.quaternion) norm += q * q;
  if (!finite(norm) || norm < 1e-12) throw std::invalid_argument("Quaternion RGB invalide");
}
Projection project(const QVector3D& point, const CameraBand& band, const QQuaternion& rotation) {
  const auto& c = band.camera;
  const auto p = rotation.rotatedVector(point);
  const double z = p.z() + c.translation[2];
  if (!finite(z) || z <= 0.05) return {};
  const double x = (p.x() + c.translation[0]) / z, y = (p.y() + c.translation[1]) / z;
  const double r2 = x*x + y*y;
  const auto& d = c.distortion;
  const double radial = 1 + d[0]*r2 + d[1]*r2*r2 + d[2]*r2*r2*r2;
  const double u = c.focalPixels * (x*radial + 2*d[3]*x*y + d[4]*(r2+2*x*x)) + c.principalX;
  const double v = c.focalPixels * (y*radial + d[3]*(r2+2*y*y) + 2*d[4]*x*y) + c.principalY;
  if (!finite(u) || !finite(v) || u < 0 || v < 0 || u > band.width-1 || v > band.height-1) return {};
  return {static_cast<int>(std::lround(v))*band.width + static_cast<int>(std::lround(u)), z};
}
std::pair<double, double> range(const CameraBand& band) {
  auto samples = band.pixels;
  std::sort(samples.begin(), samples.end());
  return {samples[(samples.size()-1)*2/100], samples[(samples.size()-1)*98/100]};
}
} // namespace

CameraColorCloud fuseCameraRgb(const QList<QVector3D>& points, const std::array<CameraBand, 3>& rgb) {
  std::array<std::vector<Projection>, 3> projections;
  std::array<std::vector<double>, 3> depth;
  std::array<std::pair<double, double>, 3> ranges;
  for (std::size_t b = 0; b < 3; ++b) {
    const auto& band = rgb[b];
    validate(band);
    ranges[b] = range(band);
    const auto& q = band.camera.quaternion;
    const auto rotation = QQuaternion(q[3], q[0], q[1], q[2]).normalized();
    depth[b].assign(band.pixels.size(), std::numeric_limits<double>::infinity());
    projections[b].reserve(points.size());
    for (const auto& point : points) {
      const auto p = project(point, band, rotation);
      projections[b].push_back(p);
      if (p.pixel >= 0) depth[b][p.pixel] = std::min(depth[b][p.pixel], p.depth);
    }
  }
  CameraColorCloud result;
  for (qsizetype i = 0; i < points.size(); ++i) {
    std::array<int, 3> channels{};
    bool visible = true;
    for (std::size_t b = 0; b < 3; ++b) {
      const auto p = projections[b][i];
      // Tolérance locale de 5 cm, préliminaire ; pas de couleur à travers une surface mesurée.
      if (p.pixel < 0 || p.depth > depth[b][p.pixel] + 0.05) { visible = false; break; }
      const auto [low, high] = ranges[b];
      const double raw = rgb[b].pixels[p.pixel];
      const double value = high > low ? (raw-low)/(high-low) : raw/65535.0;
      channels[b] = static_cast<int>(std::lround(255*std::sqrt(std::clamp(value, 0.0, 1.0))));
    }
    if (visible) {
      result.points.append(points[i]);
      result.colors.append(QColor(channels[0], channels[1], channels[2]));
    }
  }
  return result;
}
} // namespace drone_agricole::algorithms
