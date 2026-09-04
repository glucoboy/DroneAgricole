#pragma once

#include <QJsonObject>
#include <QString>

#include <stdexcept>

namespace drone_agricole::px4 {

class RunnerContractError : public std::runtime_error {
 public:
  explicit RunnerContractError(const QString& message);
};

[[nodiscard]] QJsonObject validateStartPayload(const QJsonObject& payload, const QString& workspace);
[[nodiscard]] QString rosDoubleParameterValue(double value);

}  // namespace drone_agricole::px4
