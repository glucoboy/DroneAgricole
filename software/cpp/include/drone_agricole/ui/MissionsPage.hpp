#pragma once
#include "drone_agricole/application/IStationServices.hpp"
#include <QWidget>
#include <QTimer>
#include <memory>
namespace Ui { class MissionsPage; }
namespace drone_agricole::ui {
class MissionsPage final : public QWidget {
  Q_OBJECT
 public:
  explicit MissionsPage(application::IStationServices& services, QWidget* parent = nullptr);
  ~MissionsPage() override;
  void setSection(const QString& section);
  void refresh();
  void startNewDraft();
 signals:
  void routeRequested(const QString& route, const QString& object = {});
 private:
  std::unique_ptr<Ui::MissionsPage> ui_;
  application::IStationServices& services_;
  QTimer telemetryTimer_;
  QString selectedDraftId_;
  void populateDrafts();
  void selectDraft();
  void newDraft();
  void saveDraft();
  void updateSequences();
  void updateSupervision();
  void populateJournal();
};
}
