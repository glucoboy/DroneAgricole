#pragma once

#include "drone_agricole/core/Types.hpp"

#include <QHash>

namespace drone_agricole::core {

class ResultRepository {
 public:
  explicit ResultRepository(QString workspace, QString resultsDirectory = {});

  void refresh();
  [[nodiscard]] QList<ResultSummary> search(const SearchFilters& filters = {}) const;
  [[nodiscard]] ResultDetail detail(const QString& resultId) const;
  [[nodiscard]] ReplayData replay(const QString& resultId);

  [[nodiscard]] qsizetype totalCount() const noexcept;
  [[nodiscard]] qsizetype invalidResultCount() const noexcept;
  [[nodiscard]] QJsonArray errors() const;
  [[nodiscard]] const QString& workspace() const noexcept;
  [[nodiscard]] const QString& resultsRoot() const noexcept;

 private:
  struct Record {
    QString directory;
    NormalizedResult normalized;
    ResultSummary summary;
  };

  QString workspace_;
  QString resultsRoot_;
  QHash<QString, Record> records_;
  QHash<QString, ReplayData> replayCache_;
  QJsonArray errors_;

  [[nodiscard]] const Record& record(const QString& resultId) const;
  [[nodiscard]] ResultSummary publicSummary(const QString& directory, const NormalizedResult& normalized) const;
  [[nodiscard]] static ReplayData replayPx4(const Record& record);
};

}  // namespace drone_agricole::core
