#pragma once

#include "drone_agricole/station/StationArchitecture.hpp"

#include <QDateTime>
#include <QJsonObject>
#include <QList>
#include <QStringList>

namespace drone_agricole::station {

struct PackageReference {
  PackageKind kind;
  QString packageId;
  QString version;
  QString manifestPath;
  QString contentDigest;
  QString approvalEvidenceReference;
};

struct StationOperationRequest {
  QString operationId;
  QString moduleId;
  QList<PackageReference> inputs;
  QString outputWorkspace;
  QJsonObject parameters;
  QDateTime requestedAtUtc;
};

struct StationValidationIssue {
  QString code;
  QString message;
  bool blocking{true};
};

// Contrat minimal des modules métier. L'exécution concrète restera portée par
// un adaptateur headless afin de ne pas lier les algorithmes à Qt Widgets.
class IStationModule {
 public:
  virtual ~IStationModule() = default;

  [[nodiscard]] virtual StationModuleDescriptor descriptor() const = 0;
  [[nodiscard]] virtual QList<StationValidationIssue> validate(const StationOperationRequest& request) const = 0;
};

}  // namespace drone_agricole::station
