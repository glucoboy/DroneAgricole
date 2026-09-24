#include "drone_agricole/algorithms/RowDetection.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
namespace drone_agricole::algorithms {
namespace {
constexpr double pi = 3.14159265358979323846;
double percentile(std::vector<double> values, double ratio) {
  if (values.empty()) return std::numeric_limits<double>::quiet_NaN();
  std::sort(values.begin(), values.end());
  return values[static_cast<std::size_t>(std::clamp(ratio, 0.0, 1.0) * (values.size() - 1))];
}
}
WeightedRows detectWeightedRows(const std::vector<WeightedCell>& active,
    const RowDetectionSettings& settings, const std::function<double(double, double)>& groundAt) {
  if (active.empty() || !std::isfinite(settings.gridResolution) || settings.gridResolution <= 0.0 ||
      !std::isfinite(settings.spanX) || !std::isfinite(settings.spanY) || settings.spanX < 0.0 || settings.spanY < 0.0)
    throw core::ContractError(QStringLiteral("Entrées de détection des rangs invalides"));
  const auto spanX = settings.spanX;
  const auto spanY = settings.spanY;
  const auto diagonal = std::hypot(spanX, spanY);
  const auto rhoBinSize = settings.gridResolution;
  const auto rhoBinCount = static_cast<int>(std::ceil(2.0 * diagonal / rhoBinSize)) + 1;
  std::vector<double> bins(static_cast<std::size_t>(rhoBinCount), 0.0);
  double bestScore = -1.0;
  int bestAngleDegrees = 0;
  for (int angleDegrees = 0; angleDegrees < 180; ++angleDegrees) {
    std::fill(bins.begin(), bins.end(), 0.0);
    const auto angle = angleDegrees * pi / 180.0;
    const auto normalX = -std::sin(angle);
    const auto normalY = std::cos(angle);
    for (const auto& cell : active) {
      const auto rho = normalX * cell.x + normalY * cell.y;
      const auto bin = static_cast<int>(std::floor((rho + diagonal) / rhoBinSize));
      if (bin >= 0 && bin < rhoBinCount) {
        bins[static_cast<std::size_t>(bin)] += cell.weight;
      }
    }
    const auto score = std::accumulate(bins.cbegin(), bins.cend(), 0.0,
                                       [](const double sum, const double value) { return sum + value * value; });
    if (score > bestScore) {
      bestScore = score;
      bestAngleDegrees = angleDegrees;
    }
  }

  const auto angle = bestAngleDegrees * pi / 180.0;
  const auto tangentX = std::cos(angle);
  const auto tangentY = std::sin(angle);
  const auto normalX = -tangentY;
  const auto normalY = tangentX;
  std::fill(bins.begin(), bins.end(), 0.0);
  for (const auto& cell : active) {
    const auto rho = normalX * cell.x + normalY * cell.y;
    const auto bin = static_cast<int>(std::floor((rho + diagonal) / rhoBinSize));
    if (bin >= 0 && bin < rhoBinCount) {
      bins[static_cast<std::size_t>(bin)] += cell.weight;
    }
  }
  std::vector<double> smooth(bins.size(), 0.0);
  const auto smoothingRadius = std::max(1, static_cast<int>(std::llround(0.35 / rhoBinSize)));
  for (int index = 0; index < rhoBinCount; ++index) {
    double total = 0.0;
    double weights = 0.0;
    for (int delta = -smoothingRadius; delta <= smoothingRadius; ++delta) {
      const auto source = index + delta;
      if (source < 0 || source >= rhoBinCount) {
        continue;
      }
      const auto weight = static_cast<double>(smoothingRadius + 1 - std::abs(delta));
      total += bins[static_cast<std::size_t>(source)] * weight;
      weights += weight;
    }
    smooth[static_cast<std::size_t>(index)] = total / std::max(1.0, weights);
  }
  const auto maximumPeak = *std::max_element(smooth.cbegin(), smooth.cend());
  std::vector<int> peakCandidates;
  for (int index = 1; index + 1 < rhoBinCount; ++index) {
    if (smooth[static_cast<std::size_t>(index)] >= maximumPeak * settings.peakRatio &&
        smooth[static_cast<std::size_t>(index)] >= smooth[static_cast<std::size_t>(index - 1)] &&
        smooth[static_cast<std::size_t>(index)] > smooth[static_cast<std::size_t>(index + 1)]) {
      peakCandidates.push_back(index);
    }
  }
  std::sort(peakCandidates.begin(), peakCandidates.end(), [&](const int left, const int right) {
    return smooth[static_cast<std::size_t>(left)] > smooth[static_cast<std::size_t>(right)];
  });
  std::vector<int> selectedPeaks;
  const auto minimumPeakBins = std::max(1, static_cast<int>(std::ceil(settings.minimumRowSpacing / rhoBinSize)));
  for (const auto candidate : peakCandidates) {
    const auto tooClose = std::any_of(selectedPeaks.cbegin(), selectedPeaks.cend(), [&](const int selected) {
      return std::abs(candidate - selected) < minimumPeakBins;
    });
    if (!tooClose) {
      selectedPeaks.push_back(candidate);
    }
    if (selectedPeaks.size() >= 64) {
      break;
    }
  }
  std::sort(selectedPeaks.begin(), selectedPeaks.end());

  std::vector<RowModel> rows;
  const auto rowHalfWidth = std::clamp(settings.minimumRowSpacing * 0.34, 0.35, 0.75);
  for (const auto peak : selectedPeaks) {
    const auto rho = (peak + 0.5) * rhoBinSize - diagonal;
    std::vector<double> tangential;
    for (const auto& cell : active) {
      const auto cellRho = normalX * cell.x + normalY * cell.y;
      if (std::abs(cellRho - rho) <= rowHalfWidth) {
        tangential.push_back(tangentX * cell.x + tangentY * cell.y);
      }
    }
    if (tangential.size() < 8) {
      continue;
    }
    const auto minimumT = percentile(tangential, 0.03);
    const auto maximumT = percentile(tangential, 0.97);
    if (!std::isfinite(minimumT) || !std::isfinite(maximumT) || maximumT - minimumT < 8.0) {
      continue;
    }
    RowModel row;
    row.rho = rho;
    row.minimumT = minimumT;
    row.maximumT = maximumT;
    const auto segmentCount = std::max(2, static_cast<int>(std::ceil((maximumT - minimumT) / 2.0)) + 1);
    for (int segment = 0; segment < segmentCount; ++segment) {
      const auto ratio = static_cast<double>(segment) / (segmentCount - 1);
      const auto t = minimumT + ratio * (maximumT - minimumT);
      const auto localX = tangentX * t + normalX * rho;
      const auto localY = tangentY * t + normalY * rho;


      const auto terrain = groundAt(localX, localY);
      row.points.append(QVector3D(static_cast<float>(localX), static_cast<float>(localY),
                                  static_cast<float>((std::isfinite(terrain) ? terrain : 0.0) -
                                                     0.0 + 1.2)));
    }
    rows.push_back(std::move(row));
  }
  return {std::move(rows), bestAngleDegrees};
}

QList<RowModel> detectCaptureRows(const QList<QVector3D>& points,
                           const double binSize,
                           const double minimumSpacing,
                           const double peakRatio,
                           double& orientationDegrees) {
  if (points.size() < 80) {
    throw core::ContractError(QStringLiteral("Le scan synchronisé contient trop peu de points de végétation"));
  }
  double diagonal = 0.0;
  for (const auto& point : points) {
    diagonal = std::max(diagonal, std::hypot(static_cast<double>(point.x()), static_cast<double>(point.y())));
  }
  const auto binCount = std::max(3, static_cast<int>(std::ceil(2.0 * diagonal / binSize)) + 1);
  std::vector<double> bins(static_cast<std::size_t>(binCount), 0.0);
  double bestScore = -1.0;
  int bestAngle = 0;
  for (int angleDegrees = 0; angleDegrees < 180; ++angleDegrees) {
    std::fill(bins.begin(), bins.end(), 0.0);
    const auto angle = angleDegrees * pi / 180.0;
    const auto normalX = -std::sin(angle);
    const auto normalY = std::cos(angle);
    for (const auto& point : points) {
      const auto rho = normalX * point.x() + normalY * point.y();
      const auto bin = static_cast<int>(std::floor((rho + diagonal) / binSize));
      if (bin >= 0 && bin < binCount) {
        bins[static_cast<std::size_t>(bin)] += 1.0;
      }
    }
    const auto score = std::accumulate(bins.cbegin(), bins.cend(), 0.0,
                                       [](const double sum, const double value) { return sum + value * value; });
    if (score > bestScore) {
      bestScore = score;
      bestAngle = angleDegrees;
    }
  }
  orientationDegrees = bestAngle;
  const auto angle = bestAngle * pi / 180.0;
  const auto tangentX = std::cos(angle);
  const auto tangentY = std::sin(angle);
  const auto normalX = -tangentY;
  const auto normalY = tangentX;
  std::fill(bins.begin(), bins.end(), 0.0);
  for (const auto& point : points) {
    const auto rho = normalX * point.x() + normalY * point.y();
    const auto bin = static_cast<int>(std::floor((rho + diagonal) / binSize));
    if (bin >= 0 && bin < binCount) {
      bins[static_cast<std::size_t>(bin)] += 1.0;
    }
  }
  std::vector<double> smooth(bins.size(), 0.0);
  for (int index = 0; index < binCount; ++index) {
    for (int delta = -1; delta <= 1; ++delta) {
      if (index + delta >= 0 && index + delta < binCount) {
        smooth[static_cast<std::size_t>(index)] += bins[static_cast<std::size_t>(index + delta)] *
                                                   (delta == 0 ? 2.0 : 1.0);
      }
    }
  }
  const auto maximum = *std::max_element(smooth.cbegin(), smooth.cend());
  std::vector<int> candidates;
  for (int index = 1; index + 1 < binCount; ++index) {
    if (smooth[static_cast<std::size_t>(index)] >= maximum * peakRatio &&
        smooth[static_cast<std::size_t>(index)] >= smooth[static_cast<std::size_t>(index - 1)] &&
        smooth[static_cast<std::size_t>(index)] > smooth[static_cast<std::size_t>(index + 1)]) {
      candidates.push_back(index);
    }
  }
  std::sort(candidates.begin(), candidates.end(), [&](const int left, const int right) {
    return smooth[static_cast<std::size_t>(left)] > smooth[static_cast<std::size_t>(right)];
  });
  std::vector<int> selected;
  const auto spacingBins = std::max(1, static_cast<int>(std::ceil(minimumSpacing / binSize)));
  for (const auto candidate : candidates) {
    if (std::none_of(selected.cbegin(), selected.cend(), [&](const int value) {
          return std::abs(value - candidate) < spacingBins;
        })) {
      selected.push_back(candidate);
    }
    if (selected.size() >= 12) {
      break;
    }
  }
  std::sort(selected.begin(), selected.end());
  QList<RowModel> rows;
  for (const auto peak : selected) {
    const auto rho = (peak + 0.5) * binSize - diagonal;
    std::vector<double> tangential;
    for (const auto& point : points) {
      if (std::abs(normalX * point.x() + normalY * point.y() - rho) <= 0.55) {
        tangential.push_back(tangentX * point.x() + tangentY * point.y());
      }
    }
    if (tangential.size() < 12) {
      continue;
    }
    const auto minimumT = percentile(tangential, 0.05);
    const auto maximumT = percentile(tangential, 0.95);
    if (maximumT - minimumT < 3.0) {
      continue;
    }
    RowModel row;
    row.rho = rho;
    row.minimumT = minimumT;
    row.maximumT = maximumT;
    const auto segments = std::max(2, static_cast<int>(std::ceil((maximumT - minimumT) / 1.0)) + 1);
    for (int segment = 0; segment < segments; ++segment) {
      const auto ratio = static_cast<double>(segment) / (segments - 1);
      const auto t = minimumT + ratio * (maximumT - minimumT);
      row.points.append(QVector3D(static_cast<float>(tangentX * t + normalX * rho),
                                  static_cast<float>(tangentY * t + normalY * rho), 0.0F));
    }
    rows.append(std::move(row));
  }
  return rows;
}


}