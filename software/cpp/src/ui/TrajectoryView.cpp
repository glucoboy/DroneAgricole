#include "drone_agricole/ui/TrajectoryView.hpp"

#include <QFontMetrics>
#include <QKeyEvent>
#include <QLinearGradient>
#include <QMouseEvent>
#include <QPainter>
#include <QPainterPath>
#include <QPolygonF>
#include <QWheelEvent>

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>

namespace drone_agricole::ui {
namespace {

constexpr float fieldOfViewDegrees = 45.0F;
constexpr int heightBucketCount = 10;
constexpr float pi = 3.14159265358979323846F;

float radians(const float degrees) { return degrees * pi / 180.0F; }

bool finitePoint(const QVector3D& point) {
  return std::isfinite(point.x()) && std::isfinite(point.y()) && std::isfinite(point.z());
}

QColor mix(const QColor& first, const QColor& second, const float ratio, const int alpha = 255) {
  const auto bounded = std::clamp(ratio, 0.0F, 1.0F);
  return QColor::fromRgbF(first.redF() + (second.redF() - first.redF()) * bounded,
                          first.greenF() + (second.greenF() - first.greenF()) * bounded,
                          first.blueF() + (second.blueF() - first.blueF()) * bounded,
                          static_cast<float>(alpha) / 255.0F);
}

}  // namespace

TrajectoryView::TrajectoryView(QWidget* parent) : QOpenGLWidget(parent) {
  setMinimumSize(460, 340);
  setMouseTracking(true);
  setFocusPolicy(Qt::StrongFocus);
  setToolTip(QStringLiteral(
      "Rotation : bouton gauche · Déplacement : bouton droit, central ou Maj + gauche · Zoom : molette · "
      "Double-clic : cadrer"));
}

void TrajectoryView::setSeries(QList<TrajectorySeries> series) {
  series_ = std::move(series);
  if (automaticFit_ || !cameraInitialized_) {
    updateAutomaticFit();
  }
  update();
}

void TrajectoryView::setPointCloud(QList<QVector3D> points) {
  cloud_ = std::move(points);
  if (automaticFit_ || !cameraInitialized_) {
    updateAutomaticFit();
  }
  update();
}

void TrajectoryView::clear() {
  series_.clear();
  cloud_.clear();
  cameraTarget_ = {};
  yawDegrees_ = -45.0F;
  pitchDegrees_ = 48.0F;
  cameraDistance_ = 20.0F;
  automaticFit_ = true;
  cameraInitialized_ = false;
  update();
}

qsizetype TrajectoryView::pointCloudSize() const noexcept { return cloud_.size(); }

QVector3D TrajectoryView::cameraTarget() const noexcept { return cameraTarget_; }

float TrajectoryView::cameraDistance() const noexcept { return cameraDistance_; }

void TrajectoryView::resetView() {
  yawDegrees_ = -45.0F;
  pitchDegrees_ = 48.0F;
  automaticFit_ = true;
  updateAutomaticFit();
  update();
}

void TrajectoryView::fitToData() {
  automaticFit_ = true;
  updateAutomaticFit();
  update();
}

void TrajectoryView::setTopView() {
  updateAutomaticFit();
  pitchDegrees_ = 89.0F;
  yawDegrees_ = 0.0F;
  automaticFit_ = false;
  update();
}

void TrajectoryView::initializeGL() {}

void TrajectoryView::paintGL() {
  QPainter painter(this);
  painter.setRenderHint(QPainter::Antialiasing, true);
  QLinearGradient background(0.0, 0.0, 0.0, height());
  background.setColorAt(0.0, QColor(QStringLiteral("#0d1824")));
  background.setColorAt(0.58, QColor(QStringLiteral("#08131d")));
  background.setColorAt(1.0, QColor(QStringLiteral("#071019")));
  painter.fillRect(rect(), background);

  const auto camera = cameraFrame();
  const auto bounds = dataBounds();
  const auto step = gridStep();
  drawGroundGrid(painter, camera, step);

  if (!hasContent()) {
    painter.setPen(QColor(QStringLiteral("#d4e1ee")));
    QFont titleFont = painter.font();
    titleFont.setPointSizeF(12.0);
    titleFont.setWeight(QFont::DemiBold);
    painter.setFont(titleFont);
    painter.drawText(plotRect().adjusted(24, 20, -24, -20), Qt::AlignCenter,
                     QStringLiteral("Carte 3D en attente\n\nLancez une simulation ou rechargez une trajectoire"));
    drawCompass(painter, camera);
    drawScale(painter, camera);
    return;
  }

  painter.save();
  painter.setClipRect(plotRect());
  drawPointCloud(painter, camera, bounds);
  drawTrajectories(painter, camera);
  painter.restore();

  drawLegend(painter);
  drawCompass(painter, camera);
  drawScale(painter, camera);

  QFont helpFont = painter.font();
  helpFont.setPointSizeF(8.0);
  painter.setFont(helpFont);
  painter.setPen(QColor(QStringLiteral("#8fa5ba")));
  const auto mode = automaticFit_ ? QStringLiteral("cadrage automatique") : QStringLiteral("navigation libre");
  painter.drawText(plotRect().adjusted(0, 0, -8, -6), Qt::AlignRight | Qt::AlignBottom,
                   QStringLiteral("%1 · azimut %2° · élévation %3°")
                       .arg(mode)
                       .arg(yawDegrees_, 0, 'f', 0)
                       .arg(pitchDegrees_, 0, 'f', 0));
}

void TrajectoryView::mousePressEvent(QMouseEvent* event) {
  setFocus(Qt::MouseFocusReason);
  lastMousePosition_ = event->position().toPoint();
  if (event->button() == Qt::LeftButton && !event->modifiers().testFlag(Qt::ShiftModifier)) {
    setCursor(Qt::ClosedHandCursor);
  } else if (event->button() == Qt::RightButton || event->button() == Qt::MiddleButton ||
             event->modifiers().testFlag(Qt::ShiftModifier)) {
    setCursor(Qt::SizeAllCursor);
  }
  event->accept();
}

void TrajectoryView::mouseMoveEvent(QMouseEvent* event) {
  const auto current = event->position().toPoint();
  const auto delta = current - lastMousePosition_;
  const auto pan = event->buttons().testFlag(Qt::RightButton) || event->buttons().testFlag(Qt::MiddleButton) ||
                   (event->buttons().testFlag(Qt::LeftButton) &&
                    event->modifiers().testFlag(Qt::ShiftModifier));
  if (pan) {
    automaticFit_ = false;
    panCamera(delta);
  } else if (event->buttons().testFlag(Qt::LeftButton)) {
    automaticFit_ = false;
    yawDegrees_ = std::fmod(yawDegrees_ + static_cast<float>(delta.x()) * 0.35F, 360.0F);
    pitchDegrees_ = std::clamp(pitchDegrees_ - static_cast<float>(delta.y()) * 0.30F, 8.0F, 89.0F);
  }
  lastMousePosition_ = current;
  if (pan || event->buttons().testFlag(Qt::LeftButton)) {
    update();
    event->accept();
    return;
  }
  QOpenGLWidget::mouseMoveEvent(event);
}

void TrajectoryView::mouseReleaseEvent(QMouseEvent* event) {
  unsetCursor();
  event->accept();
}

void TrajectoryView::mouseDoubleClickEvent(QMouseEvent* event) {
  if (event->button() == Qt::LeftButton) {
    resetView();
    event->accept();
    return;
  }
  QOpenGLWidget::mouseDoubleClickEvent(event);
}

void TrajectoryView::wheelEvent(QWheelEvent* event) {
  const auto steps = !event->angleDelta().isNull() ? static_cast<float>(event->angleDelta().y()) / 120.0F
                                                   : static_cast<float>(event->pixelDelta().y()) / 60.0F;
  if (std::abs(steps) > 0.001F) {
    automaticFit_ = false;
    cameraDistance_ = std::clamp(cameraDistance_ * std::pow(0.82F, steps), 0.15F, 1000000.0F);
    update();
  }
  event->accept();
}

void TrajectoryView::keyPressEvent(QKeyEvent* event) {
  const auto panPixels = std::max(18, std::min(width(), height()) / 18);
  switch (event->key()) {
    case Qt::Key_F:
    case Qt::Key_Home:
      resetView();
      break;
    case Qt::Key_1:
      setTopView();
      break;
    case Qt::Key_Left:
    case Qt::Key_A:
      automaticFit_ = false;
      panCamera(QPoint(panPixels, 0));
      update();
      break;
    case Qt::Key_Right:
    case Qt::Key_D:
      automaticFit_ = false;
      panCamera(QPoint(-panPixels, 0));
      update();
      break;
    case Qt::Key_Up:
    case Qt::Key_W:
      automaticFit_ = false;
      panCamera(QPoint(0, panPixels));
      update();
      break;
    case Qt::Key_Down:
    case Qt::Key_S:
      automaticFit_ = false;
      panCamera(QPoint(0, -panPixels));
      update();
      break;
    case Qt::Key_Plus:
    case Qt::Key_Equal:
      automaticFit_ = false;
      cameraDistance_ = std::max(0.15F, cameraDistance_ * 0.82F);
      update();
      break;
    case Qt::Key_Minus:
      automaticFit_ = false;
      cameraDistance_ = std::min(1000000.0F, cameraDistance_ / 0.82F);
      update();
      break;
    default:
      QOpenGLWidget::keyPressEvent(event);
      return;
  }
  event->accept();
}

bool TrajectoryView::hasContent() const {
  if (!cloud_.isEmpty()) {
    return true;
  }
  return std::any_of(series_.cbegin(), series_.cend(), [](const auto& value) { return !value.points.isEmpty(); });
}

TrajectoryView::Bounds TrajectoryView::dataBounds() const {
  Bounds bounds;
  bounds.minimum = QVector3D(std::numeric_limits<float>::max(), std::numeric_limits<float>::max(),
                             std::numeric_limits<float>::max());
  bounds.maximum = QVector3D(std::numeric_limits<float>::lowest(), std::numeric_limits<float>::lowest(),
                             std::numeric_limits<float>::lowest());
  const auto include = [&bounds](const QVector3D& point) {
    if (!finitePoint(point)) {
      return;
    }
    bounds.minimum.setX(std::min(bounds.minimum.x(), point.x()));
    bounds.minimum.setY(std::min(bounds.minimum.y(), point.y()));
    bounds.minimum.setZ(std::min(bounds.minimum.z(), point.z()));
    bounds.maximum.setX(std::max(bounds.maximum.x(), point.x()));
    bounds.maximum.setY(std::max(bounds.maximum.y(), point.y()));
    bounds.maximum.setZ(std::max(bounds.maximum.z(), point.z()));
    bounds.valid = true;
  };
  for (const auto& point : cloud_) {
    include(point);
  }
  for (const auto& series : series_) {
    for (const auto& point : series.points) {
      include(point);
    }
  }
  return bounds;
}

QRectF TrajectoryView::plotRect() const { return QRectF(rect()).adjusted(10.0, 10.0, -10.0, -10.0); }

TrajectoryView::CameraFrame TrajectoryView::cameraFrame() const {
  const auto yaw = radians(yawDegrees_);
  const auto pitch = radians(pitchDegrees_);
  const QVector3D offset(std::cos(pitch) * std::cos(yaw), std::cos(pitch) * std::sin(yaw), std::sin(pitch));
  CameraFrame camera;
  camera.position = cameraTarget_ + offset * cameraDistance_;
  camera.forward = (cameraTarget_ - camera.position).normalized();
  camera.right = QVector3D::crossProduct(camera.forward, QVector3D(0.0F, 0.0F, 1.0F)).normalized();
  if (camera.right.lengthSquared() < 0.001F) {
    camera.right = QVector3D(1.0F, 0.0F, 0.0F);
  }
  camera.up = QVector3D::crossProduct(camera.right, camera.forward).normalized();
  camera.focalPixels = static_cast<float>(plotRect().height() * 0.5) /
                       std::tan(radians(fieldOfViewDegrees) * 0.5F);
  return camera;
}

TrajectoryView::ProjectedPoint TrajectoryView::project(const QVector3D& point, const CameraFrame& camera) const {
  if (!finitePoint(point)) {
    return {};
  }
  const auto relative = point - camera.position;
  const auto depth = QVector3D::dotProduct(relative, camera.forward);
  if (depth <= std::max(0.01F, cameraDistance_ * 0.001F)) {
    return {};
  }
  const auto center = plotRect().center();
  const auto x = center.x() + QVector3D::dotProduct(relative, camera.right) * camera.focalPixels / depth;
  const auto y = center.y() - QVector3D::dotProduct(relative, camera.up) * camera.focalPixels / depth;
  return {QPointF(x, y), depth, true};
}

float TrajectoryView::gridStep() const {
  const auto span = std::max(1.0F, cameraDistance_ * 0.72F);
  return niceStep(span / 9.0F);
}

float TrajectoryView::worldUnitsPerPixel(const CameraFrame& camera) const {
  return camera.focalPixels > 0.0F ? cameraDistance_ / camera.focalPixels : 1.0F;
}

float TrajectoryView::niceStep(const float value) {
  if (!std::isfinite(value) || value <= 0.0F) {
    return 1.0F;
  }
  const auto exponent = std::floor(std::log10(value));
  const auto magnitude = std::pow(10.0F, exponent);
  const auto normalized = value / magnitude;
  const auto factor = normalized <= 1.0F ? 1.0F : normalized <= 2.0F ? 2.0F : normalized <= 5.0F ? 5.0F : 10.0F;
  return factor * magnitude;
}

void TrajectoryView::updateAutomaticFit() {
  const auto bounds = dataBounds();
  if (!bounds.valid) {
    return;
  }
  cameraTarget_ = (bounds.minimum + bounds.maximum) * 0.5F;
  const auto size = bounds.maximum - bounds.minimum;
  const auto radius = std::max(0.75F, size.length() * 0.5F);
  const auto aspect = static_cast<float>(std::max(1.0, plotRect().width())) /
                      static_cast<float>(std::max(1.0, plotRect().height()));
  const auto aspectPenalty = aspect < 1.0F ? 1.0F / aspect : 1.0F;
  cameraDistance_ = std::clamp(radius * aspectPenalty /
                                   (std::tan(radians(fieldOfViewDegrees) * 0.5F) * 0.72F),
                               3.0F, 1000000.0F);
  cameraInitialized_ = true;
}

void TrajectoryView::panCamera(const QPoint& pixelDelta) {
  const auto units = worldUnitsPerPixel(cameraFrame());
  const auto yaw = radians(yawDegrees_);
  const QVector3D groundRight(-std::sin(yaw), std::cos(yaw), 0.0F);
  const QVector3D groundForward(-std::cos(yaw), -std::sin(yaw), 0.0F);
  cameraTarget_ += groundRight * (-static_cast<float>(pixelDelta.x()) * units) +
                   groundForward * (static_cast<float>(pixelDelta.y()) * units);
}

void TrajectoryView::drawGroundGrid(QPainter& painter, const CameraFrame& camera, const float step) const {
  const auto span = step * 14.0F;
  const auto centerX = std::floor(cameraTarget_.x() / step) * step;
  const auto centerY = std::floor(cameraTarget_.y() / step) * step;
  painter.save();
  painter.setClipRect(plotRect());
  for (int index = -14; index <= 14; ++index) {
    const auto x = centerX + static_cast<float>(index) * step;
    const auto y = centerY + static_cast<float>(index) * step;
    const auto verticalStart = project(QVector3D(x, centerY - span, 0.0F), camera);
    const auto verticalEnd = project(QVector3D(x, centerY + span, 0.0F), camera);
    const auto horizontalStart = project(QVector3D(centerX - span, y, 0.0F), camera);
    const auto horizontalEnd = project(QVector3D(centerX + span, y, 0.0F), camera);
    const auto major = index % 5 == 0;
    painter.setPen(QPen(major ? QColor(52, 78, 101, 180) : QColor(31, 52, 70, 150), major ? 1.2 : 0.8));
    if (verticalStart.valid && verticalEnd.valid) {
      painter.drawLine(verticalStart.position, verticalEnd.position);
    }
    if (horizontalStart.valid && horizontalEnd.valid) {
      painter.drawLine(horizontalStart.position, horizontalEnd.position);
    }
  }

  const auto origin = project(QVector3D(0.0F, 0.0F, 0.0F), camera);
  const auto xAxis = project(QVector3D(step * 2.0F, 0.0F, 0.0F), camera);
  const auto yAxis = project(QVector3D(0.0F, step * 2.0F, 0.0F), camera);
  const auto zAxis = project(QVector3D(0.0F, 0.0F, step * 2.0F), camera);
  if (origin.valid) {
    QFont axisFont = painter.font();
    axisFont.setPointSizeF(7.5);
    axisFont.setBold(true);
    painter.setFont(axisFont);
    const std::array<std::pair<ProjectedPoint, QColor>, 3> axes{
        std::pair{xAxis, QColor(QStringLiteral("#ff7187"))},
        std::pair{yAxis, QColor(QStringLiteral("#74e3a8"))},
        std::pair{zAxis, QColor(QStringLiteral("#6aaeff"))},
    };
    const std::array<QString, 3> labels{QStringLiteral("X"), QStringLiteral("Y"), QStringLiteral("Z")};
    for (std::size_t index = 0; index < axes.size(); ++index) {
      if (!axes[index].first.valid) {
        continue;
      }
      painter.setPen(QPen(axes[index].second, 2.0));
      painter.drawLine(origin.position, axes[index].first.position);
      painter.drawText(axes[index].first.position + QPointF(4.0, -3.0), labels[index]);
    }
  }
  painter.restore();
}

void TrajectoryView::drawPointCloud(QPainter& painter, const CameraFrame& camera, const Bounds& bounds) const {
  if (cloud_.isEmpty() || !bounds.valid) {
    return;
  }
  std::array<QPolygonF, heightBucketCount> buckets;
  const auto heightSpan = std::max(0.001F, bounds.maximum.z() - bounds.minimum.z());
  for (const auto& point : cloud_) {
    const auto projected = project(point, camera);
    if (!projected.valid || !plotRect().adjusted(-3.0, -3.0, 3.0, 3.0).contains(projected.position)) {
      continue;
    }
    const auto normalized = (point.z() - bounds.minimum.z()) / heightSpan;
    const auto bucket = std::clamp(static_cast<int>(normalized * heightBucketCount), 0, heightBucketCount - 1);
    buckets[static_cast<std::size_t>(bucket)].append(projected.position);
  }

  painter.setRenderHint(QPainter::Antialiasing, false);
  painter.setPen(QPen(QColor(0, 5, 10, 120), 3.0, Qt::SolidLine, Qt::RoundCap));
  for (const auto& bucket : buckets) {
    painter.drawPoints(bucket);
  }
  const QColor low(QStringLiteral("#2c7890"));
  const QColor high(QStringLiteral("#a5fff2"));
  for (int index = 0; index < heightBucketCount; ++index) {
    painter.setPen(QPen(mix(low, high, static_cast<float>(index) / (heightBucketCount - 1), 220), 1.7,
                        Qt::SolidLine, Qt::RoundCap));
    painter.drawPoints(buckets[static_cast<std::size_t>(index)]);
  }
  painter.setRenderHint(QPainter::Antialiasing, true);
}

void TrajectoryView::drawTrajectories(QPainter& painter, const CameraFrame& camera) const {
  for (const auto& series : series_) {
    if (series.points.isEmpty()) {
      continue;
    }
    QPainterPath path;
    QList<ProjectedPoint> projectedPoints;
    projectedPoints.reserve(series.points.size());
    bool activePath = false;
    for (const auto& point : series.points) {
      const auto projected = project(point, camera);
      projectedPoints.append(projected);
      if (!projected.valid) {
        activePath = false;
        continue;
      }
      if (activePath) {
        path.lineTo(projected.position);
      } else {
        path.moveTo(projected.position);
        activePath = true;
      }
    }

    QPen halo(QColor(3, 8, 13, 225), series.dashed ? 5.0 : 6.0, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin);
    painter.setPen(halo);
    painter.setBrush(Qt::NoBrush);
    painter.drawPath(path);

    QPen line(series.color, series.dashed ? 2.0 : 2.8, series.dashed ? Qt::DashLine : Qt::SolidLine,
              Qt::RoundCap, Qt::RoundJoin);
    if (series.dashed) {
      line.setDashPattern({5.0, 3.0});
    }
    painter.setPen(line);
    painter.drawPath(path);

    const auto first = std::find_if(projectedPoints.cbegin(), projectedPoints.cend(),
                                    [](const auto& value) { return value.valid; });
    const auto last = std::find_if(projectedPoints.crbegin(), projectedPoints.crend(),
                                   [](const auto& value) { return value.valid; });
    if (first != projectedPoints.cend()) {
      painter.setPen(QPen(QColor(QStringLiteral("#071019")), 2.0));
      painter.setBrush(series.color);
      painter.drawEllipse(first->position, 4.2, 4.2);
    }
    if (last != projectedPoints.crend()) {
      painter.setPen(QPen(QColor(QStringLiteral("#ffffff")), 1.5));
      painter.setBrush(series.color);
      painter.drawEllipse(last->position, 6.0, 6.0);
      painter.setBrush(QColor(QStringLiteral("#ffffff")));
      painter.drawEllipse(last->position, 1.8, 1.8);
    }
  }
}

void TrajectoryView::drawLegend(QPainter& painter) const {
  QStringList labels;
  QList<QColor> colors;
  if (!cloud_.isEmpty()) {
    labels.append(QStringLiteral("Carte LiDAR · %1 points").arg(cloud_.size()));
    colors.append(QColor(QStringLiteral("#72e8dc")));
  }
  for (const auto& series : series_) {
    if (!series.points.isEmpty()) {
      labels.append(QStringLiteral("%1 · %2 poses").arg(series.label).arg(series.points.size()));
      colors.append(series.color);
    }
  }
  if (labels.isEmpty()) {
    return;
  }
  QFont legendFont = painter.font();
  legendFont.setPointSizeF(8.3);
  painter.setFont(legendFont);
  const QFontMetrics metrics(legendFont);
  int textWidth = 0;
  for (const auto& label : labels) {
    textWidth = std::max(textWidth, metrics.horizontalAdvance(label));
  }
  const auto rowHeight = metrics.height() + 5;
  const QRectF panel(plotRect().left() + 12.0, plotRect().top() + 12.0, textWidth + 48.0,
                     labels.size() * rowHeight + 16.0);
  painter.setPen(QPen(QColor(66, 91, 116, 190), 1.0));
  painter.setBrush(QColor(8, 18, 28, 220));
  painter.drawRoundedRect(panel, 8.0, 8.0);
  for (qsizetype index = 0; index < labels.size(); ++index) {
    const auto y = panel.top() + 10.0 + index * rowHeight + metrics.ascent();
    painter.setPen(QPen(colors.at(index), index == 0 && !cloud_.isEmpty() ? 3.5 : 3.0, Qt::SolidLine,
                        Qt::RoundCap));
    painter.drawLine(QPointF(panel.left() + 12.0, y - 3.0), QPointF(panel.left() + 29.0, y - 3.0));
    painter.setPen(QColor(QStringLiteral("#eef6fd")));
    painter.drawText(QPointF(panel.left() + 36.0, y), labels.at(index));
  }
}

void TrajectoryView::drawCompass(QPainter& painter, const CameraFrame& camera) const {
  const QPointF center(plotRect().right() - 35.0, plotRect().top() + 35.0);
  painter.setPen(QPen(QColor(91, 119, 145, 210), 1.0));
  painter.setBrush(QColor(8, 18, 28, 215));
  painter.drawEllipse(center, 24.0, 24.0);
  const auto origin = project(cameraTarget_, camera);
  const auto north = project(cameraTarget_ + QVector3D(0.0F, std::max(1.0F, gridStep()), 0.0F), camera);
  QPointF direction(0.0, -1.0);
  if (origin.valid && north.valid) {
    const auto delta = north.position - origin.position;
    const auto length = std::hypot(delta.x(), delta.y());
    if (length > 0.001) {
      direction = delta / length;
    }
  }
  const auto tip = center + direction * 16.0;
  const QPointF normal(-direction.y(), direction.x());
  const QPolygonF arrow{tip, center - direction * 6.0 + normal * 5.0, center - direction * 6.0 - normal * 5.0};
  painter.setPen(Qt::NoPen);
  painter.setBrush(QColor(QStringLiteral("#ff7187")));
  painter.drawPolygon(arrow);
  QFont compassFont = painter.font();
  compassFont.setPointSizeF(7.5);
  compassFont.setBold(true);
  painter.setFont(compassFont);
  painter.setPen(QColor(QStringLiteral("#ffffff")));
  painter.drawText(QRectF(center.x() - 9.0, center.y() - 9.0, 18.0, 18.0), Qt::AlignCenter,
                   QStringLiteral("N"));
}

void TrajectoryView::drawScale(QPainter& painter, const CameraFrame& camera) const {
  const auto unitsPerPixel = std::max(0.000001F, worldUnitsPerPixel(camera));
  const auto scaleWorld = niceStep(unitsPerPixel * 90.0F);
  const auto scalePixels = std::clamp(static_cast<double>(scaleWorld / unitsPerPixel), 45.0, 180.0);
  const auto left = plotRect().left() + 18.0;
  const auto bottom = plotRect().bottom() - 18.0;
  painter.setPen(QPen(QColor(QStringLiteral("#eaf3fb")), 2.0));
  painter.drawLine(QPointF(left, bottom), QPointF(left + scalePixels, bottom));
  painter.drawLine(QPointF(left, bottom - 4.0), QPointF(left, bottom + 4.0));
  painter.drawLine(QPointF(left + scalePixels, bottom - 4.0), QPointF(left + scalePixels, bottom + 4.0));
  QFont scaleFont = painter.font();
  scaleFont.setPointSizeF(8.0);
  painter.setFont(scaleFont);
  const auto label = scaleWorld >= 1000.0F ? QStringLiteral("%1 km").arg(scaleWorld / 1000.0F, 0, 'g', 3)
                                          : QStringLiteral("%1 m").arg(scaleWorld, 0, 'g', 3);
  painter.drawText(QRectF(left, bottom - 23.0, scalePixels, 16.0), Qt::AlignCenter, label);
}

}  // namespace drone_agricole::ui
