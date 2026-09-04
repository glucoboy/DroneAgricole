#pragma once

#include <QJsonDocument>
#include <QJsonObject>
#include <QStringList>

#include <stdexcept>

namespace drone_agricole::core {

class ContractError final : public std::runtime_error {
 public:
  explicit ContractError(const QString& message);
};

[[nodiscard]] QJsonDocument readJsonDocument(const QString& path);
[[nodiscard]] QJsonObject readJsonObject(const QString& path, bool required = true);
[[nodiscard]] QJsonArray readJsonLines(const QString& path);
void writeJsonObjectAtomically(const QString& path, const QJsonObject& object);

void requireSchema(const QJsonObject& object, const QString& expected, const QString& context);
void requireFields(const QJsonObject& object, const QStringList& fields, const QString& context);
[[nodiscard]] QString safeIdentifier(const QJsonValue& value, const QString& fallback);
[[nodiscard]] QString normalizedPath(const QString& path);
[[nodiscard]] QString safeWorkspacePath(const QString& workspace, const QString& relative, const QString& label);
[[nodiscard]] bool pathIsInside(const QString& root, const QString& candidate);
[[nodiscard]] QString sha256Id(const QString& value, qsizetype length = 20);
[[nodiscard]] QJsonValue nestedValue(const QJsonObject& object, const QStringList& keys);
[[nodiscard]] QString scalarText(const QJsonValue& value);
[[nodiscard]] QDateTime parseUtcDate(const QJsonValue& value);

}  // namespace drone_agricole::core
