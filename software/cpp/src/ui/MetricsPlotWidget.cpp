#include "drone_agricole/ui/MetricsPlotWidget.hpp"

#include <QPaintEvent>
#include <QPainter>
#include <QPainterPath>

#include <algorithm>
#include <limits>

namespace drone_agricole::ui {

MetricsPlotWidget::MetricsPlotWidget(QWidget* parent) : QWidget(parent) { setMinimumSize(320, 200); }

void MetricsPlotWidget::setSeries(QList<CurveSeries> series) {
  series_ = std::move(series);
  update();
}

void MetricsPlotWidget::clear() {
  series_.clear();
  update();
}

void MetricsPlotWidget::paintEvent(QPaintEvent* event) {
  Q_UNUSED(event)
  QPainter painter(this);
  painter.setRenderHint(QPainter::Antialiasing);
  painter.fillRect(rect(), QColor(QStringLiteral("#0a121c")));
  const auto plot = rect().adjusted(52, 24, -18, -42);
  painter.setPen(QPen(QColor(QStringLiteral("#536a84")), 1));
  painter.drawRect(plot);
  for (int step = 1; step < 5; ++step) {
    const auto y = plot.top() + plot.height() * step / 5.0;
    painter.setPen(QPen(QColor(QStringLiteral("#223348")), 1));
    painter.drawLine(plot.left(), y, plot.right(), y);
  }
  if (series_.isEmpty() || std::all_of(series_.cbegin(), series_.cend(), [](const auto& value) { return value.points.isEmpty(); })) {
    painter.setPen(QColor(QStringLiteral("#b5c2d1")));
    painter.drawText(plot, Qt::AlignCenter, QStringLiteral("Aucune courbe chargée"));
    return;
  }

  double minimumX = std::numeric_limits<double>::max();
  double maximumX = std::numeric_limits<double>::lowest();
  double minimumY = std::numeric_limits<double>::max();
  double maximumY = std::numeric_limits<double>::lowest();
  for (const auto& series : series_) {
    for (const auto& point : series.points) {
      minimumX = std::min(minimumX, point.x());
      maximumX = std::max(maximumX, point.x());
      minimumY = std::min(minimumY, point.y());
      maximumY = std::max(maximumY, point.y());
    }
  }
  if (maximumX <= minimumX) {
    maximumX = minimumX + 1.0;
  }
  if (maximumY <= minimumY) {
    maximumY = minimumY + 1.0;
  }
  const auto mapPoint = [&](const QPointF& point) {
    return QPointF(plot.left() + (point.x() - minimumX) / (maximumX - minimumX) * plot.width(),
                   plot.bottom() - (point.y() - minimumY) / (maximumY - minimumY) * plot.height());
  };
  for (const auto& series : series_) {
    if (series.points.isEmpty()) {
      continue;
    }
    QPainterPath path;
    path.moveTo(mapPoint(series.points.front()));
    for (qsizetype index = 1; index < series.points.size(); ++index) {
      path.lineTo(mapPoint(series.points.at(index)));
    }
    painter.setPen(QPen(series.color, 2.0));
    painter.drawPath(path);
  }
  painter.setPen(QColor(QStringLiteral("#b5c2d1")));
  painter.drawText(QRect(0, plot.top() - 8, plot.left() - 7, 20), Qt::AlignRight | Qt::AlignVCenter,
                   QString::number(maximumY, 'g', 4));
  painter.drawText(QRect(0, plot.bottom() - 10, plot.left() - 7, 20), Qt::AlignRight | Qt::AlignVCenter,
                   QString::number(minimumY, 'g', 4));
  painter.drawText(QRect(plot.left(), plot.bottom() + 8, plot.width(), 20), Qt::AlignLeft,
                   QString::number(minimumX, 'g', 4));
  painter.drawText(QRect(plot.left(), plot.bottom() + 8, plot.width(), 20), Qt::AlignRight,
                   QString::number(maximumX, 'g', 4));
  int legendX = plot.left();
  for (const auto& series : series_) {
    painter.setPen(QPen(series.color, 3));
    painter.drawLine(legendX, 13, legendX + 18, 13);
    painter.setPen(QColor(QStringLiteral("#eef5fc")));
    const auto label = series.unit.isEmpty() ? series.label : QStringLiteral("%1 [%2]").arg(series.label, series.unit);
    painter.drawText(legendX + 24, 17, label);
    legendX += 34 + painter.fontMetrics().horizontalAdvance(label);
  }
}

}  // namespace drone_agricole::ui
