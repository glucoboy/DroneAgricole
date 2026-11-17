#include "EnergyModel.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <stdexcept>

namespace cartographe::energy {
namespace {
constexpr double gravity = 9.80665;
bool finite(double x) { return std::isfinite(x); }
void require(bool condition, const char* message) { if (!condition) throw std::invalid_argument(message); }
double lerp(double x, double a, double b, double va, double vb) { return va + (vb-va)*(x-a)/(b-a); }
PropulsionPoint atThrust(const Configuration& c, double thrust) {
    for (std::size_t i=1; i<c.propulsion.size(); ++i) {
        const auto& lo=c.propulsion[i-1]; const auto& hi=c.propulsion[i];
        if (thrust<=hi.thrust_n) return {thrust, lerp(thrust,lo.thrust_n,hi.thrust_n,lo.dc_power_w,hi.dc_power_w), lerp(thrust,lo.thrust_n,hi.thrust_n,lo.rpm,hi.rpm)};
    }
    return c.propulsion.back();
}
}

void validate(const Configuration& c, const Scenario& s) {
    require(c.rotor_count==4,"rotor_count must be four for this prototype contract");
    require(finite(c.reference_voltage_v)&&c.reference_voltage_v>0,"invalid reference voltage");
    require(finite(c.propulsion_power_factor)&&c.propulsion_power_factor>0,"invalid propulsion power factor");
    require(c.propulsion.size()>=2,"propulsion curve requires at least two points");
    double t=0,p=0,r=0;
    for (const auto& x:c.propulsion) {
        require(finite(x.thrust_n)&&x.thrust_n>t&&finite(x.dc_power_w)&&x.dc_power_w>p&&finite(x.rpm)&&x.rpm>r,"propulsion curve must be finite positive and strictly increasing");
        t=x.thrust_n; p=x.dc_power_w; r=x.rpm;
    }
    std::set<std::string> loads;
    for (const auto& x:c.auxiliaries) require(!x.id.empty()&&loads.insert(x.id).second&&finite(x.useful_power_w)&&x.useful_power_w>=0&&finite(x.efficiency)&&x.efficiency>0&&x.efficiency<=1,"invalid or duplicate auxiliary branch");
    const auto& b=c.battery;
    require(finite(b.nominal_capacity_ah)&&b.nominal_capacity_ah>0&&finite(b.capacity_factor)&&b.capacity_factor>0&&b.capacity_factor<=1,"invalid usable capacity");
    require(finite(b.pack_resistance_ohm)&&b.pack_resistance_ohm>=0&&finite(b.path_resistance_ohm)&&b.path_resistance_ohm>=0,"invalid battery/path resistance");
    require(finite(b.reserve_soc)&&b.reserve_soc>=0&&b.reserve_soc<1,"invalid reserve");
    require(finite(b.minimum_bus_voltage_v)&&b.minimum_bus_voltage_v>0&&finite(b.maximum_current_a)&&b.maximum_current_a>0,"invalid electrical stopping bounds");
    require(b.ocv.size()>=2&&b.ocv.front().soc==0&&b.ocv.back().soc==1,"OCV must cover SoC zero through one");
    double q=-1,v=0;
    for (const auto& x:b.ocv) { require(finite(x.soc)&&x.soc>q&&x.soc>=0&&x.soc<=1&&finite(x.voltage_v)&&x.voltage_v>v,"invalid OCV table"); q=x.soc; v=x.voltage_v; }
    require(!s.id.empty()&&finite(s.mass_kg)&&s.mass_kg>0,"invalid scenario/mass");
    require(finite(s.initial_soc)&&s.initial_soc>=0&&s.initial_soc<=1,"invalid initial SoC");
    require(finite(s.time_step_s)&&s.time_step_s>0&&s.time_step_s<=5,"time step must be in (0,5] seconds");
    require(finite(s.maximum_duration_s)&&s.maximum_duration_s>0&&s.maximum_duration_s<=86400,"maximum duration must be in (0,86400] seconds");
    require(!s.phases.empty()&&s.phases.size()<=100,"invalid phase list");
    std::set<std::string> phases;
    for (const auto& x:s.phases) require(!x.id.empty()&&phases.insert(x.id).second&&finite(x.duration_s)&&x.duration_s>0&&finite(x.thrust_weight_ratio)&&x.thrust_weight_ratio>=0,"invalid or duplicate mission phase");
    require(s.maximum_duration_s/s.time_step_s<=1000000,"campaign sample budget exceeded");
}

double openCircuitVoltage(const Battery& b,double soc) {
    if (!finite(soc)||soc<0||soc>1||b.ocv.size()<2) throw std::invalid_argument("SoC/OCV outside declared domain");
    for (std::size_t i=1;i<b.ocv.size();++i) if (soc<=b.ocv[i].soc) return lerp(soc,b.ocv[i-1].soc,b.ocv[i].soc,b.ocv[i-1].voltage_v,b.ocv[i].voltage_v);
    return b.ocv.back().voltage_v;
}

ElectricalPoint solveElectrical(const Battery& b,double soc,double power) {
    require(finite(power)&&power>=0,"invalid DC load");
    require(finite(b.pack_resistance_ohm)&&b.pack_resistance_ohm>=0&&finite(b.path_resistance_ohm)&&b.path_resistance_ohm>=0,"invalid electrical resistance");
    const double voc=openCircuitVoltage(b,soc), resistance=b.pack_resistance_ohm+b.path_resistance_ohm;
    const double discriminant=voc*voc-4*resistance*power;
    if (discriminant<0) return {};
    const double current=power==0 ? 0 : 2*power/(voc+std::sqrt(discriminant));
    return {true,current,voc-current*resistance,current*current*b.pack_resistance_ohm,current*current*b.path_resistance_ohm};
}

Result simulate(const Configuration& c,const Scenario& s,const std::function<bool(double)>& cancelled) {
    validate(c,s);
    Result out;
    out.final_soc=s.initial_soc;
    out.minimum_voltage_v=openCircuitVoltage(c.battery,s.initial_soc);
    out.minimum_thrust_margin_n=std::numeric_limits<double>::infinity();
    const double capacity=c.battery.nominal_capacity_ah*c.battery.capacity_factor;
    double aux=0;
    for(const auto& x:c.auxiliaries) aux+=x.useful_power_w/x.efficiency;
    auto finish=[&](EndReason reason) {
        out.reason=reason; out.completed=reason==EndReason::MissionCompleted;
        out.finalized=true;
        if (!finite(out.minimum_thrust_margin_n)) out.minimum_thrust_margin_n=0;
        return out;
    };
    for(const auto& phase:s.phases) {
        out.phases.push_back({phase.id});
        auto& energy=out.phases.back();
        double phaseTime=0;
        while(phaseTime+1e-9<phase.duration_s) {
            if(cancelled&&cancelled(out.elapsed_s)) return finish(EndReason::Cancelled);
            if(out.final_soc<=c.battery.reserve_soc+1e-12) return finish(EndReason::ReserveReached);
            if(out.elapsed_s>=s.maximum_duration_s-1e-9) return finish(EndReason::TimeLimit);
            const double thrust=s.mass_kg*gravity*phase.thrust_weight_ratio/static_cast<double>(c.rotor_count);
            if (thrust>c.propulsion.back().thrust_n+1e-12) {
                out.minimum_thrust_margin_n=std::min(out.minimum_thrust_margin_n,c.propulsion.back().thrust_n-thrust);
                ++out.saturation_count;return finish(EndReason::ThrustSaturation);
            }
            if (thrust>0&&thrust<c.propulsion.front().thrust_n) return finish(EndReason::OutsideCalibration);
            const auto operating=thrust==0 ? PropulsionPoint{} : atThrust(c,thrust);
            const double propulsion=operating.dc_power_w*static_cast<double>(c.rotor_count)*c.propulsion_power_factor;
            const auto electrical=solveElectrical(c.battery,out.final_soc,propulsion+aux);
            if(!electrical.feasible) return finish(EndReason::PowerInfeasible);
            out.minimum_voltage_v=std::min(out.minimum_voltage_v,electrical.bus_voltage_v);
            out.maximum_current_a=std::max(out.maximum_current_a,electrical.current_a);
            const double ratio=electrical.bus_voltage_v/c.reference_voltage_v;
            const double ceiling=c.propulsion.back().thrust_n*std::min(1.0,ratio*ratio);
            const double margin=ceiling-thrust;
            out.minimum_thrust_margin_n=std::min(out.minimum_thrust_margin_n,margin);
            if(electrical.bus_voltage_v<c.battery.minimum_bus_voltage_v) return finish(EndReason::UnderVoltage);
            if(electrical.current_a>c.battery.maximum_current_a) return finish(EndReason::OverCurrent);
            if(thrust>0&&margin<0) { ++out.saturation_count; return finish(EndReason::ThrustSaturation); }
            double dt=std::min({s.time_step_s,phase.duration_s-phaseTime,s.maximum_duration_s-out.elapsed_s});
            if(electrical.current_a>0) dt=std::min(dt,(out.final_soc-c.battery.reserve_soc)*capacity*3600/electrical.current_a);
            out.samples.push_back({out.elapsed_s,dt,out.final_soc,electrical.bus_voltage_v,electrical.current_a,propulsion,aux,electrical.pack_loss_w,electrical.path_loss_w,thrust,operating.rpm,margin,phase.id});
            const double ah=electrical.current_a*dt/3600;
            out.final_soc=std::max(c.battery.reserve_soc,out.final_soc-ah/capacity);
            out.consumed_ah+=ah; out.elapsed_s+=dt; phaseTime+=dt;
            energy.duration_s+=dt;
            energy.propulsion_wh+=propulsion*dt/3600; energy.auxiliary_wh+=aux*dt/3600;
            energy.pack_loss_wh+=electrical.pack_loss_w*dt/3600; energy.path_loss_wh+=electrical.path_loss_w*dt/3600;
            out.bus_energy_wh+=(propulsion+aux)*dt/3600;
            out.pack_loss_wh+=electrical.pack_loss_w*dt/3600; out.path_loss_wh+=electrical.path_loss_w*dt/3600;
        }
    }
    return finish(EndReason::MissionCompleted);
}

double jointVelocityToRpm(double omega,double slowdown) {
    require(finite(omega)&&finite(slowdown)&&slowdown>0,"invalid joint velocity or Gazebo rotor slowdown");
    return std::abs(omega)*slowdown*60/(2*3.14159265358979323846);
}

ObserverSnapshot observeRotors(const Configuration& c,const ObserverState& previous,const std::vector<double>& rpm,double dt) {
    // Reuse all configuration validation, without acquiring any flight authority.
    validate(c,{"observer_contract",6,previous.soc,dt,dt,{{"observed",dt,0}}});
    require(rpm.size()==c.rotor_count,"observer requires exactly four rotor RPM values");
    require(finite(previous.elapsed_s)&&previous.elapsed_s>=0&&finite(previous.discharged_ah)&&previous.discharged_ah>=0&&finite(previous.bus_energy_wh)&&previous.bus_energy_wh>=0,"invalid observer history");
    ObserverSnapshot out;out.state=previous;
    for(double speed:rpm) {
        require(finite(speed)&&speed>=0,"observed RPM must be finite and nonnegative");
        if(speed==0) continue;
        if(speed<c.propulsion.front().rpm||speed>c.propulsion.back().rpm) {out.stop_requested=true;out.stop_reason=EndReason::OutsideCalibration;return out;}
        for(std::size_t i=1;i<c.propulsion.size();++i) if(speed<=c.propulsion[i].rpm) {
            const auto& lo=c.propulsion[i-1];const auto& hi=c.propulsion[i];
            out.propulsion_dc_power_w+=lerp(speed,lo.rpm,hi.rpm,lo.dc_power_w,hi.dc_power_w)*c.propulsion_power_factor;
            out.estimated_thrust_n+=lerp(speed,lo.rpm,hi.rpm,lo.thrust_n,hi.thrust_n);break;
        }
    }
    for(const auto& load:c.auxiliaries) out.auxiliary_dc_power_w+=load.useful_power_w/load.efficiency;
    const double power=out.propulsion_dc_power_w+out.auxiliary_dc_power_w;
    out.electrical=solveElectrical(c.battery,previous.soc,power);
    auto stop=[&](EndReason reason){out.stop_requested=true;out.stop_reason=reason;return out;};
    if(previous.soc<=c.battery.reserve_soc) return stop(EndReason::ReserveReached);
    if(!out.electrical.feasible) return stop(EndReason::PowerInfeasible);
    if(out.electrical.bus_voltage_v<c.battery.minimum_bus_voltage_v) return stop(EndReason::UnderVoltage);
    if(out.electrical.current_a>c.battery.maximum_current_a) return stop(EndReason::OverCurrent);
    const double capacity=c.battery.nominal_capacity_ah*c.battery.capacity_factor;
    double integratedDt=dt;
    if(out.electrical.current_a>0) integratedDt=std::min(dt,(previous.soc-c.battery.reserve_soc)*capacity*3600/out.electrical.current_a);
    const double ah=out.electrical.current_a*integratedDt/3600;
    out.state={std::max(c.battery.reserve_soc,previous.soc-ah/capacity),previous.elapsed_s+integratedDt,previous.discharged_ah+ah,previous.bus_energy_wh+power*integratedDt/3600};
    if(out.state.soc<=c.battery.reserve_soc+1e-12) return stop(EndReason::ReserveReached);
    return out;
}

const char* name(EndReason reason) {
    switch(reason) {
    case EndReason::MissionCompleted:return "mission_completed";
    case EndReason::ReserveReached:return "reserve_reached";
    case EndReason::UnderVoltage:return "under_voltage";
    case EndReason::OverCurrent:return "over_current";
    case EndReason::PowerInfeasible:return "power_infeasible";
    case EndReason::ThrustSaturation:return "thrust_saturation";
    case EndReason::OutsideCalibration:return "outside_calibration";
    case EndReason::Cancelled:return "cancelled";
    case EndReason::TimeLimit:return "time_limit";
    }
    return "invalid";
}
} // namespace cartographe::energy
