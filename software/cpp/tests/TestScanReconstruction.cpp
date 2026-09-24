#include "drone_agricole/algorithms/ScanReconstruction.hpp"
#include <QtTest>
#include <cmath>
using namespace drone_agricole::algorithms;
class TestScanReconstruction : public QObject {
  Q_OBJECT
 private slots:
  void recoversSixDofAndRejectsUnrelatedScans() {
    QList<QVector3D> world,current;
    for(int x=-8;x<=8;++x)for(int y=-8;y<=8;++y) {
      const auto z=0.25F*std::sin(x*0.7F)+0.4F*std::cos(y*0.6F);
      world.append({x*0.35F,y*0.35F,z});
      if(y%3==0)world.append({x*0.35F,y*0.35F,z+1.2F});
    }
    RigidPose expected{QQuaternion::fromEulerAngles(1.0F,-1.5F,2.0F),{0.08F,-0.06F,0.04F}};
    for(const auto& p:world)current.append(expected.rotation.conjugated().rotatedVector(p-expected.translation));
    const auto result=registerScan(world,current);
    QVERIFY2(result.accepted,qPrintable(QStringLiteral("rmse %1 overlap %2 converged %3").arg(result.rmse).arg(result.overlap).arg(result.converged)));
    QVERIFY((result.previousFromCurrent.translation-expected.translation).length()<0.04F);
    QVERIFY((result.previousFromCurrent.apply(current[13])-world[13]).length()<0.05F);
    for(auto& p:current)p+=QVector3D(100,0,0);
    QVERIFY(!registerScan(world,current).accepted);
    QVERIFY(!registerScan({},{}).accepted);
    QList<QVector3D> line;for(int i=0;i<100;++i)line.append({i*0.3F,0,0});
    QVERIFY(!registerScan(line,line).accepted);
  }
  void surfacePreservesHolesAndVerticalGeometry() {
    QList<QVector3D> points;QList<int> rings;
    for(int ring=0;ring<4;++ring)for(int b=350;b<370;++b) {
      if(b==359||b==360)continue;
      const double a=(b+0.5)*2*3.141592653589793/720-3.141592653589793;
      points.append({5.0F,static_cast<float>(5*std::tan(a)),ring*0.1F});rings.append(10-ring);
    }
    const auto mesh=triangulateScan(points,rings,0.3F);
    QVERIFY(mesh.triangles.size()>50);
    for(const auto& face:mesh.triangles){
      bool left=false,right=false;
      for(const auto index:face){left|=mesh.vertices[index].y()<0;right|=mesh.vertices[index].y()>0;}
      QVERIFY(!(left&&right));
    }
    const auto rejected=triangulateScan(points,rings,0.02F);
    QVERIFY(rejected.triangles.isEmpty());
    const auto bounded=voxelSample(points,0.05F,12);QCOMPARE(bounded.size(),12);
  }
  void fusesSurfacesInEstimatedFrameAndHonorsBudget() {
    TriangleMesh scan{{{0,0,1},{1,0,1},{0,1,1}},{{0,1,2}}};
    SurfaceMap map(0.05F,6,4);
    QVERIFY(map.integrate(scan,{}));
    QVERIFY(map.integrate(scan,{}));
    QCOMPARE(map.mesh().vertices.size(),3);QCOMPARE(map.mesh().triangles.size(),1);
    RigidPose pose{QQuaternion::fromAxisAndAngle(0,0,1,90),{4,0,0}};
    QVERIFY(map.integrate(scan,pose));
    QCOMPARE(map.mesh().vertices.size(),6);QCOMPARE(map.mesh().triangles.size(),2);
    QVERIFY((map.mesh().vertices[4]-QVector3D(4,1,1)).length()<1e-5F);
    map.colorize({scan.vertices[0]},{QColor(255,0,0)},pose);
    QCOMPARE(map.colors()[3],QColor(255,0,0));
    QVERIFY(!map.integrate(scan,{QQuaternion{},QVector3D(10,0,0)}));
    QCOMPARE(map.mesh().vertices.size(),6);QCOMPARE(map.mesh().triangles.size(),2);
  }
};
QTEST_APPLESS_MAIN(TestScanReconstruction)
#include "TestScanReconstruction.moc"
