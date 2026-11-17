#pragma once
#include <QString>
namespace cartographe::gazebo {
// Generates the declared synthetic scenario from verified CAD derivatives.
// Does not change the CAD, identify physical properties or start Gazebo/PX4.
void generateModel(const QString& workspace, const QString& modelDirectory,
                   const QString& airframePath);
}
