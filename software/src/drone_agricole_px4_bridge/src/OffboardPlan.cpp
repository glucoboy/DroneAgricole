#include "drone_agricole_px4_bridge/OffboardPlan.hpp"

#include <stdexcept>

namespace drone_agricole::px4 {

std::vector<MissionStage> squareMissionNed(const Vector3& origin, const double altitude, const double leg) {
  if (altitude < 0.5 || altitude > 10.0) {
    throw std::invalid_argument("l'altitude d'essai doit être comprise entre 0,5 et 10 m");
  }
  if (leg < 0.5 || leg > 20.0) {
    throw std::invalid_argument("le côté du carré doit être compris entre 0,5 et 20 m");
  }
  const auto down = origin[2] - altitude;
  return {{"takeoff", {origin[0], origin[1], down}},
          {"leg_north", {origin[0] + leg, origin[1], down}},
          {"leg_east", {origin[0] + leg, origin[1] + leg, down}},
          {"leg_south", {origin[0], origin[1] + leg, down}},
          {"leg_west", {origin[0], origin[1], down}}};
}

}  // namespace drone_agricole::px4
