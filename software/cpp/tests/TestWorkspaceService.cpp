#include "drone_agricole/application/WorkspaceService.hpp"
#include "drone_agricole/adapters/BomHardwareInventory.hpp"
#include "drone_agricole/adapters/JsonWorkspaceStore.hpp"

#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLockFile>
#include <QTemporaryDir>
#include <QtTest>
#include <limits>
#include <stdexcept>

using namespace drone_agricole;
namespace {
class Hardware final : public application::IHardwareInventory {
 public:
  domain::HardwareInventory load() const override { return {}; }
  QString sourcePath() const override { return QStringLiteral("test-bom"); }
};

class MemoryStore final : public application::IWorkspaceStore {
 public:
  QJsonObject document;
  QJsonObject imported;
  bool present{false};
  bool failSave{false};
  QJsonObject load() const override { return document; }
  void save(const QJsonObject& value) override {
    if (failSave) throw std::runtime_error("Storage unavailable");
    document = value; present = true;
  }
  QString path() const override { return QStringLiteral("memory"); }
  bool exists() const override { return present; }
  QJsonObject readMissionDocument(const QString&) const override { return imported; }
  void writeMissionDocument(const QString&, const QJsonObject&) const override {}
};

domain::MissionDraft draft() {
  domain::MissionDraft result;
  result.name = QStringLiteral("Préparation d'acquisition");
  result.parcel = QStringLiteral("Zone de travail");
  result.checklist.append({QStringLiteral("interfaces"), QStringLiteral("Contrôler les interfaces réelles"), false});
  return result;
}

QByteArray readBytes(const QString& path) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly)) return {};
  return file.readAll();
}

void writeBytes(const QString& path, const QByteArray& bytes) {
  QFile file(path);
  if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size()) throw std::runtime_error("Test file write failed");
}
}

class TestWorkspaceService : public QObject {
  Q_OBJECT
 private slots:
  void emptyWorkspaceCreatesNoData() {
    QTemporaryDir temporary;
    QVERIFY(temporary.isValid());
    adapters::JsonWorkspaceStore store(temporary.path());
    Hardware hardware;
    application::WorkspaceService service(store, hardware);
    QVERIFY(service.missions().isEmpty());
    QCOMPARE(service.preferences().themeId, QStringLiteral("professional"));
    QVERIFY(service.preferences().favoriteResultIds.isEmpty());
    QVERIFY(!store.exists());
  }

  void persistsDraftsPreferencesAndFavoritesAcrossInstances() {
    QTemporaryDir temporary;
    adapters::JsonWorkspaceStore store(temporary.path());
    Hardware hardware;
    application::WorkspaceService service(store, hardware);
    auto mission = draft();
    mission.datasetId = QStringLiteral("dataset");
    mission.sequenceId = QStringLiteral("sequence");
    mission.altitudeMeters = 18.5;
    const auto saved = service.saveMission(mission);
    QVERIFY(!saved.id.isEmpty());
    QVERIFY(saved.updatedAt.isValid());
    auto preferences = service.preferences();
    preferences.themeId = QStringLiteral("premium");
    service.savePreferences(preferences);
    service.setFavoriteResult(QStringLiteral("archive/result-id"), true);
    service.setFavoriteResult(QStringLiteral("archive/result-id"), true);
    adapters::JsonWorkspaceStore reopenedStore(temporary.path());
    application::WorkspaceService reopened(reopenedStore, hardware);
    QCOMPARE(reopened.missions().size(), 1);
    const auto restored = reopened.mission(saved.id);
    QCOMPARE(restored.datasetId, mission.datasetId);
    QCOMPARE(restored.sequenceId, mission.sequenceId);
    QVERIFY(restored.altitudeMeters.has_value());
    QCOMPARE(*restored.altitudeMeters, 18.5);
    QVERIFY(!restored.speedMetersPerSecond.has_value());
    QCOMPARE(restored.checklist.size(), 1);
    QVERIFY(!restored.checklist.first().checked);
    QCOMPARE(reopened.preferences().themeId, QStringLiteral("premium"));
    QCOMPARE(reopened.preferences().favoriteResultIds.size(), 1);
    QVERIFY(reopened.isFavoriteResult(QStringLiteral("archive/result-id")));
    reopened.setFavoriteResult(QStringLiteral("archive/result-id"), false);
    QVERIFY(reopened.preferences().favoriteResultIds.isEmpty());
    QVERIFY(reopened.removeMission(saved.id));
    QVERIFY(!reopened.removeMission(saved.id));
    QVERIFY(reopened.missions().isEmpty());
  }

