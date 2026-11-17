#pragma once
#include "drone_agricole/application/GazeboExportService.hpp"
#include <QWidget>
#include <memory>
namespace Ui { class GazeboModelPage; }
namespace drone_agricole::ui {
class GazeboModelPage final : public QWidget {
  Q_OBJECT
 public:
  explicit GazeboModelPage(application::GazeboExportService&,QWidget* parent=nullptr);
  ~GazeboModelPage() override;
  void refresh();
 private:
  application::GazeboExportService& service_;
  std::unique_ptr<Ui::GazeboModelPage> ui_;
  QString directory_;
  void updateState();
  void showPreview(const QJsonObject&);
};
}
