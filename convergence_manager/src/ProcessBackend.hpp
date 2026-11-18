#pragma once

#include "Campaign.hpp"

namespace convergence {

struct ToolPaths {
    QString l1, l3, l4, python, freecad;
};

class ProcessBackend final : public Backend {
public:
    ProcessBackend(QDir root, QDir output, QJsonObject config, ToolPaths tools);
    static QJsonObject buildV3(const QDir &root, const QDir &sandbox, const QJsonObject &request);
    QJsonObject freeze(const QString &configPath);
    void verify() const;
    void verifyConsolidation(const QJsonObject &outcome) const;
    QJsonObject inventory() override;
    QJsonObject research(const QString &issue, const QDir &operation) override;
    QJsonObject explore(const QDir &operation) override;
    QJsonObject build(const QJsonObject &assignments, const QDir &operation) override;
    QJsonObject validate(const QJsonObject &built, const QDir &operation) override;

private:
    QJsonObject readValidation(const QJsonObject &built, const QDir &out, const QString &caseId,
                               const QString &portfolio, int code) const;
    QDir root_, output_;
    QJsonObject config_, manifest_;
    ToolPaths tools_;
};

QJsonObject verifyEvidence(const QDir &directory, const QString &lot);

} // namespace convergence
