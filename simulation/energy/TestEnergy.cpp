#include "EnergyModel.hpp"
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace cartographe::energy;
namespace {
int checks=0;
void check(bool ok,const char* what) {++checks;if(!ok)throw std::runtime_error(what);}
template<typename F>void rejects(F f,const char* what){bool rejected=false;try{f();}catch(const std::invalid_argument&){rejected=true;}check(rejected,what);}
Configuration fixture(){
 Configuration c;c.reference_voltage_v=22.2;
 c.propulsion={{8.1395195,79.92,3900},{11.2776475,130.98,4600},{14.0235095,173.16,5100},{16.5732385,224.22,5600},{18.828768,264.18,6000}};
 c.auxiliaries={{"all_avionics",75,.8}};
 c.battery={20,.9,.02,.005,.2,19.2,100,{{0,19.2},{.2,21.6},{.5,22.8},{1,25.2}}};return c;
}
Scenario scenario(){return {"test",6,1,1,2400,{{"hover",2400,1}}};}
}
int main(){try{
 auto c=fixture();auto s=scenario();validate(c,s);
 auto e=solveElectrical(c.battery,1,800);
 check(e.feasible&&e.bus_voltage_v<25.2,"loaded voltage drop");
 check(std::abs(e.current_a*e.bus_voltage_v-800)<1e-8,"constant power root");
 check(std::abs(e.current_a*25.2-800-e.pack_loss_w-e.path_loss_w)<1e-8,"source/bus/loss conservation");
 c.battery.pack_resistance_ohm=0;c.battery.path_resistance_ohm=0;e=solveElectrical(c.battery,1,800);
 check(std::abs(e.current_a-800/25.2)<1e-12,"zero resistance");
 c=fixture();auto result=simulate(c,s);
 check(result.finalized&&result.reason==EndReason::ReserveReached,"hover reaches configured reserve");
 check(std::abs(result.final_soc-.2)<1e-10,"reserve exact event");
 check(std::abs(result.consumed_ah-14.4)<1e-8,"usable capacity and reserve");
 double sum=0;for(auto& p:result.phases)sum+=p.propulsion_wh+p.auxiliary_wh;
 check(std::abs(sum-result.bus_energy_wh)<1e-8,"phase energy accounting");
 check(result.samples.front().auxiliary_w==93.75,"auxiliary DC conversion counted once");
 s.phases={{"mission",10,1}};result=simulate(c,s);
 check(result.reason==EndReason::MissionCompleted&&result.completed,"bounded mission finalized");
 s.phases={{"hover",2400,1}};result=simulate(c,s,[](double t){return t>=3;});
 check(result.finalized&&!result.completed&&result.reason==EndReason::Cancelled&&result.elapsed_s==3,"cancelled result finalized distinctly");
 s.initial_soc=.2;check(simulate(c,s).reason==EndReason::ReserveReached,"initial reserve refusal");
 s=scenario();s.mass_kg=8;check(simulate(c,s).reason==EndReason::ThrustSaturation,"upper calibration/saturation refusal");
 s.mass_kg=1;check(simulate(c,s).reason==EndReason::OutsideCalibration,"lower calibration refusal");
 s=scenario();c.battery.minimum_bus_voltage_v=26;check(simulate(c,s).reason==EndReason::UnderVoltage,"under voltage event");
 c=fixture();c.battery.maximum_current_a=1;check(simulate(c,s).reason==EndReason::OverCurrent,"current bound event");
 c=fixture();c.battery.pack_resistance_ohm=1;check(simulate(c,s).reason==EndReason::PowerInfeasible,"constant power collapse refusal");
 c=fixture();s.maximum_duration_s=2;check(simulate(c,s).reason==EndReason::TimeLimit,"hard time bound");
 s=scenario();s.phases={{"avionics_only",2,0}};result=simulate(c,s);check(result.samples[0].propulsion_w==0&&result.bus_energy_wh>0,"motors off auxiliary accounting");
 c=fixture();s=scenario();s.time_step_s=0;rejects([&]{simulate(c,s);},"zero step");
 s=scenario();s.initial_soc=1.1;rejects([&]{simulate(c,s);},"invalid SoC");
 s=scenario();c.auxiliaries.push_back(c.auxiliaries.front());rejects([&]{simulate(c,s);},"duplicate auxiliary rejects double counting");
 c=fixture();c.auxiliaries[0].efficiency=0;rejects([&]{simulate(c,s);},"zero efficiency");
 c=fixture();c.propulsion[1].thrust_n=c.propulsion[0].thrust_n;rejects([&]{simulate(c,s);},"non monotone calibration");
 c=fixture();c.battery.ocv[0].soc=.1;rejects([&]{simulate(c,s);},"incomplete OCV");
 c=fixture();s.mass_kg=std::numeric_limits<double>::quiet_NaN();rejects([&]{simulate(c,s);},"non finite mass");
 c=fixture();auto observed=observeRotors(c,{1,0,0,0},{5100,5100,5100,5100},1);
 check(!observed.stop_requested&&std::abs(observed.propulsion_dc_power_w-4*173.16)<1e-10,"observed RPM to DC power");
 check(observed.state.soc<1&&observed.state.elapsed_s==1&&observed.electrical.bus_voltage_v>0,"observer battery snapshot");
 check(observeRotors(c,{1,0,0,0},{6100,5100,5100,5100},1).stop_reason==EndReason::OutsideCalibration,"observer RPM domain refusal");
 rejects([&]{observeRotors(c,{1,0,0,0},{5100,5100},1);},"observer missing rotor");
 rejects([&]{observeRotors(c,{1,0,0,0},{-1,5100,5100,5100},1);},"observer RPM sign conversion explicit");
 check(std::abs(jointVelocityToRpm(2*3.14159265358979323846,10)-600)<1e-10,"Gazebo slowdown restored in physical RPM");
 check(std::abs(jointVelocityToRpm(-2*3.14159265358979323846,10)-600)<1e-10,"CW joint speed magnitude");
 rejects([&]{jointVelocityToRpm(1,0);},"invalid simulation slowdown");
 std::cout<<"PASS "<<checks<<" energy model checks\n";return 0;
 }catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
