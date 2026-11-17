#include "MassProperties.hpp"
#include <iostream>
using namespace cartographe::mass;
void need(bool b){if(!b)throw std::runtime_error("mass test failed");}
template<class F>void rejects(F f){bool thrown=false;try{f();}catch(const std::invalid_argument&){thrown=true;}need(thrown);}
int main(){
  Tensor unit=identity();Component a{"a","",1.,Vector{-1,0,0},unit},b{"b","",1.,Vector{1,0,0},unit};auto r=aggregate({a,b});need(r.complete&&r.knownMass==2&&(*r.centre)[0]==0&&std::abs((*r.inertia)[1][1]-4)<1e-10);
  Component child{"child","a",.5,Vector{},unit};r=aggregate({a,b,child});need(r.knownMass==2);
  auto unknown=b;unknown.kilograms.reset();r=aggregate({a,unknown});need(!r.complete&&!r.centre&&!r.inertia&&r.unknown.size()==1&&r.knownMass==1);
  auto missingDistribution=b;missingDistribution.centre.reset();missingDistribution.inertia.reset();r=aggregate({a,missingDistribution});need(r.massComplete&&!r.complete&&!r.centre&&r.knownMass==2&&r.unknownMass.empty()&&r.unknownDistribution.size()==1);
  Component unknownParent{"parent","",{},{},{}};Component knownChild{"child","parent",.25,{},{}};
  r=aggregate({unknownParent,knownChild});need(!r.massComplete&&r.knownMass==.25&&r.unknownMass.size()==1);
  auto missingTensor=b;missingTensor.inertia.reset();r=aggregate({a,missingTensor});need(r.massComplete&&r.centreComplete&&r.centre&&!r.inertia&&r.knownMass==2);
  auto zero=b;zero.kilograms=0.;rejects([&]{aggregate({zero});});
  auto invalid=b;invalid.kilograms=std::nan("");rejects([&]{aggregate({invalid});});
  rejects([&]{aggregate({a,a});});child.includedIn="absent";rejects([&]{aggregate({a,child});});a.includedIn="b";b.includedIn="a";rejects([&]{aggregate({a,b});});a.includedIn="";b.includedIn="";
  auto bad=unit;bad[0][0]=-1;rejects([&]{checkTensor(bad);});bad=unit;bad[0][0]=4;rejects([&]{checkTensor(bad);});bad=unit;bad[0][1]=.1;rejects([&]{checkTensor(bad);});a.rotation[0][0]=2;rejects([&]{aggregate({a});});a.rotation=identity();a.rotation[0][0]=-1;rejects([&]{aggregate({a});});
  // Rotation of diag(1,2,3) through 90 degrees exchanges x/y principal moments.
  a.rotation={{{0,-1,0},{1,0,0},{0,0,1}}};a.inertia=Tensor{{{1,0,0},{0,2,0},{0,0,3}}};r=aggregate({a});need(std::abs((*r.inertia)[0][0]-2)<1e-10&&std::abs((*r.inertia)[1][1]-1)<1e-10);
  std::cout<<"Mass properties: transport, rotation, inclusion, unknowns and negative cases passed\n";
}
