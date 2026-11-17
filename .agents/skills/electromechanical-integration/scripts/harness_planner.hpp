#pragma once
#include <QJsonObject>
#include <QString>
namespace harness {
QJsonObject plan(const QJsonObject& input);
QJsonObject validate(const QJsonObject& input, const QJsonObject& candidate);
QString markdown(const QJsonObject& report);
}
