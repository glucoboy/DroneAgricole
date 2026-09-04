#pragma once

#include "drone_agricole_px4_bridge/Frames.hpp"

#include <string>
#include <vector>

namespace drone_agricole::px4 {

struct MissionStage {
  std::string name;
  Vector3 targetNed;
};

[[nodiscard]] std::vector<MissionStage> squareMissionNed(const Vector3& originNed,
                                                         double altitudeMeters,
                                                         double legMeters);

}  // namespace drone_agricole::px4
