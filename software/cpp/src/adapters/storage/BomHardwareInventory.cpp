#include "drone_agricole/adapters/BomHardwareInventory.hpp"

#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QSet>
#include <cmath>
#include <stdexcept>

namespace drone_agricole::adapters {
namespace {
[[noreturn]] void fail(const QString& text) { throw std::runtime_error(text.toStdString()); }
QString text(const QJsonObject& object, const QString& key) {
  const auto value = object.value(key);
  if (!value.isUndefined() && !value.isNull() && !value.isString())
    fail(QStringLiteral("Champ BOM non textuel : %1").arg(key));
  return value.toString();
}
std::optional<double> number(const QJsonObject& object, const QString& key) {
  const auto value = object.value(key);
  if (value.isUndefined() || value.isNull()) return {};
  if (!value.isDouble() || !std::isfinite(value.toDouble()) || value.toDouble() < 0)
    fail(QStringLiteral("Valeur BOM invalide : %1").arg(key));
  return value.toDouble();
}
QStringList strings(const QJsonObject& object, const QString& key) {
  const auto value = object.value(key);
  if (value.isUndefined()) return {};
  if (!value.isArray()) fail(QStringLiteral("Tableau BOM invalide : %1").arg(key));
  QStringList result;
  for (const auto& entry : value.toArray()) {
    if (!entry.isString()) fail(QStringLiteral("Entrée BOM non textuelle : %1").arg(key));
    result.append(entry.toString());
  }
  return result;
}
}

BomHardwareInventory::BomHardwareInventory(const QString& workspace)
    : path_(QDir(workspace).absoluteFilePath(QStringLiteral("hardware/mecanique/cartographe/nomenclature_prototype.json"))) {}

domain::HardwareInventory BomHardwareInventory::load() const {
  QFile file(path_);
  if (!file.open(QIODevice::ReadOnly)) fail(QStringLiteral("Nomenclature indisponible : %1").arg(path_));
  if (file.size() > 16 * 1024 * 1024) fail(QStringLiteral("Nomenclature trop volumineuse"));
  const auto bytes = file.readAll();
  if (file.error() != QFileDevice::NoError) fail(QStringLiteral("Lecture incomplète de la nomenclature"));
  QJsonParseError error;
  const auto document = QJsonDocument::fromJson(bytes, &error);
  if (error.error != QJsonParseError::NoError || !document.isObject()) fail(QStringLiteral("Nomenclature JSON invalide : %1").arg(error.errorString()));
  const auto object = document.object();
  if (object.value(QStringLiteral("schema_version")).toInt(-1) != 2 || !object.value(QStringLiteral("items")).isArray() ||
      !object.value(QStringLiteral("configuration")).isObject()) fail(QStringLiteral("Structure ou version de nomenclature inconnue"));
  domain::HardwareInventory inventory;
  inventory.sourcePath = path_;
  inventory.reference = text(object, QStringLiteral("reference"));
  inventory.date = text(object, QStringLiteral("date"));
  inventory.status = text(object, QStringLiteral("statut"));
  inventory.qualification = text(object, QStringLiteral("qualification"));
  inventory.configuration = object.value(QStringLiteral("configuration")).toObject();
  inventory.selection = text(inventory.configuration, QStringLiteral("selection"));
  QSet<QString> ids;
  for (const auto& value : object.value(QStringLiteral("items")).toArray()) {
    if (!value.isObject()) fail(QStringLiteral("Ligne de nomenclature invalide"));
    const auto definition = value.toObject();
    domain::HardwareItem item;
    item.id = text(definition, QStringLiteral("id"));
    if (item.id.isEmpty() || ids.contains(item.id)) fail(QStringLiteral("Identifiant BOM absent ou dupliqué : %1").arg(item.id));
    ids.insert(item.id);
    item.designation = text(definition, QStringLiteral("designation"));
    item.family = text(definition, QStringLiteral("famille"));
    item.manufacturer = text(definition, QStringLiteral("fabricant"));
    item.manufacturerReference = text(definition, QStringLiteral("reference_fabricant"));
    item.subsystem = text(definition, QStringLiteral("sous_systeme"));
    item.scope = text(definition, QStringLiteral("perimetre"));
    item.status = text(definition, QStringLiteral("statut"));
    item.physicalAvailability = text(definition, QStringLiteral("disponibilite_physique"));
    item.quantity = number(definition, QStringLiteral("quantite"));
    item.unit = text(definition, QStringLiteral("unite"));
    item.unitMassGrams = number(definition, QStringLiteral("masse_unitaire_g"));
    item.reservations = strings(definition, QStringLiteral("reserves"));
    item.sources = strings(definition, QStringLiteral("sources"));
    item.definition = definition;
    inventory.items.append(item);
  }
  return inventory;
}

}  // namespace drone_agricole::adapters