  void saveFailurePreservesPreviouslyVisibleState() {
    MemoryStore store;
    Hardware hardware;
    application::WorkspaceService service(store, hardware);
    auto saved = service.saveMission(draft());
    const auto original = store.document;
    store.failSave = true;
    saved.name = QStringLiteral("Modification non enregistrée");
    QVERIFY_EXCEPTION_THROWN(service.saveMission(saved), std::runtime_error);
    QCOMPARE(store.document, original);
    QCOMPARE(service.mission(saved.id).name, draft().name);
    QVERIFY_EXCEPTION_THROWN(service.setFavoriteResult(QStringLiteral("result"), true), std::runtime_error);
    QVERIFY(service.preferences().favoriteResultIds.isEmpty());
  }

  void rejectsNonFiniteValuesAndInvalidReferences() {
    MemoryStore store;
    Hardware hardware;
    application::WorkspaceService service(store, hardware);
    auto mission = draft();
    mission.altitudeMeters = std::numeric_limits<double>::quiet_NaN();
    QVERIFY_EXCEPTION_THROWN(service.saveMission(mission), std::runtime_error);
    mission.altitudeMeters = std::numeric_limits<double>::infinity();
    QVERIFY_EXCEPTION_THROWN(service.saveMission(mission), std::runtime_error);
    mission.altitudeMeters = 0;
    QVERIFY_EXCEPTION_THROWN(service.saveMission(mission), std::runtime_error);
    mission.altitudeMeters.reset();
    mission.sequenceId = QStringLiteral("sequence-only");
    QVERIFY_EXCEPTION_THROWN(service.saveMission(mission), std::runtime_error);
    mission.sequenceId.clear();
    mission.checklist.append(mission.checklist.first());
    QVERIFY_EXCEPTION_THROWN(service.saveMission(mission), std::runtime_error);
    QVERIFY(!store.present);
  }

  void corruptOrNewerStateIsNeverOverwritten() {
    QTemporaryDir temporary;
    adapters::JsonWorkspaceStore store(temporary.path());
    Hardware hardware;
    application::WorkspaceService service(store, hardware);
    QVERIFY(QDir().mkpath(QFileInfo(store.path()).absolutePath()));
    for (const auto& bytes : {QByteArray("{broken"), QByteArray("{}"),
                              QByteArray("{\"schema\":\"drone_agricole.station_workspace.v99\"}")}) {
      writeBytes(store.path(), bytes);
      QVERIFY_EXCEPTION_THROWN(service.missions(), std::runtime_error);
      QVERIFY_EXCEPTION_THROWN(service.saveMission(draft()), std::runtime_error);
      QVERIFY_EXCEPTION_THROWN(service.savePreferences({}), std::runtime_error);
      QCOMPARE(readBytes(store.path()), bytes);
      const auto diagnostics = service.diagnostics();
      QVERIFY(diagnostics.stateExists);
      QVERIFY(!diagnostics.stateReadable);
      QVERIFY(!diagnostics.messages.isEmpty());
    }
  }

  void rejectsDuplicateMissionIdsInStoredState() {
    MemoryStore store;
    Hardware hardware;
    application::WorkspaceService service(store, hardware);
    service.saveMission(draft());
    auto missions = store.document.value(QStringLiteral("missions")).toArray();
    missions.append(missions.first());
    store.document.insert(QStringLiteral("missions"), missions);
    const auto original = store.document;
    QVERIFY_EXCEPTION_THROWN(service.missions(), std::runtime_error);
    QVERIFY_EXCEPTION_THROWN(service.saveMission(draft()), std::runtime_error);
    QCOMPARE(store.document, original);
  }

