#include "drone_agricole/ui/ResultViewPage.hpp"
#include "drone_agricole/ui/TrajectoryView.hpp"
#include "drone_agricole/ui/MetricsPlotWidget.hpp"
#include "ui_result_view_page.h"
namespace drone_agricole::ui {
namespace { const QList<QColor> comparisonColors{QColor(QStringLiteral("#55e2d2"))}; }
ResultViewPage::ResultViewPage(application::IStationServices& services, QWidget* parent)
    : QWidget(parent), ui_(std::make_unique<Ui::ResultViewPage>()), services_(services) {
  ui_->setupUi(this);
  connect(ui_->surfaceCheckBox,&QCheckBox::toggled,ui_->archiveTrajectoryView,&TrajectoryView::setSurfaceVisible);
  connect(ui_->pathCheckBox,&QCheckBox::toggled,ui_->archiveTrajectoryView,&TrajectoryView::setTrajectoriesVisible);
}
ResultViewPage::~ResultViewPage() = default;
void ResultViewPage::openResult(const QString& id) {
  if (currentId_ == id) return;
  const auto detail = services_.detail(id);
  const auto replay = services_.replay(id);
  const auto label = QStringLiteral("%1 · %2").arg(detail.summary.variantId, detail.summary.runId);
  ui_->archiveNotes->clear();
  showReplay(replay, label);
  ui_->resultTitle->setText(QStringLiteral("Archive · %1 · %2").arg(label,
      replay.reconstructionPartial?QStringLiteral("carte partielle"):QStringLiteral("résultat archivé")));
  currentId_ = id;
}
void ResultViewPage::appendLog(const QString& text) { ui_->archiveNotes->appendPlainText(text); }
void ResultViewPage::showReplay(const core::ReplayData& replay, const QString& label) {
  ui_->archiveTrajectoryView->clear();
  QList<TrajectorySeries> trajectories;
  if (!replay.estimate.isEmpty()) {
    trajectories.append(TrajectorySeries{label, comparisonColors.at(0), replay.estimate, false, {}});
  }
  if (!replay.truth.isEmpty()) {
    trajectories.append(TrajectorySeries{QStringLiteral("Vérité terrain"), QColor(QStringLiteral("#ffd166")), replay.truth, true, {}});
  }
  if (!replay.px4Path.isEmpty()) {
    trajectories.append(TrajectorySeries{label, comparisonColors.at(0), replay.px4Path, false, {}});
  }
  for (const auto& line : replay.mapPolylines) {
    if (line.role == QStringLiteral("detected_row")) {
      trajectories.append(TrajectorySeries{line.label, QColor(QStringLiteral("#53d8d2")), line.points, false,
                                           QStringLiteral("Rangs détectés")});
    } else if (line.role == QStringLiteral("candidate_trajectory")) {
      trajectories.append(TrajectorySeries{line.label, QColor(QStringLiteral("#ff9f68")), line.points, true,
                                           QStringLiteral("Trajectoires candidates · non qualifiées")});
    } else if (line.role == QStringLiteral("acquisition_trajectory")) {
      trajectories.append(TrajectorySeries{line.label,QColor(QStringLiteral("#ffbf69")),line.points,false,
                                           QStringLiteral("Acquisition estimée · superposition")});
    } else {
      trajectories.append(TrajectorySeries{line.label, QColor(QStringLiteral("#d98cff")), line.points, true,
                                           QStringLiteral("Objets cartographiques")});
    }
  }
  ui_->archiveTrajectoryView->setPointCloud(replay.mapPoints);
  ui_->archiveTrajectoryView->setCameraProjectedPoints(replay.cameraProjectedPoints, replay.cameraPointColors);
  ui_->archiveTrajectoryView->setReferencePoints(replay.referencePoints);
  ui_->archiveTrajectoryView->setSeries(trajectories);
  ui_->archiveTrajectoryView->setSurface(replay.surfaceVertices,replay.surfaceTriangles,replay.surfaceColors);
  ui_->surfaceCheckBox->setEnabled(!replay.surfaceTriangles.isEmpty());
  if (replay.domain == QStringLiteral("mapping") && replay.cameraPointColors.isEmpty() && replay.surfaceTriangles.isEmpty()) {
    ui_->archiveTrajectoryView->setTopView();
  } else {
    ui_->archiveTrajectoryView->resetView();
  }
  ui_->archiveMetricsPlot->setSeries({CurveSeries{replay.curveLabel, replay.curveUnit, comparisonColors.at(0), replay.curve}});
  ui_->archiveMetricsPlot->setVisible(!replay.curve.isEmpty());
  for (const auto& note : replay.notes) {
    appendLog(QStringLiteral("Carte · %1").arg(note));
  }
}


}
