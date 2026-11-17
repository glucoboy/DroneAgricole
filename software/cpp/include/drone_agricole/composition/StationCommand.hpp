#pragma once
#include <QJsonObject>
namespace drone_agricole::composition {
int runStationCommand(const QJsonObject& options);
int runStationWorkspaceCommand(const QJsonObject& options);
int runGazeboModelCommand(const QJsonObject& options);
}
