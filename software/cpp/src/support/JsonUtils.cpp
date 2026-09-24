#include "drone_agricole/core/JsonUtils.hpp"

#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonParseError>
#include <QRegularExpression>
#include <QSaveFile>

namespace drone_agricole::core {

ContractError::ContractError(const QString& message) : std::runtime_error(message.toStdString()) {}

QJsonDocument readJsonDocument(const QString& path) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly)) {
    throw ContractError(QStringLiteral("JSON absent ou illisible : %1").arg(QFileInfo(path).fileName()));
  }
  QJsonParseError error;
  const auto document = QJsonDocument::fromJson(file.readAll(), &error);
  if (error.error != QJsonParseError::NoError) {
    throw ContractError(QStringLiteral("JSON invalide %1 : %2").arg(QFileInfo(path).fileName(), error.errorString()));
  }
  return document;
}

QJsonObject readJsonObject(const QString& path, const bool required) {
  if (!QFileInfo::exists(path)) {
    if (required) {
      throw ContractError(QStringLiteral("Fichier absent : %1").arg(QFileInfo(path).fileName()));
    }
    return {};
  }
  const auto document = readJsonDocument(path);
  if (!document.isObject()) {
    throw ContractError(QStringLiteral("Objet JSON attendu : %1").arg(QFileInfo(path).fileName()));
  }
  return document.object();
}

QJsonArray readJsonLines(const QString& path) {
  QJsonArray values;
  QFile file(path);
  if (!file.exists()) {
    return values;
  }
  if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
    throw ContractError(QStringLiteral("Événements illisibles : %1").arg(QFileInfo(path).fileName()));
  }
  qsizetype lineNumber = 0;
  while (!file.atEnd()) {
    ++lineNumber;
    const auto line = file.readLine().trimmed();
    if (line.isEmpty()) {
      continue;
    }
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(line, &error);
    if (error.error != QJsonParseError::NoError || !document.isObject()) {
      throw ContractError(QStringLiteral("Événement JSON invalide à la ligne %1").arg(lineNumber));
    }
    values.append(document.object());
  }
  return values;
}

void writeJsonObjectAtomically(const QString& path, const QJsonObject& object) {
  QDir().mkpath(QFileInfo(path).absolutePath());
  QSaveFile file(path);
  if (!file.open(QIODevice::WriteOnly)) {
    throw ContractError(QStringLiteral("Écriture impossible : %1").arg(path));
  }
  file.write(QJsonDocument(object).toJson(QJsonDocument::Indented));
  if (!file.commit()) {
    throw ContractError(QStringLiteral("Validation de l'écriture impossible : %1").arg(path));
  }
}

void requireSchema(const QJsonObject& object, const QString& expected, const QString& context) {
  if (object.value(QStringLiteral("schema")).toString() != expected) {
    throw ContractError(QStringLiteral("%1 : schéma %2 attendu").arg(context, expected));
  }
}

void requireFields(const QJsonObject& object, const QStringList& fields, const QString& context) {
  for (const auto& field : fields) {
    if (!object.contains(field) || object.value(field).isUndefined() || object.value(field).isNull()) {
      throw ContractError(QStringLiteral("%1.%2 est requis").arg(context, field));
    }
  }
}

QString safeIdentifier(const QJsonValue& value, const QString& fallback) {
  auto text = value.toVariant().toString().toLower();
  text.replace(QRegularExpression(QStringLiteral("[^a-z0-9_-]+")), QStringLiteral("_"));
  text.remove(QRegularExpression(QStringLiteral("^[_-]+|[_-]+$")));
  if (text.isEmpty() || !text.front().isLetterOrNumber()) {
    text = fallback;
  }
  return text.left(96);
}

QString normalizedPath(const QString& path) {
  return QDir::cleanPath(QDir::fromNativeSeparators(path));
}

bool pathIsInside(const QString& root, const QString& candidate) {
  const auto rootPath = normalizedPath(QFileInfo(root).absoluteFilePath());
  const auto candidatePath = normalizedPath(QFileInfo(candidate).absoluteFilePath());
#ifdef Q_OS_WIN
  constexpr auto sensitivity = Qt::CaseInsensitive;
#else
  constexpr auto sensitivity = Qt::CaseSensitive;
#endif
  return candidatePath.compare(rootPath, sensitivity) == 0 ||
         candidatePath.startsWith(rootPath + QLatin1Char('/'), sensitivity);
}

QString safeWorkspacePath(const QString& workspace, const QString& relative, const QString& label) {
  if (QDir::isAbsolutePath(relative)) {
    throw ContractError(QStringLiteral("%1 doit être relatif au workspace").arg(label));
  }
  const auto candidate = QFileInfo(QDir(workspace).filePath(relative)).absoluteFilePath();
  if (!pathIsInside(workspace, candidate)) {
    throw ContractError(QStringLiteral("%1 sort du workspace").arg(label));
  }
  return normalizedPath(candidate);
}

QString sha256Id(const QString& value, const qsizetype length) {
  return QString::fromLatin1(QCryptographicHash::hash(value.toUtf8(), QCryptographicHash::Sha256).toHex()).left(length);
}

QJsonValue nestedValue(const QJsonObject& object, const QStringList& keys) {
  QJsonValue value(object);
  for (const auto& key : keys) {
    if (!value.isObject()) {
      return {};
    }
    value = value.toObject().value(key);
  }
  return value;
}

QString scalarText(const QJsonValue& value) {
  if (value.isNull() || value.isUndefined()) {
    return {};
  }
  if (value.isString()) {
    return value.toString();
  }
  if (value.isBool()) {
    return value.toBool() ? QStringLiteral("true") : QStringLiteral("false");
  }
  if (value.isDouble()) {
    return QString::number(value.toDouble(), 'g', 12);
  }
  if (value.isArray()) {
    return QString::fromUtf8(QJsonDocument(value.toArray()).toJson(QJsonDocument::Compact));
  }
  return QString::fromUtf8(QJsonDocument(value.toObject()).toJson(QJsonDocument::Compact));
}

QDateTime parseUtcDate(const QJsonValue& value) {
  if (!value.isString() || value.toString().isEmpty()) {
    return {};
  }
  auto parsed = QDateTime::fromString(value.toString(), Qt::ISODateWithMs);
  if (!parsed.isValid()) {
    parsed = QDateTime::fromString(value.toString(), Qt::ISODate);
  }
  return parsed.isValid() ? parsed.toUTC() : QDateTime{};
}

}  // namespace drone_agricole::core
