#pragma once
#include "drone_agricole/application/IStationServices.hpp"
#include <QWidget>
#include <memory>
namespace Ui { class ResultViewPage; }
namespace drone_agricole::ui {
class ResultViewPage final : public QWidget {
  Q_OBJECT
 public:
  explicit ResultViewPage(application::IStationServices& services, QWidget* parent = nullptr);
  ~ResultViewPage() override;
  void openResult(const QString& id);
 private:
  std::unique_ptr<Ui::ResultViewPage> ui_;
  application::IStationServices& services_;
  QString currentId_;
  void showReplay(const core::ReplayData& replay, const QString& label);
  void appendLog(const QString& text);
};
}
