#include "drone_agricole_px4_bridge/Frames.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace drone_agricole::px4 {
namespace {

Quaternion multiply(const Quaternion& left, const Quaternion& right) {
  const auto [lw, lx, ly, lz] = left;
  const auto [rw, rx, ry, rz] = right;
  return {lw * rw - lx * rx - ly * ry - lz * rz,
          lw * rx + lx * rw + ly * rz - lz * ry,
          lw * ry - lx * rz + ly * rw + lz * rx,
          lw * rz + lx * ry - ly * rx + lz * rw};
}

Quaternion normalized(const Quaternion& source) {
  if (!std::all_of(source.begin(), source.end(), [](const auto value) { return std::isfinite(value); })) {
    throw std::invalid_argument("quaternion PX4 invalide");
  }
  const auto norm = std::sqrt(source[0] * source[0] + source[1] * source[1] + source[2] * source[2] +
                              source[3] * source[3]);
  if (norm < 1.0e-12) {
    throw std::invalid_argument("quaternion PX4 de norme nulle");
  }
  Quaternion result{source[0] / norm, source[1] / norm, source[2] / norm, source[3] / norm};
  if (result[0] < 0.0) {
    for (auto& value : result) {
      value = -value;
    }
  }
  return result;
}

Vector3 rotateWorldToBody(const Quaternion& bodyToWorld, const Vector3& vector) {
  const auto quaternion = normalized(bodyToWorld);
  const Quaternion conjugate{quaternion[0], -quaternion[1], -quaternion[2], -quaternion[3]};
  const auto rotated = multiply(multiply(conjugate, {0.0, vector[0], vector[1], vector[2]}), quaternion);
  return {rotated[1], rotated[2], rotated[3]};
}

}  // namespace

Vector3 nedToEnu(const Vector3& vector) { return {vector[1], vector[0], -vector[2]}; }

Vector3 frdToFlu(const Vector3& vector) { return {vector[0], -vector[1], -vector[2]}; }

Quaternion px4QuaternionToRosWxyz(const Quaternion& quaternion) {
  constexpr auto sqrtHalf = 0.7071067811865475244;
  const Quaternion enuFromNed{0.0, sqrtHalf, sqrtHalf, 0.0};
  const Quaternion frdFromFlu{0.0, 1.0, 0.0, 0.0};
  return normalized(multiply(multiply(enuFromNed, normalized(quaternion)), frdFromFlu));
}

std::array<double, 4> px4QuaternionToRosXyzw(const Quaternion& quaternion) {
  const auto result = px4QuaternionToRosWxyz(quaternion);
  return {result[1], result[2], result[3], result[0]};
}

Vector3 nedVelocityToBodyFlu(const Quaternion& orientationPx4, const Vector3& velocityNed) {
  return rotateWorldToBody(px4QuaternionToRosWxyz(orientationPx4), nedToEnu(velocityNed));
}

}  // namespace drone_agricole::px4
