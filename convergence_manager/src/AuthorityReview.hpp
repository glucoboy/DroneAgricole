#pragma once

#include <QDir>
#include <QJsonObject>

namespace convergence {

constexpr auto a5AdmissionSchema = "v3.a5.admission_request/1";

QJsonObject verifyAuthorityReview(const QDir &root, const QDir &sandbox, const QJsonObject &request,
                                 const QString &requestSha256, const QString &trustPath,
                                 const QString &testTrustSha256, bool mutation);

} // namespace convergence
