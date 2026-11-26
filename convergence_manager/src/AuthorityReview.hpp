#pragma once

#include <QDateTime>
#include <QDir>
#include <QJsonArray>
#include <QJsonObject>

#include <functional>

namespace convergence {

constexpr auto a5AdmissionSchema = "v3.a5.admission_request/1";
constexpr auto a6AdmissionSchema = "v3.a6.admission_request/1";
constexpr auto a6EvidencePackage = "v3.a6.private_evidence/1";

struct AuthorizedReview {
    QDir trusted;
    QString journalKeySha256;
    QString decisionId;
    QString reviewSha256;
    QString requestSha256;
    QString profilePath;
    QString trustSha256;
    QJsonObject bindings;
    QJsonObject effect;
    QDateTime expiresAt;
    QString registrySha256;
};

using AuthorityRegistryHook = std::function<void(const AuthorizedReview &, const QJsonArray &events,
                                                const QDateTime &now, const QString &denial)>;

QJsonObject verifyAuthorityReview(const QDir &root, const QDir &sandbox, const QJsonObject &request,
                                 const QString &requestSha256, const QString &trustPath,
                                 const QString &testTrustSha256, bool mutation,
                                 const AuthorityRegistryHook &hook = {}, bool finalizing = false);

} // namespace convergence
