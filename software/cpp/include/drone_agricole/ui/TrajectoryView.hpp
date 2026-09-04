#pragma once

#include <QColor>
#include <QList>
#include <QOpenGLWidget>
#include <QPoint>
#include <QRectF>
#include <QString>
#include <QVector3D>

class QKeyEvent;
class QMouseEvent;
class QPainter;
class QWheelEvent;

namespace drone_agricole::ui {

struct TrajectorySeries {
  QString label;
  QColor color;
  QList<QVector3D> points;
  bool dashed{false};
};

class TrajectoryView final : public QOpenGLWidget {
  Q_OBJECT

 public:
  explicit TrajectoryView(QWidget* parent = nullptr);

  void setSeries(QList<TrajectorySeries> series);
  void setPointCloud(QList<QVector3D> points);
  void clear();

  [[nodiscard]] qsizetype pointCloudSize() const noexcept;
  [[nodiscard]] QVector3D cameraTarget() const noexcept;
  [[nodiscard]] float cameraDistance() const noexcept;

 public slots:
  void resetView();
  void fitToData();
  void setTopView();

 protected:
  void initializeGL() override;
  void paintGL() override;
  void mousePressEvent(QMouseEvent* event) override;
  void mouseMoveEvent(QMouseEvent* event) override;
  void mouseReleaseEvent(QMouseEvent* event) override;
  void mouseDoubleClickEvent(QMouseEvent* event) override;
  void wheelEvent(QWheelEvent* event) override;
  void keyPressEvent(QKeyEvent* event) override;

 private:
  struct Bounds {
    QVector3D minimum;
    QVector3D maximum;
    bool valid{false};
  };

  struct CameraFrame {
    QVector3D position;
    QVector3D forward;
    QVector3D right;
    QVector3D up;
    float focalPixels{1.0F};
  };

  struct ProjectedPoint {
    QPointF position;
    float depth{0.0F};
    bool valid{false};
  };

  QList<TrajectorySeries> series_;
  QList<QVector3D> cloud_;
  QPoint lastMousePosition_;
  QVector3D cameraTarget_;
  float yawDegrees_{-45.0F};
  float pitchDegrees_{48.0F};
  float cameraDistance_{20.0F};
  bool automaticFit_{true};
  bool cameraInitialized_{false};

  [[nodiscard]] bool hasContent() const;
  [[nodiscard]] Bounds dataBounds() const;
  [[nodiscard]] QRectF plotRect() const;
  [[nodiscard]] CameraFrame cameraFrame() const;
  [[nodiscard]] ProjectedPoint project(const QVector3D& point, const CameraFrame& camera) const;
  [[nodiscard]] float gridStep() const;
  [[nodiscard]] float worldUnitsPerPixel(const CameraFrame& camera) const;
  static float niceStep(float value);

  void updateAutomaticFit();
  void panCamera(const QPoint& pixelDelta);
  void drawGroundGrid(QPainter& painter, const CameraFrame& camera, float step) const;
  void drawPointCloud(QPainter& painter, const CameraFrame& camera, const Bounds& bounds) const;
  void drawTrajectories(QPainter& painter, const CameraFrame& camera) const;
  void drawLegend(QPainter& painter) const;
  void drawCompass(QPainter& painter, const CameraFrame& camera) const;
  void drawScale(QPainter& painter, const CameraFrame& camera) const;
};

}  // namespace drone_agricole::ui
