#pragma once
#include "drone_agricole/algorithms/CameraColorFusion.hpp"
#include <QStringList>
#include <QJsonObject>
namespace drone_agricole::core {
QList<QStringList> friulBotImageSets(const QString& directory);
algorithms::CameraColorCloud colorFriulBotScan(const QList<QVector3D>& points,
                                             const QStringList& images, const QString& calibration);
QJsonObject runFriulBotReconstruction(const QJsonObject& options);
}
