#pragma once
#include "drone_agricole/application/IStationServices.hpp"
#include <QWidget>
#include <memory>
namespace Ui { class ComparisonPage; }
namespace drone_agricole::ui {
class ComparisonPage final : public QWidget {
  Q_OBJECT
 public:
  explicit ComparisonPage(application::IStationServices& services, QWidget* parent = nullptr);
  ~ComparisonPage() override;
  bool compare(const QStringList& ids);
 private:
  std::unique_ptr<Ui::ComparisonPage> ui_;
  application::IStationServices& services_;
  QString comparisonReport_;
  void showComparison(const QJsonObject& comparison, const QStringList& resultIds);
  void exportComparisonReport();
};
}
