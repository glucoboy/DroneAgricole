#pragma once

#include <QDateTime>
#include <QDir>
#include <QJsonArray>
#include <QJsonObject>
#include <QMap>
#include <memory>

namespace convergence {

// The deployment provisions both files and controls the directory. One open
// journal owns the exclusive writer lock, including while native tools run.
class A6Journal final {
public:
    A6Journal(const QDir &trusted, const QString &keySha256,
              const QDateTime &observedAt = QDateTime::currentDateTimeUtc());
    ~A6Journal();

    void observeRegistry(const QJsonArray &events, const QDateTime &now);
    void reserve(const QString &id, const QString &reviewSha, const QString &requestSha);
    void transition(const QString &id, const QString &state, const QJsonObject &detail = {});
    QString state(const QString &id) const;

private:
    class File;
    void append(const QString &state, const QString &id, const QJsonObject &detail, const QDateTime &now);
    void apply(const QJsonObject &event, const QByteArray &mac);

    QDir trusted_;
    std::unique_ptr<File> file_;
    QByteArray key_;
    QByteArray previousMac_ = QByteArray(64, '0');
    QDateTime lastSeen_;
    QMap<QString, QString> decisions_;
    QString registryPrefix_;
    int registryEvents_ = 0;
    int sequence_ = 0;
    bool healthy_ = true;
};

} // namespace convergence
