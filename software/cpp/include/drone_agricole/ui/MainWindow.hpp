#pragma once

#include "drone_agricole/core/ComparisonService.hpp"
#include "drone_agricole/core/ContractRegistry.hpp"
#include "drone_agricole/core/LiveTelemetry.hpp"
#include "drone_agricole/core/ResultRepository.hpp"
#include "drone_agricole/core/RunnerRegistry.hpp"

#include <QHash>
#include <QMainWindow>
#include <QProcess>
#include <QTimer>

#include <memory>
#include <optional>

class QWidget;
class QComboBox;

namespace Ui {
class MainWindow;
}

namespace drone_agricole::ui {

class MainWindow final : public QMainWindow {
  Q_OBJECT

 public:
  explicit MainWindow(QString workspace, QWidget* parent = nullptr);
  ~MainWindow() override;

 private slots:
  void simulationChanged();
  void variantChanged();
  void startRun();
  void stopRun();
  void processOutput();
  void processFinished(int exitCode, QProcess::ExitStatus exitStatus);
  void refreshHistory();
  void applyHistoryFilters();
  void resetHistoryFilters();
  void historySelectionChanged();
  void replaySelectedResult();
  void duplicateSelectedResult();
  void openSelectedResultFolder();
  void compareSelectedResults();
  void exportComparisonReport();
  void showAbout();
  void updateLiveTelemetry();

 private:
  std::unique_ptr<Ui::MainWindow> ui_;
  QString workspace_;
  std::unique_ptr<core::ContractRegistry> contracts_;
  std::unique_ptr<core::ResultRepository> repository_;
  std::unique_ptr<core::RunnerRegistry> runners_;
  std::unique_ptr<core::ComparisonService> comparisons_;
  std::unique_ptr<core::LiveTelemetry> telemetry_;
  QHash<QString, QWidget*> parameterEditors_;
  QList<core::ResultSummary> visibleResults_;
  QString selectedResultId_;
  QString comparisonReport_;
  QProcess process_;
  QTimer telemetryTimer_;
  QList<QPointF> liveAteCurve_;
  QString processLineBuffer_;
  bool telemetryConnected_{false};
  std::optional<core::PreparedRun> activeRun_;

  void connectInterface();
  void initializeData();
  void populateSimulations();
  void populateVariants();
  void populateDatasetSequences();
  void populateProfiles();
  void rebuildParameterEditors();
  void populateFilterChoices();
  void populateHistoryTable(const core::SearchFilters& filters = {});
  void showResultDetail(const core::ResultDetail& detail);
  void showReplay(const core::ReplayData& replay, const QString& label);
  void showComparison(const QJsonObject& comparison, const QStringList& resultIds);
  void setRunState(bool running, const QString& message);
  void appendLog(const QString& text);
  void consumeRunnerProgress(const QString& text);
  void setTelemetryConnectionState(bool connected);
  void setGlobalStatus(const QString& text, bool error = false);

  [[nodiscard]] QString currentSimulationId() const;
  [[nodiscard]] QString currentVariantId() const;
  [[nodiscard]] QJsonObject parameterValues() const;
  [[nodiscard]] QJsonObject currentRequest() const;
  [[nodiscard]] QStringList checkedResultIds() const;
  [[nodiscard]] core::SearchFilters historyFilters() const;
  static void selectComboData(QComboBox* combo, const QString& value);
};

}  // namespace drone_agricole::ui
