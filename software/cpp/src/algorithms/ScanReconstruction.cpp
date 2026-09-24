#include "drone_agricole/algorithms/ScanReconstruction.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <stdexcept>
#include <unordered_map>
#include <vector>

namespace drone_agricole::algorithms {
namespace {
using Key = std::array<int, 3>;
struct Hash {
  std::size_t operator()(const Key& k) const {
    std::size_t h = 0;
    for (const auto v : k) h ^= std::hash<int>{}(v) + 0x9e3779b9 + (h<<6) + (h>>2);
    return h;
  }
};
bool valid(const QVector3D& p) {
  return std::isfinite(p.x()) && std::isfinite(p.y()) && std::isfinite(p.z()) && p.lengthSquared() < 1e10F;
}
Key key(const QVector3D& p, float cell) {
  return {static_cast<int>(std::floor(p.x()/cell)), static_cast<int>(std::floor(p.y()/cell)),
          static_cast<int>(std::floor(p.z()/cell))};
}
// Diagonalisation de Jacobi du problème quaternionique symétrique 4x4.
QQuaternion optimalRotation(const double h[3][3]) {
  const auto trace = h[0][0]+h[1][1]+h[2][2];
  double a[4][4] = {
    {trace,h[1][2]-h[2][1],h[2][0]-h[0][2],h[0][1]-h[1][0]},
    {h[1][2]-h[2][1],h[0][0]-h[1][1]-h[2][2],h[0][1]+h[1][0],h[0][2]+h[2][0]},
    {h[2][0]-h[0][2],h[0][1]+h[1][0],-h[0][0]+h[1][1]-h[2][2],h[1][2]+h[2][1]},
    {h[0][1]-h[1][0],h[0][2]+h[2][0],h[1][2]+h[2][1],-h[0][0]-h[1][1]+h[2][2]}};
  double v[4][4]{};
  for (int i=0;i<4;++i) v[i][i]=1;
  for (int sweep=0;sweep<60;++sweep) {
    int p=0,q=1;
    for (int i=0;i<4;++i) for (int j=i+1;j<4;++j) if (std::abs(a[i][j])>std::abs(a[p][q])) {p=i;q=j;}
    if (std::abs(a[p][q])<1e-12) break;
    const double theta=0.5*std::atan2(2*a[p][q],a[q][q]-a[p][p]);
    const double c=std::cos(theta),s=std::sin(theta),ap=a[p][p],aq=a[q][q],off=a[p][q];
    for(int k=0;k<4;++k) if(k!=p && k!=q) {
      const double x=a[k][p], y=a[k][q];
      a[k][p]=a[p][k]=c*x-s*y; a[k][q]=a[q][k]=s*x+c*y;
    }
    a[p][p]=c*c*ap-2*s*c*off+s*s*aq; a[q][q]=s*s*ap+2*s*c*off+c*c*aq; a[p][q]=a[q][p]=0;
    for(int k=0;k<4;++k) { const auto x=v[k][p], y=v[k][q]; v[k][p]=c*x-s*y; v[k][q]=s*x+c*y; }
  }
  int largest=0; for(int i=1;i<4;++i) if(a[i][i]>a[largest][largest]) largest=i;
  return QQuaternion(v[0][largest],v[1][largest],v[2][largest],v[3][largest]).normalized();
}
struct Pair { QVector3D from,to; float distance; };
class Neighbors {
 public:
  Neighbors(const QList<QVector3D>& points,float radius): points_(points),radius_(radius) {
    for(qsizetype i=0;i<points.size();++i) cells_[key(points[i],radius)].push_back(i);
  }
  bool nearest(const QVector3D& p,Pair& result) const {
    const auto k=key(p,radius_); float best=radius_*radius_; bool found=false;
    for(int x=-1;x<=1;++x) for(int y=-1;y<=1;++y) for(int z=-1;z<=1;++z) {
      const auto it=cells_.find({k[0]+x,k[1]+y,k[2]+z}); if(it==cells_.end()) continue;
      for(const auto i:it->second) {
        const auto d=(p-points_[i]).lengthSquared();
        if(d<best) {best=d;result={p,points_[i],d};found=true;}
      }
    }
    return found;
  }
 private:
  const QList<QVector3D>& points_; float radius_;
  std::unordered_map<Key,std::vector<qsizetype>,Hash> cells_;
};
} // namespace

RigidPose compose(const RigidPose& a,const RigidPose& b) {
  return {(a.rotation*b.rotation).normalized(),a.apply(b.translation)};
}
QList<QVector3D> voxelSample(const QList<QVector3D>& points,float size,int limit) {
  if(!std::isfinite(size)||size<0.01F||limit<1) throw std::invalid_argument("Grille de points invalide");
  std::unordered_map<Key,qsizetype,Hash> cells;
  QList<QVector3D> output;
  for(const auto& p:points) if(valid(p)) {
    if(cells.emplace(key(p,size),output.size()).second) output.append(p);
  }
  if(output.size()<=limit) return output;
  QList<QVector3D> bounded; bounded.reserve(limit);
  for(int i=0;i<limit;++i) bounded.append(output[static_cast<qsizetype>(i)*output.size()/limit]);
  return bounded;
}
Registration registerScan(const QList<QVector3D>& previous,const QList<QVector3D>& current,const RigidPose& initial) {
  Registration result; result.previousFromCurrent=initial;
  if(!valid(initial.translation) || initial.rotation.isNull()) return result;
  for(const float scale : {0.45F,0.20F}) {
    const auto target=voxelSample(previous,scale,6000), source=voxelSample(current,scale,6000);
    if(target.size()<40||source.size()<40) return result;
    Neighbors search(target,scale==0.45F?1.5F:0.6F);
    result.converged=false;
    for(int iteration=0;iteration<40;++iteration) {
      std::vector<Pair> pairs; pairs.reserve(source.size());
      for(const auto& p:source) {Pair pair; if(search.nearest(result.previousFromCurrent.apply(p),pair)) pairs.push_back(pair);}
      result.overlap=static_cast<double>(pairs.size())/source.size();
      if(pairs.size()<40||result.overlap<0.35) return result;
      std::sort(pairs.begin(),pairs.end(),[](const auto& a,const auto& b){return a.distance<b.distance;});
      pairs.resize(std::max<std::size_t>(40,pairs.size()*85/100));
      QVector3D from,to;
      for(const auto& p:pairs){from+=p.from;to+=p.to;}
      from/=pairs.size();to/=pairs.size();
      double h[3][3]{},scatter[3][3]{}; double spread=0;
      for(const auto& pair:pairs){const auto a=pair.from-from,b=pair.to-to;spread+=a.lengthSquared();
        for(int i=0;i<3;++i)for(int j=0;j<3;++j){h[i][j]+=a[i]*b[j];scatter[i][j]+=a[i]*a[j];}}
      if(spread/pairs.size()<0.1) return result;
      double squaredScatter=0;for(const auto& row:scatter)for(const auto value:row)squaredScatter+=value*value;
      if((spread*spread-squaredScatter)<0.004*spread*spread) return result;
      const auto rotation=optimalRotation(h);
      const RigidPose delta{rotation,to-rotation.rotatedVector(from)};
      result.previousFromCurrent=compose(delta,result.previousFromCurrent);
      ++result.iterations;
      float angle; QVector3D axis; rotation.getAxisAndAngle(&axis,&angle);
      if(delta.translation.length()<0.001F && std::min(std::abs(angle),std::abs(360-angle))<0.03F){result.converged=true;break;}
    }
    double squared=0;int matches=0;
    for(const auto& p:source){Pair pair;if(search.nearest(result.previousFromCurrent.apply(p),pair)){squared+=pair.distance;++matches;}}
    result.rmse=matches?std::sqrt(squared/matches):std::numeric_limits<double>::infinity();
    result.overlap=static_cast<double>(matches)/source.size();
  }
  float angle; QVector3D axis; result.previousFromCurrent.rotation.getAxisAndAngle(&axis,&angle);
  result.accepted=result.converged && result.overlap>=0.5 && result.rmse<=0.25 &&
    result.previousFromCurrent.translation.length()<=2.0F && std::min(std::abs(angle),std::abs(360-angle))<=20;
  return result;
}

TriangleMesh triangulateScan(const QList<QVector3D>& points,const QList<int>& rings,float maximumEdge,int bins) {
  if(points.size()!=rings.size()||!std::isfinite(maximumEdge)||maximumEdge<=0||bins<16||bins>4096)
    throw std::invalid_argument("Topologie de scan invalide");
  std::map<int,std::pair<double,int>> elevations;
  for(qsizetype i=0;i<points.size();++i) if(valid(points[i])&&points[i].length()>0.1F) {
    auto& value=elevations[rings[i]];value.first+=std::atan2(points[i].z(),std::hypot(points[i].x(),points[i].y()));++value.second;
  }
  if(elevations.size()>128) throw std::invalid_argument("Trop d'anneaux LiDAR");
  std::vector<int> order;for(const auto& e:elevations)order.push_back(e.first);
  std::sort(order.begin(),order.end(),[&](int a,int b){return elevations[a].first/elevations[a].second<elevations[b].first/elevations[b].second;});
  std::map<int,int> rows;for(std::size_t i=0;i<order.size();++i)rows[order[i]]=i;
  std::vector<int> grid(order.size()*bins,-1);
  TriangleMesh mesh;mesh.vertices=points;
  for(qsizetype i=0;i<points.size();++i) if(valid(points[i])&&rows.count(rings[i])) {
    int b=static_cast<int>((std::atan2(points[i].y(),points[i].x())+3.141592653589793)*bins/(2*3.141592653589793));
    b=std::clamp(b,0,bins-1);auto& slot=grid[rows[rings[i]]*bins+b];
    if(slot<0||points[i].lengthSquared()<points[slot].lengthSquared())slot=i;
  }
  auto triangle=[&](int a,int b,int c){
    if(a<0||b<0||c<0) return;
    const auto ab=points[b]-points[a],ac=points[c]-points[a],bc=points[c]-points[b];
    const float largest=std::max({ab.lengthSquared(),ac.lengthSquared(),bc.lengthSquared()});
    if(largest>maximumEdge*maximumEdge||QVector3D::crossProduct(ab,ac).length()<largest*0.03F)return;
    // Normale vers le capteur : orientation cohérente des faces observées.
    if(QVector3D::dotProduct(QVector3D::crossProduct(ab,ac),points[a])>0) std::swap(b,c);
    mesh.triangles.append({a,b,c});
  };
  for(std::size_t r=1;r<order.size();++r)for(int b=0;b<bins;++b){const int next=(b+1)%bins;
    const auto a=grid[(r-1)*bins+b],c=grid[r*bins+b],d=grid[r*bins+next],e=grid[(r-1)*bins+next];
    triangle(a,c,d);triangle(a,d,e);
  }
  return mesh;
}
SurfaceMap::SurfaceMap(float size,int vertices,int faces):voxelSize_(size),maximumVertices_(vertices),maximumFaces_(faces) {
  if(!std::isfinite(size)||size<0.01F||vertices<1||faces<1)throw std::invalid_argument("Budget de surface invalide");
}
bool SurfaceMap::integrate(const TriangleMesh& scan,const RigidPose& pose) {
  std::set<Key> additions;
  for(const auto& p:scan.vertices) {
    const auto world=pose.apply(p);
    if(!valid(world))throw std::invalid_argument("Sommet de surface invalide");
    const auto k=key(world,voxelSize_);if(!vertices_.count(k))additions.insert(k);
  }
  if(mesh_.vertices.size()+additions.size()>static_cast<std::size_t>(maximumVertices_)||
     mesh_.triangles.size()+scan.triangles.size()>maximumFaces_)return false;
  for(const auto& face:scan.triangles)for(const auto i:face)
    if(i<0||i>=scan.vertices.size())throw std::invalid_argument("Indice de surface invalide");
  QList<int> indices;indices.reserve(scan.vertices.size());
  for(const auto& p:scan.vertices) {
    const auto world=pose.apply(p), kpoint=world;
    const auto k=key(kpoint,voxelSize_);
    const auto [it,inserted]=vertices_.emplace(k,mesh_.vertices.size());
    if(inserted){mesh_.vertices.append(world);colors_.append(QColor(130,155,160));colorCounts_.append(0);}
    indices.append(it->second);
  }
  for(const auto& t:scan.triangles) {
    const std::array<int,3> mapped{indices[t[0]],indices[t[1]],indices[t[2]]};
    if(mapped[0]==mapped[1]||mapped[1]==mapped[2]||mapped[0]==mapped[2])continue;
    if(QVector3D::crossProduct(mesh_.vertices[mapped[1]]-mesh_.vertices[mapped[0]],
                              mesh_.vertices[mapped[2]]-mesh_.vertices[mapped[0]]).lengthSquared()<1e-10F)continue;
    auto sorted=mapped;std::sort(sorted.begin(),sorted.end());
    if(faces_.insert(sorted).second)mesh_.triangles.append(mapped);
  }
  return true;
}
void SurfaceMap::colorize(const QList<QVector3D>& points,const QList<QColor>& colors,const RigidPose& pose) {
  if(points.size()!=colors.size())throw std::invalid_argument("Couleurs non alignées");
  for(qsizetype i=0;i<points.size();++i){
    const auto it=vertices_.find(key(pose.apply(points[i]),voxelSize_));if(it==vertices_.end())continue;
    const int index=it->second;auto& count=colorCounts_[index];const auto old=colors_[index],value=colors[i];
    colors_[index]=QColor((old.red()*count+value.red())/(count+1),(old.green()*count+value.green())/(count+1),
                          (old.blue()*count+value.blue())/(count+1));++count;
  }
}
} // namespace drone_agricole::algorithms
