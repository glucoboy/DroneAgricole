#pragma once

#include <QDateTime>
#include <QJsonArray>
#include <QJsonObject>
#include <QMap>
#include <QString>

namespace architecture_decision {

struct EvidenceContext {
    QString lot = "l3";
    QString runner = "architecture_decision_core";
    QString variant = "synthetic";
    QString domain = "SYNTHETIC_BENCH";
    QString startedMessage = "Exploration des bancs L3 lancée";
    QString finishedMessage = "Résultats des bancs L3 publiés";
    QString failedVerdict;
};

class Evidence {
public:
    Evidence(const QString &output, const QJsonArray &inputs, const QJsonObject &parameters,
             const QJsonObject &software, const EvidenceContext &context = {});

    void finalize(const QJsonObject &campaign, const QMap<QString, QString> &published);

private:
    QString output_;
    QString runId_;
    QJsonObject request_;
    QJsonObject software_;
    QString requestDigest_;
    QDateTime startedAt_;
    EvidenceContext context_;
};

} // namespace architecture_decision