  void lockAndConcurrentChangesPreserveDiskState() {
    QTemporaryDir temporary;
    adapters::JsonWorkspaceStore store(temporary.path());
    Hardware hardware;
    application::WorkspaceService service(store, hardware);
    service.saveMission(draft());
    const auto original = readBytes(store.path());
    {
      QLockFile lock(store.path() + QStringLiteral(".lock"));
      QVERIFY(lock.tryLock(0));
      QVERIFY_EXCEPTION_THROWN(service.setFavoriteResult(QStringLiteral("result"), true), std::runtime_error);
      QCOMPARE(readBytes(store.path()), original);
    }
    adapters::JsonWorkspaceStore otherStore(temporary.path());
    auto firstDocument = store.load();
    auto staleDocument = otherStore.load();
    firstDocument.insert(QStringLiteral("marker"), QStringLiteral("first"));
    store.save(firstDocument);
    staleDocument.insert(QStringLiteral("marker"), QStringLiteral("stale"));
    QVERIFY_EXCEPTION_THROWN(otherStore.save(staleDocument), std::runtime_error);
    QCOMPARE(store.load().value(QStringLiteral("marker")).toString(), QStringLiteral("first"));
  }

  void importsDistinctNonExecutableDraftAndExportsAtomically() {
    QTemporaryDir temporary;
    adapters::JsonWorkspaceStore store(temporary.path());
    Hardware hardware;
    application::WorkspaceService service(store, hardware);
    const auto original = service.saveMission(draft());
    const auto exportPath = QDir(temporary.path()).filePath(QStringLiteral("draft.json"));
    service.exportMission(original.id, exportPath);
    const auto bytes = readBytes(exportPath);
    const auto exported = QJsonDocument::fromJson(bytes).object();
    QCOMPARE(exported.value(QStringLiteral("status")).toString(), QStringLiteral("draft"));
    QVERIFY(!exported.value(QStringLiteral("execution_allowed")).toBool(true));
    const auto imported = service.importMission(exportPath);
    QVERIFY(imported.id != original.id);
    QCOMPARE(imported.name, original.name);
    QCOMPARE(service.missions().size(), 2);
    QVERIFY_EXCEPTION_THROWN(service.exportMission(original.id, exportPath), std::runtime_error);
    QCOMPARE(readBytes(exportPath), bytes);
    auto executable = exported;
    executable.insert(QStringLiteral("execution_allowed"), true);
    writeBytes(exportPath, QJsonDocument(executable).toJson());
    QVERIFY_EXCEPTION_THROWN(service.importMission(exportPath), std::runtime_error);
    QCOMPARE(service.missions().size(), 2);
  }

  void exportStaysInsideWorkspace() {
    QTemporaryDir temporary;
    QTemporaryDir outside;
    adapters::JsonWorkspaceStore store(temporary.path());
    Hardware hardware;
    application::WorkspaceService service(store, hardware);
    const auto mission = service.saveMission(draft());
    const auto outsidePath = QDir(outside.path()).filePath(QStringLiteral("draft.json"));
    QVERIFY_EXCEPTION_THROWN(service.exportMission(mission.id, outsidePath), std::runtime_error);
    QVERIFY(!QFileInfo::exists(outsidePath));
  }

  void inventoryReadsCurrentBomWithoutInventingAvailability() {
    const auto workspace = QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE);
    adapters::BomHardwareInventory source(workspace);
    const auto original = readBytes(source.sourcePath());
    QVERIFY(!original.isEmpty());
    const auto inventory = source.load();
    QCOMPARE(inventory.reference, QStringLiteral("BOM-CARTO-PROTOTYPE"));
    QCOMPARE(inventory.items.size(), QJsonDocument::fromJson(original).object().value(QStringLiteral("items")).toArray().size());
    QVERIFY(!inventory.items.isEmpty());
    QCOMPARE(inventory.qualification, QStringLiteral("À valider"));
    const auto first = inventory.items.first();
    QCOMPARE(first.id, QStringLiteral("MEC-X650-KIT"));
    QVERIFY(first.unitMassGrams.has_value());
    QCOMPARE(*first.unitMassGrams, 2000.0);
    QCOMPARE(first.definition.value(QStringLiteral("perimetre")).toString(), QStringLiteral("approvisionnement"));
    QVERIFY(first.definition.value(QStringLiteral("contribution_connue_g")).isNull());
    QCOMPARE(first.physicalAvailability, first.definition.value(QStringLiteral("disponibilite_physique")).toString());
    QCOMPARE(readBytes(source.sourcePath()), original);
  }
};

QTEST_GUILESS_MAIN(TestWorkspaceService)
#include "TestWorkspaceService.moc"
