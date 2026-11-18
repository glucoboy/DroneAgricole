#pragma once

#include <QDir>
#include <QJsonObject>

namespace convergence {

void require(bool valid, const QString &message);
QByteArray read(const QString &path);
QString digest(const QByteArray &bytes);
QString fileDigest(const QString &path);
QJsonObject parse(const QByteArray &bytes, const QString &source);
QJsonObject load(const QString &path);
QString write(const QString &path, const QByteArray &bytes);
QString write(const QString &path, const QJsonObject &object);
QString fileInside(const QDir &root, const QString &path);
QString relative(const QDir &root, const QString &path);
bool hasRedirectedComponent(const QDir &root, const QString &absolutePath);
QString identifier(const QJsonValue &value);

} // namespace convergence
