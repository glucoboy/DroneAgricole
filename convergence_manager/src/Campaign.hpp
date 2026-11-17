#pragma once

#include <QDir>
#include <QJsonObject>
#include <functional>

namespace convergence {

class Backend {
public:
    virtual ~Backend() = default;
    virtual QJsonObject inventory() = 0;
    virtual QJsonObject research(const QString &issue, const QDir &operation) = 0;
    virtual QJsonObject explore(const QDir &operation) = 0;
    virtual QJsonObject build(const QJsonObject &assignments, const QDir &operation) = 0;
    virtual QJsonObject validate(const QJsonObject &built, const QDir &operation) = 0;
};

class Campaign {
public:
    Campaign(QDir output, QJsonObject config, QJsonObject manifest, Backend &backend);
    int run(int steps = -1);

private:
    void advance();
    void transition(const QString &state);
    void checkpoint();
    void precheck();
    void diagnose();
    void changeFamily();
    void consolidate();
    void revalidate();
    void verdict();
    QJsonObject finalOutcome() const;
    void recordAttempt(QJsonObject observation);
    QJsonObject operation(const QString &kind, const QString &area, const QString &id,
                          const std::function<QJsonObject(const QDir &)> &execute);
    QJsonObject applied(const QJsonObject &candidate) const;
    QJsonObject candidate(const QString &id) const;
    QJsonObject problem(const QString &id) const;
    QString reference() const;
    int budget(const QString &name) const;

    QDir output_;
    QJsonObject config_;
    QJsonObject manifest_;
    QJsonObject state_;
    Backend &backend_;
};

} // namespace convergence
