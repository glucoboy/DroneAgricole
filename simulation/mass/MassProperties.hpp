#pragma once
#include <array>
#include <cmath>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

namespace cartographe::mass {
using Vector=std::array<double,3>;
using Tensor=std::array<std::array<double,3>,3>;
inline Tensor identity(){return {{{1,0,0},{0,1,0},{0,0,1}}};}
struct Component {
    std::string id, includedIn;
    std::optional<double> kilograms;
    std::optional<Vector> centre;
    std::optional<Tensor> inertia;
    Tensor rotation{identity()}; // component axes -> common frame, CG already common frame
};
struct Aggregate {
    bool complete{}, massComplete{}, centreComplete{};
    std::vector<std::string> unknown, unknownMass, unknownDistribution;
    double knownMass{};
    std::optional<Vector> centre;
    std::optional<Tensor> inertia;
};
inline void checkTensor(Tensor a){
    for(int i=0;i<3;++i)for(int j=0;j<3;++j)
        if(!std::isfinite(a[i][j])||std::abs(a[i][j]-a[j][i])>1e-10)throw std::invalid_argument("inertia nonfinite/asymmetric");
    // Jacobi diagonalisation, then principal-moment triangle inequalities.
    for(int step=0;step<24;++step){int p=0,q=1;for(int i=0;i<3;++i)for(int j=i+1;j<3;++j)if(std::abs(a[i][j])>std::abs(a[p][q])){p=i;q=j;}
        if(std::abs(a[p][q])<1e-12)break;double angle=.5*std::atan2(2*a[p][q],a[q][q]-a[p][p]);double c=std::cos(angle),s=std::sin(angle);Tensor r=identity();r[p][p]=c;r[q][q]=c;r[p][q]=s;r[q][p]=-s;Tensor next{};for(int i=0;i<3;++i)for(int j=0;j<3;++j)for(int k=0;k<3;++k)for(int l=0;l<3;++l)next[i][j]+=r[k][i]*a[k][l]*r[l][j];a=next;}
    for(int i=0;i<3;++i){if(a[i][i]<-1e-10)throw std::invalid_argument("negative inertia");double other=0;for(int j=0;j<3;++j)if(i!=j)other+=a[j][j];if(a[i][i]>other+1e-9)throw std::invalid_argument("inertia triangle");}
}
inline Aggregate aggregate(const std::vector<Component>& components){
    std::map<std::string,const Component*> ids;
    for(const auto &c:components)if(c.id.empty()||!ids.emplace(c.id,&c).second)throw std::invalid_argument("duplicate/empty mass id");
    for(const auto &c:components){std::map<std::string,bool> seen;auto p=&c;while(!p->includedIn.empty()){if(!ids.count(p->includedIn)||seen[p->includedIn])throw std::invalid_argument("missing/cyclic mass inclusion");seen[p->includedIn]=true;p=ids.at(p->includedIn);}}
    Aggregate out;Vector weighted{};std::vector<const Component*> accepted;
    bool centres=true, tensors=true;
    for(const auto &c:components){
        if(c.kilograms&&(!std::isfinite(*c.kilograms)||*c.kilograms<=0))throw std::invalid_argument("invalid mass");
        if(c.centre)for(double v:*c.centre)if(!std::isfinite(v))throw std::invalid_argument("invalid centre");
        if(c.inertia)checkTensor(*c.inertia);
        for(int i=0;i<3;++i)for(int j=0;j<3;++j){double dot=0;for(int k=0;k<3;++k)dot+=c.rotation[k][i]*c.rotation[k][j];if(!std::isfinite(dot)||std::abs(dot-(i==j?1.:0.))>1e-9)throw std::invalid_argument("nonorthogonal rotation");}
        const auto&r=c.rotation;double det=r[0][0]*(r[1][1]*r[2][2]-r[1][2]*r[2][1])-r[0][1]*(r[1][0]*r[2][2]-r[1][2]*r[2][0])+r[0][2]*(r[1][0]*r[2][1]-r[1][1]*r[2][0]);if(std::abs(det-1)>1e-9)throw std::invalid_argument("improper rotation");
        // A known ancestor covers its descendants. If its own mass is still
        // unknown, known children remain useful in the partial subtotal.
        bool covered=false;
        for(auto parent=c.includedIn;!parent.empty();parent=ids.at(parent)->includedIn)
            if(ids.at(parent)->kilograms){covered=true;break;}
        if(covered)continue;
        if(!c.kilograms)out.unknownMass.push_back(c.id);
        if(!c.centre||!c.inertia)out.unknownDistribution.push_back(c.id);
        if(!c.kilograms||!c.centre||!c.inertia)out.unknown.push_back(c.id);
        centres=centres&&c.centre.has_value();tensors=tensors&&c.inertia.has_value();
        if(!c.kilograms)continue;
        const double m=*c.kilograms;out.knownMass+=m;
        if(c.centre)for(int i=0;i<3;++i)weighted[i]+=m*(*c.centre)[i];
        accepted.push_back(&c);
    }
    out.massComplete=out.unknownMass.empty()&&out.knownMass>0;
    out.centreComplete=out.massComplete&&centres;
    out.complete=out.centreComplete&&tensors;
    if(!out.centreComplete)return out;
    Vector cg{};for(int i=0;i<3;++i)cg[i]=weighted[i]/out.knownMass;
    out.centre=cg;if(!out.complete)return out;
    Tensor total{};
    for(auto c:accepted){Vector d{};double length=0;for(int i=0;i<3;++i){d[i]=(*c->centre)[i]-cg[i];length+=d[i]*d[i];}
        for(int i=0;i<3;++i)for(int j=0;j<3;++j){for(int k=0;k<3;++k)for(int l=0;l<3;++l)total[i][j]+=c->rotation[i][k]*(*c->inertia)[k][l]*c->rotation[j][l];total[i][j]+=*c->kilograms*((i==j?length:0)-d[i]*d[j]);}}
    checkTensor(total);out.centre=cg;out.inertia=total;return out;
}
}
