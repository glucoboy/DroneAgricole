#include "drone_agricole_px4_bridge/Frames.hpp"

#include <gtest/gtest.h>

#include <cmath>
#include <stdexcept>

using namespace drone_agricole::px4;

TEST(Px4Frames, Vectors) {
  EXPECT_EQ(nedToEnu({1.0, 2.0, 3.0}), (Vector3{2.0, 1.0, -3.0}));
  EXPECT_EQ(frdToFlu({1.0, 2.0, 3.0}), (Vector3{1.0, -2.0, -3.0}));
}

TEST(Px4Frames, QuaternionsAndVelocity) {
  const auto north = px4QuaternionToRosXyzw({1.0, 0.0, 0.0, 0.0});
  const auto half = std::sqrt(0.5);
  EXPECT_NEAR(north[2], half, 1.0e-12);
  EXPECT_NEAR(north[3], half, 1.0e-12);
  const auto east = px4QuaternionToRosXyzw({half, 0.0, 0.0, half});
  EXPECT_NEAR(east[2], 0.0, 1.0e-12);
  EXPECT_NEAR(east[3], 1.0, 1.0e-12);
  const auto velocity = nedVelocityToBodyFlu({1.0, 0.0, 0.0, 0.0}, {3.0, 0.0, 0.0});
  EXPECT_NEAR(velocity[0], 3.0, 1.0e-12);
  EXPECT_NEAR(velocity[1], 0.0, 1.0e-12);
  EXPECT_THROW(static_cast<void>(px4QuaternionToRosXyzw({0.0, 0.0, 0.0, 0.0})), std::invalid_argument);
}
