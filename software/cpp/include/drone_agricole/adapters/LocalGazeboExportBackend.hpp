#pragma once
#include "drone_agricole/application/GazeboExportService.hpp"
namespace drone_agricole::adapters {
class LocalGazeboExportBackend final : public application::IGazeboExportBackend {
 public:
  explicit LocalGazeboExportBackend(QString workspace);
  QJsonObject inspect() const override;
  QJsonObject execute(const application::GazeboExportRequest&, const std::atomic_bool&, Progress) override;
  static QJsonObject preview(const QString& modelDirectory);
 private:
  QString workspace_;
};
}
