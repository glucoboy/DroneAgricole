#pragma once

#include "drone_agricole/application/WorkspacePorts.hpp"

namespace drone_agricole::adapters {

class BomHardwareInventory final : public application::IHardwareInventory {
 public:
  explicit BomHardwareInventory(const QString& workspace);
  domain::HardwareInventory load() const override;
  QString sourcePath() const override { return path_; }
 private:
  QString path_;
};

}  // namespace drone_agricole::adapters
