#include "drone_agricole/core/BenchmarkTelemetry.hpp"

namespace drone_agricole::core {

class BenchmarkTelemetryPublisher::Impl {};

BenchmarkTelemetryPublisher::BenchmarkTelemetryPublisher() : impl_(std::make_unique<Impl>()) {}
BenchmarkTelemetryPublisher::~BenchmarkTelemetryPublisher() = default;
void BenchmarkTelemetryPublisher::publish(double, double, double, double) {}

}  // namespace drone_agricole::core
