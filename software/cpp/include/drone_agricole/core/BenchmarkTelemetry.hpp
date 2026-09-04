#pragma once

#include <memory>

namespace drone_agricole::core {

class BenchmarkTelemetryPublisher final {
 public:
  BenchmarkTelemetryPublisher();
  ~BenchmarkTelemetryPublisher();

  BenchmarkTelemetryPublisher(const BenchmarkTelemetryPublisher&) = delete;
  BenchmarkTelemetryPublisher& operator=(const BenchmarkTelemetryPublisher&) = delete;

  void publish(double expectedDurationSeconds,
               double cpuPercentOneCore,
               double cpuTotalSeconds,
               double memoryRssMib);

 private:
  class Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace drone_agricole::core
