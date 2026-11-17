#pragma once
#include "drone_agricole/application/IStationServices.hpp"
#include <QWidget>
#include <memory>
namespace Ui { class SystemPage; }
namespace drone_agricole::ui {
class SystemPage final : public QWidget {
  Q_OBJECT
 public:
  explicit SystemPage(application::IStationServices& services, QWidget* parent = nullptr);
  ~SystemPage() override;
  void setSection(const QString& section);
  void refresh();
 signals:
  void routeRequested(const QString& route, const QString& object = {});
  void themeChanged();
 private:
  std::unique_ptr<Ui::SystemPage> ui_;
  application::IStationServices& services_;
  void loadPreferences();
  void savePreferences();
  void populateHardware();
  void showHardware();
  void updateDiagnostics();
  void populateMaintenance();
};
}
