#include "drone_agricole_px4_bridge/OffboardPlan.hpp"

#include <gtest/gtest.h>

#include <stdexcept>

using namespace drone_agricole::px4;

TEST(Px4OffboardPlan, Square) {
  const auto mission = squareMissionNed({10.0, -2.0, 0.5}, 2.0, 3.0);
  ASSERT_EQ(mission.size(), 5U);
  EXPECT_EQ(mission.front().name, "takeoff");
  EXPECT_EQ(mission.back().name, "leg_west");
  EXPECT_EQ(mission.front().targetNed, (Vector3{10.0, -2.0, -1.5}));
  EXPECT_EQ(mission[2].targetNed, (Vector3{13.0, 1.0, -1.5}));
  EXPECT_THROW(squareMissionNed({0.0, 0.0, 0.0}, 0.1, 2.0), std::invalid_argument);
  EXPECT_THROW(squareMissionNed({0.0, 0.0, 0.0}, 2.0, 30.0), std::invalid_argument);
}
