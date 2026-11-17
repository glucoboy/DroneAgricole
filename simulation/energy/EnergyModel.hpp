#pragma once

#include <cstddef>
#include <functional>
#include <string>
#include <vector>

namespace cartographe::energy {

struct PropulsionPoint { double thrust_n{}, dc_power_w{}, rpm{}; };
struct OcvPoint { double soc{}, voltage_v{}; };
struct AuxiliaryLoad { std::string id; double useful_power_w{}, efficiency{}; };
struct Battery {
    double nominal_capacity_ah{}, capacity_factor{};
    double pack_resistance_ohm{}, path_resistance_ohm{};
    double reserve_soc{}, minimum_bus_voltage_v{}, maximum_current_a{};
    std::vector<OcvPoint> ocv;
};
struct Configuration {
    std::size_t rotor_count{4};
    double reference_voltage_v{}, propulsion_power_factor{1.0};
    std::vector<PropulsionPoint> propulsion;
    std::vector<AuxiliaryLoad> auxiliaries;
    Battery battery;
};
struct Phase { std::string id; double duration_s{}, thrust_weight_ratio{}; };
struct Scenario {
    std::string id;
    double mass_kg{}, initial_soc{}, time_step_s{}, maximum_duration_s{};
    std::vector<Phase> phases;
};
struct ElectricalPoint { bool feasible{}; double current_a{}, bus_voltage_v{}, pack_loss_w{}, path_loss_w{}; };
struct Sample {
    double time_s{}, duration_s{}, soc{}, voltage_v{}, current_a{};
    double propulsion_w{}, auxiliary_w{}, pack_loss_w{}, path_loss_w{};
    double thrust_per_rotor_n{}, rpm{}, thrust_margin_n{};
    std::string phase;
};
struct PhaseEnergy { std::string id; double duration_s{}, propulsion_wh{}, auxiliary_wh{}, pack_loss_wh{}, path_loss_wh{}; };
enum class EndReason { MissionCompleted, ReserveReached, UnderVoltage, OverCurrent, PowerInfeasible, ThrustSaturation, OutsideCalibration, Cancelled, TimeLimit };
struct Result {
    EndReason reason{EndReason::TimeLimit};
    bool completed{}, finalized{};
    double elapsed_s{}, final_soc{}, consumed_ah{}, bus_energy_wh{}, pack_loss_wh{}, path_loss_wh{};
    double minimum_voltage_v{}, maximum_current_a{}, minimum_thrust_margin_n{};
    std::size_t saturation_count{};
    std::vector<PhaseEnergy> phases;
    std::vector<Sample> samples;
};
struct ObserverState { double soc{}, elapsed_s{}, discharged_ah{}, bus_energy_wh{}; };
struct ObserverSnapshot {
    ObserverState state;
    ElectricalPoint electrical;
    double propulsion_dc_power_w{}, auxiliary_dc_power_w{}, estimated_thrust_n{};
    bool stop_requested{};
    EndReason stop_reason{EndReason::TimeLimit};
};

// DC power is measured upstream of the reference motor/ESC chain. Do not add
// another motor or ESC efficiency. Only separately declared auxiliaries and
// pack/path I^2R losses are added. Voltage-dependent thrust ceiling is an
// explicit V^2 proxy, bounded above by the last reference curve point.
void validate(const Configuration& config, const Scenario& scenario);
double openCircuitVoltage(const Battery& battery, double soc);
ElectricalPoint solveElectrical(const Battery& battery, double soc, double bus_power_w);
Result simulate(const Configuration& config, const Scenario& scenario,
                const std::function<bool(double)>& cancelled = {});
// Pure observer contract for a future Gazebo adapter. RPM inputs are observed
// joint speeds converted by jointVelocityToRpm(omega, slowdown); current SDF
// rotorVelocitySlowdownSim=10 means abs(omega_joint)*10*60/(2*pi). It commands no
// motors and publishes no PX4 battery. No Gazebo/MAVLink adapter is installed.
ObserverSnapshot observeRotors(const Configuration& config, const ObserverState& previous,
                              const std::vector<double>& measured_rpm, double dt_s);
double jointVelocityToRpm(double joint_rad_per_s, double rotor_velocity_slowdown_sim);
const char* name(EndReason reason);

} // namespace cartographe::energy
