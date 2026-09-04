#include "drone_agricole/core/TrajectoryAnalysis.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <numeric>

namespace drone_agricole::core {
namespace {

QQuaternion normalized(const QQuaternion& value) {
  if (value.lengthSquared() < 1e-16f) {
    throw ContractError(QStringLiteral("Quaternion de norme nulle dans la trajectoire"));
  }
  return value.normalized();
}

qsizetype nearestFutureIndex(const QList<TimedPose>& poses, const qsizetype first, const double target) {
  auto lower = std::lower_bound(poses.cbegin() + first + 1, poses.cend(), target,
                                [](const TimedPose& pose, const double value) { return pose.timeSeconds < value; });
  if (lower == poses.cend()) {
    return poses.size() - 1;
  }
  const auto after = static_cast<qsizetype>(std::distance(poses.cbegin(), lower));
  if (after <= first + 1) {
    return after;
  }
  const auto before = after - 1;
  return std::abs(poses[before].timeSeconds - target) <= std::abs(poses[after].timeSeconds - target) ? before : after;
}

}  // namespace

QJsonObject errorStatistics(const QList<double>& values) {
  if (values.isEmpty()) {
    throw ContractError(QStringLiteral("Aucune erreur mesurable"));
  }
  const auto total = std::accumulate(values.cbegin(), values.cend(), 0.0);
  const auto squares = std::accumulate(values.cbegin(), values.cend(), 0.0,
                                       [](const double sum, const double value) { return sum + value * value; });
  auto sorted = values;
  std::sort(sorted.begin(), sorted.end());
  const auto middle = sorted.size() / 2;
  const auto median = sorted.size() % 2 == 0 ? (sorted[middle - 1] + sorted[middle]) / 2.0 : sorted[middle];
  return {
      {QStringLiteral("rmse"), std::sqrt(squares / static_cast<double>(values.size()))},
      {QStringLiteral("mean"), total / static_cast<double>(values.size())},
      {QStringLiteral("median"), median},
      {QStringLiteral("maximum"), *std::max_element(values.cbegin(), values.cend())},
  };
}

double rotationErrorDegrees(const QQuaternion& reference, const QQuaternion& estimate) {
  const auto left = normalized(reference);
  const auto right = normalized(estimate);
  const auto dot = std::clamp(std::abs(QQuaternion::dotProduct(left, right)), 0.0f, 1.0f);
  return 2.0 * std::acos(static_cast<double>(dot)) * 180.0 / std::acos(-1.0);
}

RigidAlignment alignPositions(const QList<QVector3D>& source, const QList<QVector3D>& target) {
  if (source.size() != target.size() || source.size() < 3) {
    throw ContractError(QStringLiteral("L'alignement SE3 exige au moins trois paires"));
  }
  QVector3D sourceCenter;
  QVector3D targetCenter;
  for (qsizetype index = 0; index < source.size(); ++index) {
    sourceCenter += source[index];
    targetCenter += target[index];
  }
  sourceCenter /= static_cast<float>(source.size());
  targetCenter /= static_cast<float>(target.size());

  std::array<std::array<double, 3>, 3> covariance{};
  for (qsizetype index = 0; index < source.size(); ++index) {
    const auto a = source[index] - sourceCenter;
    const auto b = target[index] - targetCenter;
    const std::array<double, 3> left{a.x(), a.y(), a.z()};
    const std::array<double, 3> right{b.x(), b.y(), b.z()};
    for (int row = 0; row < 3; ++row) {
      for (int column = 0; column < 3; ++column) {
        covariance[row][column] += left[row] * right[column];
      }
    }
  }
  const auto& m = covariance;
  const auto trace = m[0][0] + m[1][1] + m[2][2];
  const std::array<std::array<double, 4>, 4> horn{{
      {{trace, m[1][2] - m[2][1], m[2][0] - m[0][2], m[0][1] - m[1][0]}},
      {{m[1][2] - m[2][1], m[0][0] - m[1][1] - m[2][2], m[0][1] + m[1][0], m[2][0] + m[0][2]}},
      {{m[2][0] - m[0][2], m[0][1] + m[1][0], -m[0][0] + m[1][1] - m[2][2], m[1][2] + m[2][1]}},
      {{m[0][1] - m[1][0], m[2][0] + m[0][2], m[1][2] + m[2][1], -m[0][0] - m[1][1] + m[2][2]}},
  }};
  std::array<double, 4> eigenvector{1.0, 0.0, 0.0, 0.0};
  for (int iteration = 0; iteration < 80; ++iteration) {
    std::array<double, 4> next{};
    for (int row = 0; row < 4; ++row) {
      for (int column = 0; column < 4; ++column) {
        next[row] += horn[row][column] * eigenvector[column];
      }
    }
    const auto norm = std::sqrt(std::inner_product(next.cbegin(), next.cend(), next.cbegin(), 0.0));
    if (norm < 1e-15) {
      break;
    }
    for (auto& value : next) {
      value /= norm;
    }
    eigenvector = next;
  }
  const auto rotation = normalized(QQuaternion(static_cast<float>(eigenvector[0]),
                                                static_cast<float>(eigenvector[1]),
                                                static_cast<float>(eigenvector[2]),
                                                static_cast<float>(eigenvector[3])));
  return RigidAlignment{rotation, targetCenter - rotation.rotatedVector(sourceCenter)};
}

QJsonObject computeRpe(const QList<TimedPose>& estimate,
                       const QList<TimedPose>& truth,
                       const double deltaSeconds,
                       const double toleranceSeconds) {
  if (estimate.size() != truth.size() || estimate.size() < 2) {
    throw ContractError(QStringLiteral("Les trajectoires RPE doivent être appariées"));
  }
  QList<double> translations;
  QList<double> rotations;
  QList<double> observedDeltas;
  for (qsizetype first = 0; first + 1 < estimate.size(); ++first) {
    const auto target = estimate[first].timeSeconds + deltaSeconds;
    const auto second = nearestFutureIndex(estimate, first, target);
    if (second <= first) {
      continue;
    }
    const auto observed = estimate[second].timeSeconds - estimate[first].timeSeconds;
    if (std::abs(observed - deltaSeconds) > toleranceSeconds) {
      continue;
    }
    const auto estimateFirstRotation = normalized(estimate[first].orientation);
    const auto truthFirstRotation = normalized(truth[first].orientation);
    const auto estimateTranslation = estimateFirstRotation.conjugated().rotatedVector(
        estimate[second].position - estimate[first].position);
    const auto truthTranslation = truthFirstRotation.conjugated().rotatedVector(
        truth[second].position - truth[first].position);
    const auto estimateRotation = estimateFirstRotation.conjugated() * normalized(estimate[second].orientation);
    const auto truthRotation = truthFirstRotation.conjugated() * normalized(truth[second].orientation);
    translations.append(static_cast<double>((estimateTranslation - truthTranslation).length()));
    rotations.append(rotationErrorDegrees(truthRotation, estimateRotation));
    observedDeltas.append(observed);
  }
  if (translations.isEmpty()) {
    throw ContractError(QStringLiteral("Aucune paire valide pour l'intervalle RPE demandé"));
  }
  const auto [minimum, maximum] = std::minmax_element(observedDeltas.cbegin(), observedDeltas.cend());
  const auto average = std::accumulate(observedDeltas.cbegin(), observedDeltas.cend(), 0.0) /
                       static_cast<double>(observedDeltas.size());
  return {
      {QStringLiteral("delta_s"), deltaSeconds},
      {QStringLiteral("delta_tolerance_s"), toleranceSeconds},
      {QStringLiteral("pairs"), observedDeltas.size()},
      {QStringLiteral("observed_delta_s"),
       QJsonObject{{QStringLiteral("minimum"), *minimum}, {QStringLiteral("mean"), average},
                   {QStringLiteral("maximum"), *maximum}}},
      {QStringLiteral("translation_m"), errorStatistics(translations)},
      {QStringLiteral("rotation_deg"), errorStatistics(rotations)},
  };
}

double trajectoryLength(const QList<QVector3D>& positions) {
  double length = 0.0;
  for (qsizetype index = 1; index < positions.size(); ++index) {
    length += static_cast<double>((positions[index] - positions[index - 1]).length());
  }
  return length;
}

}  // namespace drone_agricole::core
