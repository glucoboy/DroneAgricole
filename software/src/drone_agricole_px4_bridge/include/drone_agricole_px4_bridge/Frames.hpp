#pragma once

#include <array>

namespace drone_agricole::px4 {

using Vector3 = std::array<double, 3>;
using Quaternion = std::array<double, 4>;  // w, x, y, z

[[nodiscard]] Vector3 nedToEnu(const Vector3& vector);
[[nodiscard]] Vector3 frdToFlu(const Vector3& vector);
[[nodiscard]] Quaternion px4QuaternionToRosWxyz(const Quaternion& quaternion);
[[nodiscard]] std::array<double, 4> px4QuaternionToRosXyzw(const Quaternion& quaternion);
[[nodiscard]] Vector3 nedVelocityToBodyFlu(const Quaternion& orientationPx4, const Vector3& velocityNed);

}  // namespace drone_agricole::px4
