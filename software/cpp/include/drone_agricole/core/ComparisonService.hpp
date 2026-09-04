#pragma once

#include "drone_agricole/core/ResultRepository.hpp"

namespace drone_agricole::core {

class ComparisonService {
 public:
  explicit ComparisonService(ResultRepository& repository);

  [[nodiscard]] QJsonObject preview(const QStringList& resultIds) const;
  [[nodiscard]] QString report(const QStringList& resultIds) const;
  [[nodiscard]] ComparisonResult compare(const QStringList& resultIds) const;

  static void validateResultIds(const QStringList& resultIds);
  [[nodiscard]] static QString renderMarkdownReport(const QJsonObject& comparison);

 private:
  ResultRepository& repository_;
};

}  // namespace drone_agricole::core
