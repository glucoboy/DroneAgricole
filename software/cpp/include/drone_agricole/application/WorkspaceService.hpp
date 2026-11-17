#pragma once

#include "drone_agricole/application/WorkspacePorts.hpp"

namespace drone_agricole::application {

class WorkspaceService {
 public:
  WorkspaceService(IWorkspaceStore& store, IHardwareInventory& hardware);
  QList<domain::MissionDraft> missions() const;
  domain::MissionDraft mission(const QString& id) const;
  domain::MissionDraft saveMission(domain::MissionDraft mission);
  bool removeMission(const QString& id);
  domain::MissionDraft importMission(const QString& path);
  void exportMission(const QString& id, const QString& path) const;
  domain::WorkspacePreferences preferences() const;
  void savePreferences(domain::WorkspacePreferences preferences);
  void setFavoriteResult(const QString& id, bool favorite);
  bool isFavoriteResult(const QString& id) const;
  domain::HardwareInventory hardwareInventory() const;
  domain::WorkspaceDiagnostics diagnostics() const;
  static QJsonObject missionDocument(const domain::MissionDraft& mission);

 private:
  IWorkspaceStore& store_;
  IHardwareInventory& hardware_;
  domain::WorkspaceState load() const;
  void save(const domain::WorkspaceState& state);
};

}  // namespace drone_agricole::application
