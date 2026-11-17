#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QMap>

namespace interconnection {

using Index = QMap<QString, QJsonObject>;

struct Finding {
    QString domain;
    QString code;
    QString subject;
    QString status;
    QString reason;

    QJsonObject json() const;
};

using Findings = QList<Finding>;

Index index(const QJsonValue &records, const QString &collection);
bool sourced(const QJsonObject &value, const Index &evidence, bool synthetic);
QJsonObject findCompatibleMates(const QJsonObject &dossier, const QString &receptacleId);
QJsonObject validate(const QJsonObject &dossier, const QString &stateId,
                     const QJsonArray &researchReports);

class ConnectorCatalog {
public:
    ConnectorCatalog(const QJsonObject &dossier, Index evidence, bool synthetic);
    QJsonObject part(const QString &id) const;
    QString contactPart(const QJsonObject &reference) const;
    bool hasSource(const QJsonObject &value) const;
    Findings checkPair(const QString &receptacle, const QString &mate,
                       const QJsonObject &requirements, const QString &subject) const;
    QJsonObject pair(const QString &receptacle, const QString &mate) const;
    QJsonArray bom(const QMap<QString, int> &used) const;
    QJsonArray matches(const QString &receptacle) const;

private:
    Index parts_;
    QMap<QPair<QString, QString>, QJsonObject> pairs_;
    Index evidence_;
    bool synthetic_;
};

QJsonObject checkGeometry(const QJsonObject &dossier, const QJsonObject &state,
                         const QJsonArray &interfaces, Findings &findings);

} // namespace interconnection
