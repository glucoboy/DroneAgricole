#pragma once
#include "drone_agricole/application/IStationServices.hpp"
#include <QWidget>
#include <memory>
namespace Ui { class DataPage; }
namespace drone_agricole::ui {
class DataPage final : public QWidget {
  Q_OBJECT
 public:
  explicit DataPage(application::IStationServices& services, QWidget* parent = nullptr);
  ~DataPage() override;
  void setSection(const QString& section);
  void refresh();
 signals:
  void routeRequested(const QString& route, const QString& object = {});
 private:
  std::unique_ptr<Ui::DataPage> ui_;
  application::IStationServices& services_;
  QString selectedResultId_;
  void populateCatalogue();
  void showSequence();
  void populateAcquisitions();
  void showAcquisition();
  void exportMetadata();
  void importDrafts();
  void exportDrafts();
};
}
