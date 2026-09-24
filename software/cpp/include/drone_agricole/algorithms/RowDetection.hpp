#pragma once
#include <QList>
#include <QVector3D>
#include <functional>
#include <vector>
namespace drone_agricole::algorithms {
struct WeightedCell { double x{0.0}; double y{0.0}; double z{0.0}; double weight{0.0}; };
struct RowModel {
  double rho{0.0};
  double minimumT{0.0};
  double maximumT{0.0};
  QList<QVector3D> points;
};
struct RowDetectionSettings {
  double spanX;
  double spanY;
  double gridResolution;
  double minimumRowSpacing;
  double peakRatio;
};
struct WeightedRows { std::vector<RowModel> rows; int orientationDegrees{0}; };
// Coordonnées métriques locales. Le terrain est fourni dans le même repère.
// Ni fichier, ni dataset, ni vérité terrain d'évaluation dans ces entrées.
WeightedRows detectWeightedRows(const std::vector<WeightedCell>& active,
    const RowDetectionSettings& settings, const std::function<double(double, double)>& groundAt);
QList<RowModel> detectCaptureRows(const QList<QVector3D>& points, double binSize,
    double minimumSpacing, double peakRatio, double& orientationDegrees);
}
