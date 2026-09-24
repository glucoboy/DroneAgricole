#pragma once
#include "drone_agricole/application/IStationServices.hpp"
#include <QWidget>
#include <QTimer>
#include <QHash>
#include <memory>
class QComboBox;
namespace Ui { class ExecutionPage; }
namespace drone_agricole::ui {
class ExecutionPage final : public QWidget {
  Q_OBJECT
 public:
  explicit ExecutionPage(application::IStationServices& services, QWidget* parent = nullptr);
  ~ExecutionPage() override;
  void applyRequest(const QJsonObject& request);
  void showReplay(const core::ReplayData& replay, const QString& label);
 signals:
  void resultAvailable(const QString& id);
 private:
  std::unique_ptr<Ui::ExecutionPage> ui_;
  application::IStationServices& services_;
  QHash<QString, QWidget*> parameterEditors_;
  QTimer telemetryTimer_;
  QList<QPointF> liveAteCurve_;
  bool telemetryConnected_{false};
  void populateSimulations();
  void simulationChanged();
  void variantChanged();
  void populateVariants();
  void populateDatasetSequences();
  void populateSequences();
  void populateProfiles();
  void rebuildParameterEditors();
  QJsonObject parameterValues() const;
  QJsonObject currentRequest() const;
  QString currentSimulationId() const;
  QString currentVariantId() const;
  void startRun();
  void updateLiveTelemetry();
  void setTelemetryConnectionState(bool connected);
  void appendLog(const QString& text);
  void updateRunState();
  void runCompleted();
  static void selectComboData(QComboBox* combo, const QString& value);
};
}
