#include "drone_agricole/application/WorkspaceService.hpp"

#include <QJsonArray>
#include <QRegularExpression>
#include <QSet>
#include <QUuid>
#include <cmath>
#include <stdexcept>

namespace drone_agricole::application {
namespace {
[[noreturn]] void fail(const QString& text) { throw std::runtime_error(text.toStdString()); }

void rejectUnknown(const QJsonObject& object, const QSet<QString>& accepted, const QString& label) {
  for (auto item = object.constBegin(); item != object.constEnd(); ++item)
    if (!accepted.contains(item.key())) fail(QStringLiteral("Champ %1 inconnu : %2").arg(label, item.key()));
}

QString textValue(const QJsonObject& object, const QString& key, qsizetype maximum = 2000) {
  const auto value = object.value(key);
  if (!value.isUndefined() && !value.isString()) fail(QStringLiteral("Le champ %1 doit être du texte").arg(key));
  const auto text = value.toString();
  if (text.size() > maximum) fail(QStringLiteral("Le champ %1 est trop long").arg(key));
  return text;
}

void checkId(const QString& id, const QString& label) {
  static const QRegularExpression pattern(QStringLiteral("^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"));
  if (!pattern.match(id).hasMatch()) fail(QStringLiteral("Identifiant %1 invalide").arg(label));
}

std::optional<double> optionalNumber(const QJsonObject& object, const QString& key) {
  const auto value = object.value(key);
  if (value.isNull() || value.isUndefined()) return {};
  if (!value.isDouble() || !std::isfinite(value.toDouble()) || value.toDouble() <= 0.0)
    fail(QStringLiteral("Le champ %1 exige une valeur finie positive ou null").arg(key));
  return value.toDouble();
}

void validateMission(const domain::MissionDraft& mission) {
  checkId(mission.id, QStringLiteral("de mission"));
  if (mission.name.trimmed().isEmpty() || mission.name.size() > 200)
    fail(QStringLiteral("Le nom de mission est requis (200 caractères maximum)"));
  if (mission.parcel.size() > 500 || mission.notes.size() > 20000)
    fail(QStringLiteral("Parcelle ou notes de mission trop longues"));
  if (mission.operation != QStringLiteral("survey") && mission.operation != QStringLiteral("treatment"))
    fail(QStringLiteral("Opération de mission inconnue"));
  if (mission.drone != QStringLiteral("cartographer") && mission.drone != QStringLiteral("sprayer"))
    fail(QStringLiteral("Type de drone inconnu"));
  for (const auto value : {mission.altitudeMeters, mission.speedMetersPerSecond})
    if (value && (!std::isfinite(*value) || *value <= 0.0))
      fail(QStringLiteral("Altitude et vitesse exigent une valeur finie positive ou inconnue"));
  if (!mission.datasetId.isEmpty()) checkId(mission.datasetId, QStringLiteral("de dataset"));
  if (!mission.sequenceId.isEmpty()) checkId(mission.sequenceId, QStringLiteral("de séquence"));
  if (!mission.sequenceId.isEmpty() && mission.datasetId.isEmpty())
    fail(QStringLiteral("Une séquence de mission exige un dataset"));
  if (mission.checklist.size() > 100) fail(QStringLiteral("Liste de contrôle trop longue"));
  QSet<QString> ids;
  for (const auto& item : mission.checklist) {
    checkId(item.id, QStringLiteral("de contrôle"));
    if (ids.contains(item.id)) fail(QStringLiteral("Identifiant de contrôle dupliqué : %1").arg(item.id));
    ids.insert(item.id);
    if (item.label.trimmed().isEmpty() || item.label.size() > 500)
      fail(QStringLiteral("Libellé de contrôle manquant ou trop long"));
  }
}

domain::MissionDraft parseMission(const QJsonObject& object) {
  rejectUnknown(object, {QStringLiteral("schema"), QStringLiteral("status"), QStringLiteral("execution_allowed"),
                         QStringLiteral("id"), QStringLiteral("name"), QStringLiteral("parcel"), QStringLiteral("operation"),
                         QStringLiteral("drone"), QStringLiteral("altitude_meters"), QStringLiteral("speed_meters_per_second"),
                         QStringLiteral("dataset_id"), QStringLiteral("sequence_id"), QStringLiteral("notes"),
                         QStringLiteral("checklist"), QStringLiteral("updated_at_utc")}, QStringLiteral("de brouillon"));
  if (object.value(QStringLiteral("schema")).toString() != QStringLiteral("drone_agricole.mission_draft.v1") ||
      object.value(QStringLiteral("status")).toString() != QStringLiteral("draft") ||
      !object.value(QStringLiteral("execution_allowed")).isBool() || object.value(QStringLiteral("execution_allowed")).toBool())
    fail(QStringLiteral("Le document doit être un brouillon de mission non exécutable v1"));
  domain::MissionDraft mission;
  mission.id = textValue(object, QStringLiteral("id"), 128);
  mission.name = textValue(object, QStringLiteral("name"), 200);
  mission.parcel = textValue(object, QStringLiteral("parcel"), 500);
  mission.operation = textValue(object, QStringLiteral("operation"), 32);
  mission.drone = textValue(object, QStringLiteral("drone"), 32);
  mission.altitudeMeters = optionalNumber(object, QStringLiteral("altitude_meters"));
  mission.speedMetersPerSecond = optionalNumber(object, QStringLiteral("speed_meters_per_second"));
  mission.datasetId = textValue(object, QStringLiteral("dataset_id"), 128);
  mission.sequenceId = textValue(object, QStringLiteral("sequence_id"), 128);
  mission.notes = textValue(object, QStringLiteral("notes"), 20000);
  const auto timestamp = textValue(object, QStringLiteral("updated_at_utc"), 64);
  mission.updatedAt = QDateTime::fromString(timestamp, Qt::ISODateWithMs);
  if (!mission.updatedAt.isValid() || mission.updatedAt.offsetFromUtc() != 0 ||
      (!timestamp.endsWith(QLatin1Char('Z')) && !timestamp.endsWith(QStringLiteral("+00:00"))))
    fail(QStringLiteral("Date UTC du brouillon invalide"));
  const auto checklist = object.value(QStringLiteral("checklist"));
  if (!checklist.isArray()) fail(QStringLiteral("Le brouillon exige un tableau checklist"));
  for (const auto& value : checklist.toArray()) {
    if (!value.isObject()) fail(QStringLiteral("Contrôle de mission invalide"));
    const auto item = value.toObject();
    rejectUnknown(item, {QStringLiteral("id"), QStringLiteral("label"), QStringLiteral("checked")}, QStringLiteral("de contrôle"));
    if (!item.value(QStringLiteral("checked")).isBool()) fail(QStringLiteral("État de contrôle invalide"));
    mission.checklist.append({textValue(item, QStringLiteral("id"), 128),
                             textValue(item, QStringLiteral("label"), 500), item.value(QStringLiteral("checked")).toBool()});
  }
  validateMission(mission);
  return mission;
}

void validatePreferences(const domain::WorkspacePreferences& preferences) {
  if (preferences.themeId != QStringLiteral("professional") && preferences.themeId != QStringLiteral("premium"))
    fail(QStringLiteral("Thème inconnu"));
  if (preferences.favoriteResultIds.size() > 10000) fail(QStringLiteral("Trop de résultats favoris"));
  QSet<QString> ids;
  for (const auto& id : preferences.favoriteResultIds) {
    if (id.isEmpty() || id.size() > 500) fail(QStringLiteral("Identifiant de résultat favori invalide"));
    if (ids.contains(id)) fail(QStringLiteral("Résultat favori dupliqué"));
    ids.insert(id);
  }
}
}

WorkspaceService::WorkspaceService(IWorkspaceStore& store, IHardwareInventory& hardware) : store_(store), hardware_(hardware) {}

domain::WorkspaceState WorkspaceService::load() const {
  const auto object = store_.load();
  if (object.isEmpty() && !store_.exists()) return {};
  if (object.value(QStringLiteral("schema")).toString() != QStringLiteral("drone_agricole.station_workspace.v1"))
    fail(QStringLiteral("Version de l'espace station inconnue ; le fichier est conservé"));
  rejectUnknown(object, {QStringLiteral("schema"), QStringLiteral("missions"), QStringLiteral("preferences")}, QStringLiteral("d'espace station"));
  if (!object.value(QStringLiteral("missions")).isArray() || !object.value(QStringLiteral("preferences")).isObject())
    fail(QStringLiteral("État station incomplet ; le fichier est conservé"));
  domain::WorkspaceState state;
  QSet<QString> ids;
  const auto missions = object.value(QStringLiteral("missions")).toArray();
  if (missions.size() > 1000) fail(QStringLiteral("Trop de brouillons dans l'espace station"));
  for (const auto& value : missions) {
    if (!value.isObject()) fail(QStringLiteral("Brouillon station invalide"));
    const auto mission = parseMission(value.toObject());
    if (ids.contains(mission.id)) fail(QStringLiteral("Identifiant de mission dupliqué : %1").arg(mission.id));
    ids.insert(mission.id);
    state.missions.append(mission);
  }
  const auto preferences = object.value(QStringLiteral("preferences")).toObject();
  rejectUnknown(preferences, {QStringLiteral("theme_id"), QStringLiteral("favorite_result_ids")}, QStringLiteral("de préférences"));
  state.preferences.themeId = textValue(preferences, QStringLiteral("theme_id"), 32);
  if (!preferences.value(QStringLiteral("favorite_result_ids")).isArray()) fail(QStringLiteral("Liste des favoris invalide"));
  for (const auto& value : preferences.value(QStringLiteral("favorite_result_ids")).toArray()) {
    if (!value.isString()) fail(QStringLiteral("Identifiant favori invalide"));
    state.preferences.favoriteResultIds.append(value.toString());
  }
  validatePreferences(state.preferences);
  return state;
}

void WorkspaceService::save(const domain::WorkspaceState& state) {
  QJsonArray missions;
  for (const auto& mission : state.missions) missions.append(missionDocument(mission));
  QJsonArray favorites;
  for (const auto& id : state.preferences.favoriteResultIds) favorites.append(id);
  store_.save({{QStringLiteral("schema"), QStringLiteral("drone_agricole.station_workspace.v1")},
               {QStringLiteral("missions"), missions},
               {QStringLiteral("preferences"), QJsonObject{{QStringLiteral("theme_id"), state.preferences.themeId},
                                                            {QStringLiteral("favorite_result_ids"), favorites}}}});
}

QList<domain::MissionDraft> WorkspaceService::missions() const { return load().missions; }

domain::MissionDraft WorkspaceService::mission(const QString& id) const {
  for (const auto& mission : missions()) if (mission.id == id) return mission;
  fail(QStringLiteral("Brouillon introuvable : %1").arg(id));
}

domain::MissionDraft WorkspaceService::saveMission(domain::MissionDraft mission) {
  auto state = load();
  if (mission.id.isEmpty()) mission.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
  mission.name = mission.name.trimmed();
  mission.updatedAt = QDateTime::currentDateTimeUtc();
  validateMission(mission);
  bool replaced = false;
  for (auto& current : state.missions) {
    if (current.id == mission.id) { current = mission; replaced = true; break; }
  }
  if (!replaced) {
    if (state.missions.size() >= 1000) fail(QStringLiteral("Limite de 1000 brouillons atteinte"));
    state.missions.append(mission);
  }
  save(state);
  return mission;
}

bool WorkspaceService::removeMission(const QString& id) {
  auto state = load();
  for (qsizetype index = 0; index < state.missions.size(); ++index) {
    if (state.missions.at(index).id == id) { state.missions.removeAt(index); save(state); return true; }
  }
  return false;
}

domain::MissionDraft WorkspaceService::importMission(const QString& path) {
  auto imported = parseMission(store_.readMissionDocument(path));
  // Importer crée un document distinct et ne peut écraser un brouillon local.
  imported.id.clear();
  return saveMission(imported);
}

void WorkspaceService::exportMission(const QString& id, const QString& path) const {
  store_.writeMissionDocument(path, missionDocument(mission(id)));
}

domain::WorkspacePreferences WorkspaceService::preferences() const { return load().preferences; }

void WorkspaceService::savePreferences(domain::WorkspacePreferences preferences) {
  validatePreferences(preferences);
  auto state = load();
  state.preferences = std::move(preferences);
  save(state);
}

void WorkspaceService::setFavoriteResult(const QString& id, bool favorite) {
  auto state = load();
  if (favorite && !state.preferences.favoriteResultIds.contains(id)) state.preferences.favoriteResultIds.append(id);
  if (!favorite) state.preferences.favoriteResultIds.removeAll(id);
  validatePreferences(state.preferences);
  save(state);
}

bool WorkspaceService::isFavoriteResult(const QString& id) const { return preferences().favoriteResultIds.contains(id); }

domain::HardwareInventory WorkspaceService::hardwareInventory() const { return hardware_.load(); }

domain::WorkspaceDiagnostics WorkspaceService::diagnostics() const {
  domain::WorkspaceDiagnostics result;
  result.statePath = store_.path();
  result.hardwareSourcePath = hardware_.sourcePath();
  result.stateExists = store_.exists();
  try {
    const auto state = load();
    result.stateReadable = true;
    result.missionCount = state.missions.size();
    result.favoriteCount = state.preferences.favoriteResultIds.size();
  } catch (const std::exception& error) { result.messages.append(QString::fromUtf8(error.what())); }
  try {
    const auto inventory = hardware_.load();
    result.hardwareReadable = true;
    result.hardwareItemCount = inventory.items.size();
  } catch (const std::exception& error) { result.messages.append(QString::fromUtf8(error.what())); }
  result.messages.append(QStringLiteral("Les brouillons et contrôles locaux ne constituent pas une autorisation de vol."));
  result.messages.append(QStringLiteral("La nomenclature décrit une définition matérielle ; connexion et qualification restent à vérifier."));
  return result;
}

QJsonObject WorkspaceService::missionDocument(const domain::MissionDraft& mission) {
  validateMission(mission);
  QJsonArray checklist;
  for (const auto& item : mission.checklist)
    checklist.append(QJsonObject{{QStringLiteral("id"), item.id}, {QStringLiteral("label"), item.label}, {QStringLiteral("checked"), item.checked}});
  return {{QStringLiteral("schema"), QStringLiteral("drone_agricole.mission_draft.v1")},
          {QStringLiteral("status"), QStringLiteral("draft")}, {QStringLiteral("execution_allowed"), false},
          {QStringLiteral("id"), mission.id}, {QStringLiteral("name"), mission.name}, {QStringLiteral("parcel"), mission.parcel},
          {QStringLiteral("operation"), mission.operation}, {QStringLiteral("drone"), mission.drone},
          {QStringLiteral("altitude_meters"), mission.altitudeMeters ? QJsonValue(*mission.altitudeMeters) : QJsonValue(QJsonValue::Null)},
          {QStringLiteral("speed_meters_per_second"), mission.speedMetersPerSecond ? QJsonValue(*mission.speedMetersPerSecond) : QJsonValue(QJsonValue::Null)},
          {QStringLiteral("dataset_id"), mission.datasetId}, {QStringLiteral("sequence_id"), mission.sequenceId},
          {QStringLiteral("notes"), mission.notes}, {QStringLiteral("checklist"), checklist},
          {QStringLiteral("updated_at_utc"), mission.updatedAt.toUTC().toString(Qt::ISODateWithMs)}};
}

}  // namespace drone_agricole::application
