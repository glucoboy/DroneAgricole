#pragma once

#include <QDir>
#include <QJsonObject>

#include <functional>

namespace convergence {

struct AuthorizedReview;

using AuthorizedNativeStage = std::function<void(const QString &state, const QJsonObject &detail)>;

QJsonObject runV3Mutation(const QDir &root, const QDir &sandbox, const QDir &output,
                          const QByteArray &planBytes, const QJsonObject &plan,
                          const QString &freecadPython, const QString &t0Validator);

QJsonObject runV3AuthorizedNative(const QDir &root, const QDir &sandbox, const QDir &output,
                                 const AuthorizedReview &authorization, const QString &freecadPython,
                                 const QString &t0Validator, const AuthorizedNativeStage &stage,
                                 bool simulateInterruptedSave = false);

} // namespace convergence
