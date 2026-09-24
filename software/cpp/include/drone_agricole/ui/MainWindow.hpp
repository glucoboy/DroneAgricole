#pragma once
#include "drone_agricole/application/IStationServices.hpp"
#include "drone_agricole/ui/NavigationModel.hpp"
#include <QMainWindow>
#include <memory>
namespace Ui { class MainWindow; }
namespace drone_agricole::ui {
class ExecutionPage;
class ResultsPage;
class ComparisonPage;
class ResultViewPage;
class MainWindow final : public QMainWindow {
  Q_OBJECT
 public:
  explicit MainWindow(application::IStationServices& services, QWidget* parent = nullptr);
  ~MainWindow() override;
 protected:
  void closeEvent(QCloseEvent* event) override;
 private:
  std::unique_ptr<Ui::MainWindow> ui_;
  application::IStationServices& services_;
  NavigationModel navigation_;
  QHash<QString, QWidget*> pages_;
  ExecutionPage* executionPage_;
  ResultsPage* resultsPage_;
  ComparisonPage* comparisonPage_;
  ResultViewPage* resultPage_;
  QString lastResultId_;
  bool closePending_{false};
  void registerPage(const QString& id, const QString& title, QWidget* page, bool primary);
  void updateNavigation();
  void updateTreatment();
  void refreshOverview();
};
}
