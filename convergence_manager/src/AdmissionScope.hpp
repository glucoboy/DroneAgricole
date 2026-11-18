#pragma once

#include <QDir>
#include <QJsonObject>

namespace convergence {

// The root supplies the shipped policy evidence. The sandbox is a private input copy.
// The decision is for the evaluated request only and never certifies a result.
QJsonObject evaluateAdmissionScope(const QDir &root, const QDir &sandbox, const QJsonObject &request);

// B.1 profiles are reviewed, byte-pinned extensions of the A.1 bench policy.
QJsonObject loadMutationProfile(const QDir &root, const QString &sha);
QJsonObject mutationAdmissionRequest(const QJsonObject &profile, const QString &sha, const QJsonObject &action);

} // namespace convergence
