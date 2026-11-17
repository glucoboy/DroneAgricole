#pragma once
#include "drone_agricole/application/IStationServices.hpp"
#include <QWidget>
#include <QSet>
#include <memory>
class QComboBox;
namespace Ui { class ResultsPage; }
namespace drone_agricole::ui {
class ResultsPage final : public QWidget {
  Q_OBJECT
 public:
  explicit ResultsPage(application::IStationServices& services, QWidget* parent = nullptr);
  ~ResultsPage() override;
  void refreshHistory();
  void selectResult(const QString& id);
 signals:
  void replayRequested(const QString& id);
  void duplicateRequested(const QJsonObject& request);
  void comparisonRequested(const QStringList& ids);
  void analysisRequested(const QString& id);
 private:
  std::unique_ptr<Ui::ResultsPage> ui_;
  application::IStationServices& services_;
  QList<core::ResultSummary> visibleResults_;
  QString selectedResultId_;
  QSet<QString> favoriteResultIds_;
  bool favoritesAvailable_{true};
  QString favoriteError_;
  void refreshFavorites();
  bool selectVisibleResult(const QString& id);
  void populateFilterChoices();
  core::SearchFilters historyFilters() const;
  void populateHistoryTable(const core::SearchFilters& filters = {});
  void applyHistoryFilters();
  void resetHistoryFilters();
  void historySelectionChanged();
  void showResultDetail(const core::ResultDetail& detail);
  void openSelectedResultFolder();
  void toggleFavorite();
  void exportVisibleResults();
  QStringList checkedResultIds() const;
  static void selectComboData(QComboBox* combo, const QString& value);
};
}
