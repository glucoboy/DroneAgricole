#pragma once
#include "drone_agricole/application/IStationServices.hpp"
#include "drone_agricole/adapters/ProcessRunBackend.hpp"
#include "drone_agricole/core/ContractRegistry.hpp"
#include "drone_agricole/core/RunnerRegistry.hpp"
#include "drone_agricole/core/ComparisonService.hpp"

namespace drone_agricole::composition {
class StationComposition final : public application::IStationServices,
                                 private application::IRunPreparation,
                                 private application::IResultFinalizer {
 public:
  explicit StationComposition(const QString& workspace);
  application::RunService& execution() override { return execution_; }
  QString workspace() const override { return contracts_.workspace(); }
  QList<core::SimulationDefinition> simulations() const override { return contracts_.simulations(); }
  QList<core::DatasetSequence> datasetSequences() const override { return contracts_.datasetSequences(); }
  const core::SimulationDefinition& simulation(const QString& id) const override { return contracts_.simulation(id); }
  const core::VariantDefinition& variant(const QString& simulation, const QString& id) const override { return contracts_.variant(simulation, id); }
  QList<core::DatasetSequence> compatibleSequences(const QString& simulation, const QString& variant) const override { return contracts_.compatibleSequences(simulation, variant); }
  QJsonObject resolveRequest(const QString& simulation, const QString& variant, const QString& profile,
                            const QString& dataset, const QString& sequence, const QJsonObject& parameters) const override {
    return contracts_.resolveRequest(simulation, variant, profile, dataset, sequence, parameters);
  }
  qsizetype schemaDocumentCount() const override { return contracts_.schemaDocumentCount(); }
  void refresh() override { repository_.refresh(); }
  QList<core::ResultSummary> search(const core::SearchFilters& filters = {}) const override { return repository_.search(filters); }
  core::ResultDetail detail(const QString& id) const override { return repository_.detail(id); }
  core::ReplayData replay(const QString& id) override { return repository_.replay(id); }
  qsizetype totalCount() const override { return repository_.totalCount(); }
  qsizetype invalidResultCount() const override { return repository_.invalidResultCount(); }
  QString resultsRoot() const override { return repository_.resultsRoot(); }
  core::ComparisonResult compare(const QStringList& ids) override { return comparison_.compare(ids); }
  void exportReport(const QString& path, const QString& report) override;
  void resetTelemetry() override;
  core::LiveTelemetrySnapshot snapshot() override;
 private:
  core::ContractRegistry contracts_;
  core::RunnerRegistry runners_;
  core::ResultRepository repository_;
  core::ComparisonService comparison_;
  std::unique_ptr<core::LiveTelemetry> telemetry_;
  adapters::ProcessRunBackend backend_;
  application::RunService execution_;
  domain::PreparedRun prepare(const QJsonObject& request) override;
  void finalize(const domain::PreparedRun& run) override;
};
}  // namespace drone_agricole::composition
