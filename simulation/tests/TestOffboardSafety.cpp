#include "drone_agricole_px4_bridge/OffboardSafety.hpp"

#include <iostream>
#include <limits>
#include <stdexcept>

using namespace drone_agricole::px4;

namespace {
void check(const bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
}

int main() {
  try {
    int refused = 0;
    try { requireOffboardAuthorization(false, "1"); } catch (const std::runtime_error&) { ++refused; }
    try { requireOffboardAuthorization(true, ""); } catch (const std::runtime_error&) { ++refused; }
    try { requireOffboardAuthorization(true, "true"); } catch (const std::runtime_error&) { ++refused; }
    check(refused == 3, "execute and SITL environment locks must both be explicit");
    requireOffboardAuthorization(true, "1");
    check(expiredOffboardDeadline("arming", 9.9, 9.9) == OffboardDeadline::None, "arming before deadline");
    check(expiredOffboardDeadline("arming", 10.0, 10.0) == OffboardDeadline::Arming,
          "arming deadline must take precedence over command retry");
    check(expiredOffboardDeadline("mission_stage", 100.0, 1.0) == OffboardDeadline::Global, "global deadline");
    check(expiredOffboardDeadline("landing", 120.0, 34.9) == OffboardDeadline::None,
          "global deadline allows bounded landing grace");
    check(expiredOffboardDeadline("landing", 135.0, 35.0) == OffboardDeadline::Landing,
          "LAND retries cannot reset landing deadline");
    check(landingConfirmed(true, false, 0.2, 0.2), "fresh landed and disarmed confirms landing");
    check(!landingConfirmed(true, true, 0.1, 0.1), "armed does not confirm landing");
    check(!landingConfirmed(false, false, 0.1, 0.1), "disarmed alone does not confirm landing");
    check(!landingConfirmed(true, false, 1.0, 0.1), "stale land flag rejected");
    check(!landingConfirmed(true, false, 0.1, 1.0), "stale status rejected");
    check(!landingConfirmed(true, false, std::numeric_limits<double>::quiet_NaN(), 0.1), "invalid age rejected");
    check(offboardTelemetryFresh(0.1, 0.1), "fresh status and odometry accepted");
    check(offboardTelemetryFresh(0.0, 0.0), "zero receive ages accepted");
    check(!offboardTelemetryFresh(1.0, 0.1), "status freshness boundary rejected");
    check(!offboardTelemetryFresh(0.1, 0.5), "odometry freshness boundary rejected");
    for (const double age : {-0.1, std::numeric_limits<double>::quiet_NaN(),
                              std::numeric_limits<double>::infinity()}) {
      check(!offboardTelemetryFresh(age, 0.1), "invalid status age rejected");
      check(!offboardTelemetryFresh(0.1, age), "invalid odometry age rejected");
    }
    for (const auto* state : {"warmup", "arming", "mission_stage", "hover"}) {
      check(requiresLiveOffboardTelemetry(state), "live telemetry required before each Offboard publication");
    }
    for (const auto* state : {"waiting_for_data", "failsafe_gap", "landing"}) {
      check(!requiresLiveOffboardTelemetry(state), "landing and loss observation retain their own guards");
    }
    requireBoundedOffboardParameter(2.0, 0.5, 10.0, "altitude");
    int rejected = 0;
    for (const double value : {-1.0, 10.1, std::numeric_limits<double>::infinity(),
                                std::numeric_limits<double>::quiet_NaN()}) {
      try { requireBoundedOffboardParameter(value, 0.5, 10.0, "altitude"); }
      catch (const std::invalid_argument&) { ++rejected; }
    }
    check(rejected == 4, "direct ROS parameters must reject non-finite and out-of-range values");
    check(classifyOffboardResult(false, 0, true, true, true) == OffboardResultState::Completed, "success finalization");
    check(classifyOffboardResult(true, 1, true, false, true) == OffboardResultState::Cancelled, "confirmed cancellation");
    check(classifyOffboardResult(true, 1, true, false, false) == OffboardResultState::Failed, "unconfirmed cancel rejected");
    check(classifyOffboardResult(true, 137, true, false, true) == OffboardResultState::Failed, "crashed cancellation rejected");
    check(classifyOffboardResult(false, 0, false, true, true) == OffboardResultState::Failed, "missing result rejected");
    check(classifyOffboardResult(false, 0, true, true, false) == OffboardResultState::Failed, "unconfirmed success rejected");
    check(classifyOffboardResult(false, 1, true, true, true) == OffboardResultState::Failed, "failed process rejected");
    std::cout << "Offboard safety: authorization, deadlines, freshness, parameters and finalization checks passed\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
