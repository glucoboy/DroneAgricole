#pragma once

#include "drone_agricole/application/IStationServices.hpp"
#include <QWidget>
#include <memory>

namespace Ui { class AnalysisPage; }
namespace drone_agricole::ui {
class AnalysisPage final : public QWidget {
  Q_OBJECT
 public:
  explicit AnalysisPage(application::IStationServices& services, QWidget* parent = nullptr);
  ~AnalysisPage() override;
  void setSection(const QString& section);
  void refreshResults();
  void openResult(const QString& id);
 private:
  std::unique_ptr<Ui::AnalysisPage> ui_;
  application::IStationServices& services_;
  QString currentId_;
  QString report_;
  void loadSelectedResult();
  void exportReport();
  void clearResult();
};
}  // namespace drone_agricole::ui
