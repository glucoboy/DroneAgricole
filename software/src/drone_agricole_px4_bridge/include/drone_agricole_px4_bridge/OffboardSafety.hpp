#pragma once

#include <cmath>
#include <stdexcept>
#include <string>

namespace drone_agricole::px4 {

// Wall-clock budgets for the SITL runner, independent of ROS time and of
// repeated mode/LAND requests. A landing timeout never confirms a landing.
struct OffboardDeadlines {
  double globalSeconds{100.0};
  double armingSeconds{10.0};
  double landingSeconds{35.0};
  double waitingDataSeconds{12.0};
};

enum class OffboardDeadline { None, Global, Arming, Landing };

inline void requireOffboardAuthorization(const bool execute, const std::string& sitlEnvironment) {
  if (!execute) throw std::runtime_error("Essai refusé : execute:=true est requis.");
  if (sitlEnvironment != "1") throw std::runtime_error("Essai refusé : le verrou d'environnement SITL est absent.");
}

inline OffboardDeadline expiredOffboardDeadline(const std::string& state,
                                                const double totalSeconds,
                                                const double stateSeconds,
                                                const OffboardDeadlines& deadlines = {}) {
  if (state == "landing") {
    return stateSeconds >= deadlines.landingSeconds ? OffboardDeadline::Landing : OffboardDeadline::None;
  }
  if (totalSeconds >= deadlines.globalSeconds) return OffboardDeadline::Global;
  if (state == "arming" && stateSeconds >= deadlines.armingSeconds) return OffboardDeadline::Arming;
  return OffboardDeadline::None;
}

inline bool landingConfirmed(const bool landed, const bool armed,
                             const double landAgeSeconds, const double statusAgeSeconds) {
  return landed && !armed && std::isfinite(landAgeSeconds) && std::isfinite(statusAgeSeconds) &&
         landAgeSeconds >= 0.0 && statusAgeSeconds >= 0.0 && landAgeSeconds < 1.0 && statusAgeSeconds < 1.0;
}

inline bool offboardTelemetryFresh(const double statusAgeSeconds, const double odometryAgeSeconds) {
  return std::isfinite(statusAgeSeconds) && std::isfinite(odometryAgeSeconds) &&
         statusAgeSeconds >= 0.0 && odometryAgeSeconds >= 0.0 &&
         statusAgeSeconds < 1.0 && odometryAgeSeconds < 0.5;
}

inline bool requiresLiveOffboardTelemetry(const std::string& state) {
  return state == "warmup" || state == "arming" || state == "mission_stage" || state == "hover";
}

inline void requireBoundedOffboardParameter(const double value, const double minimum,
                                            const double maximum, const char* name) {
  if (!std::isfinite(value) || value < minimum || value > maximum) {
    throw std::invalid_argument(std::string(name) + " hors limites SITL");
  }
}

enum class OffboardResultState { Completed, Cancelled, Failed };

inline OffboardResultState classifyOffboardResult(const bool stopRequested, const int exitCode,
                                                  const bool resultPresent, const bool success,
                                                  const bool landingWasConfirmed) {
  if (!resultPresent || !landingWasConfirmed) return OffboardResultState::Failed;
  if (stopRequested) {
    return exitCode == 0 || exitCode == 1 ? OffboardResultState::Cancelled : OffboardResultState::Failed;
  }
  return exitCode == 0 && success ? OffboardResultState::Completed : OffboardResultState::Failed;
}

}  // namespace drone_agricole::px4
