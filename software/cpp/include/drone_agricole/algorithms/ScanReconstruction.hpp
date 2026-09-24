#pragma once
#include <QList>
#include <QQuaternion>
#include <QVector3D>
#include <array>
#include <QColor>
#include <map>
#include <set>

namespace drone_agricole::algorithms {
struct RigidPose {
  QQuaternion rotation;
  QVector3D translation;
  QVector3D apply(const QVector3D& p) const { return rotation.rotatedVector(p) + translation; }
};
RigidPose compose(const RigidPose& worldFromPrevious, const RigidPose& previousFromCurrent);
struct Registration {
  RigidPose previousFromCurrent;
  bool accepted{false};
  double rmse{0}, overlap{0};
  int iterations{0};
  bool converged{false};
};
// Aucun fichier, aucune référence de trajectoire. Les poses sont estimées depuis la géométrie.
Registration registerScan(const QList<QVector3D>& previous, const QList<QVector3D>& current,
                          const RigidPose& initial = {});
QList<QVector3D> voxelSample(const QList<QVector3D>& points, float size, int limit);
struct TriangleMesh {
  QList<QVector3D> vertices;
  QList<std::array<int, 3>> triangles;
};
// Les anneaux sont ordonnés par leur élévation mesurée, pas par l'identifiant constructeur.
TriangleMesh triangulateScan(const QList<QVector3D>& points, const QList<int>& rings,
                             float maximumEdge, int azimuthBins = 720);
class SurfaceMap {
 public:
  explicit SurfaceMap(float voxelSize, int maximumVertices = 100000, int maximumFaces = 150000);
  bool integrate(const TriangleMesh& scan, const RigidPose& pose);
  void colorize(const QList<QVector3D>& points, const QList<QColor>& colors, const RigidPose& pose);
  const TriangleMesh& mesh() const { return mesh_; }
  const QList<QColor>& colors() const { return colors_; }
  const QList<int>& colorCounts() const { return colorCounts_; }
 private:
  float voxelSize_; int maximumVertices_,maximumFaces_;
  TriangleMesh mesh_;
  std::map<std::array<int,3>,int> vertices_;
  std::set<std::array<int,3>> faces_;
  QList<QColor> colors_;
  QList<int> colorCounts_;
};
} // namespace drone_agricole::algorithms
