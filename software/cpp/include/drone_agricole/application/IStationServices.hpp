#pragma once
#include "drone_agricole/application/RunService.hpp"
#include "drone_agricole/core/Types.hpp"
#include "drone_agricole/core/LiveTelemetry.hpp"

namespace drone_agricole::application {
// Façade des cas d'usage existants. Aucune implémentation de stockage ou de
// transport ne traverse cette frontière vers les pages.
class IStationServices {
 public:
  virtual ~IStationServices() = default;
  virtual RunService& execution() = 0;
  virtual QString workspace() const = 0;
  virtual QList<core::SimulationDefinition> simulations() const = 0;
  virtual QList<core::DatasetSequence> datasetSequences() const = 0;
  virtual const core::SimulationDefinition& simulation(const QString& id) const = 0;
  virtual const core::VariantDefinition& variant(const QString& simulation, const QString& id) const = 0;
  virtual QList<core::DatasetSequence> compatibleSequences(const QString& simulation, const QString& variant) const = 0;
  virtual QJsonObject resolveRequest(const QString& simulation, const QString& variant, const QString& profile,
                                    const QString& dataset, const QString& sequence, const QJsonObject& parameters) const = 0;
  virtual qsizetype schemaDocumentCount() const = 0;
  virtual void refresh() = 0;
  virtual QList<core::ResultSummary> search(const core::SearchFilters& filters = {}) const = 0;
  virtual core::ResultDetail detail(const QString& id) const = 0;
  virtual core::ReplayData replay(const QString& id) = 0;
  virtual qsizetype totalCount() const = 0;
  virtual qsizetype invalidResultCount() const = 0;
  virtual QString resultsRoot() const = 0;
  virtual core::ComparisonResult compare(const QStringList& ids) = 0;
  virtual void exportReport(const QString& path, const QString& report) = 0;
  virtual void resetTelemetry() = 0;
  virtual core::LiveTelemetrySnapshot snapshot() = 0;
};
}  // namespace drone_agricole::application
