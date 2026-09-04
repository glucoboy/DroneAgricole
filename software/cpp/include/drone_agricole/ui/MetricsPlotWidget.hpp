#pragma once

#include <QColor>
#include <QList>
#include <QPointF>
#include <QString>
#include <QWidget>

namespace drone_agricole::ui {

struct CurveSeries {
  QString label;
  QString unit;
  QColor color;
  QList<QPointF> points;
};

class MetricsPlotWidget final : public QWidget {
  Q_OBJECT

 public:
  explicit MetricsPlotWidget(QWidget* parent = nullptr);

  void setSeries(QList<CurveSeries> series);
  void clear();

 protected:
  void paintEvent(QPaintEvent* event) override;

 private:
  QList<CurveSeries> series_;
};

}  // namespace drone_agricole::ui
