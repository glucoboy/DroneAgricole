#pragma once

#include "drone_agricole/application/WorkspacePorts.hpp"
#include <QByteArray>

namespace drone_agricole::adapters {

class JsonWorkspaceStore final : public application::IWorkspaceStore {
 public:
  explicit JsonWorkspaceStore(const QString& workspace);
  QJsonObject load() const override;
  void save(const QJsonObject& document) override;
  QString path() const override { return path_; }
  bool exists() const override;
  QJsonObject readMissionDocument(const QString& path) const override;
  void writeMissionDocument(const QString& path, const QJsonObject& document) const override;
 private:
  QString workspace_;
  QString path_;
  mutable QByteArray lastReadDigest_;
  mutable bool hasLoaded_{false};
  void validateStateLocation() const;
};

}  // namespace drone_agricole::adapters
