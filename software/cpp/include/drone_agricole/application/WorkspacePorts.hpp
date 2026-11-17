#pragma once

#include "drone_agricole/domain/WorkspaceTypes.hpp"

namespace drone_agricole::application {

class IWorkspaceStore {
 public:
  virtual ~IWorkspaceStore() = default;
  virtual QJsonObject load() const = 0;
  // L'adaptateur refuse une modification concurrente depuis la dernière lecture.
  virtual void save(const QJsonObject& document) = 0;
  virtual QString path() const = 0;
  virtual bool exists() const = 0;
  virtual QJsonObject readMissionDocument(const QString& path) const = 0;
  virtual void writeMissionDocument(const QString& path, const QJsonObject& document) const = 0;
};

class IHardwareInventory {
 public:
  virtual ~IHardwareInventory() = default;
  virtual domain::HardwareInventory load() const = 0;
  virtual QString sourcePath() const = 0;
};

}  // namespace drone_agricole::application
