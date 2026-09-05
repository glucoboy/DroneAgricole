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
  // atan2 reste précis près de zéro, contrairement à acos d'un produit
  // scalaire arrondi en float (Qt stocke les quaternions en simple précision).
  const double aw = left.scalar(), ax = left.x(), ay = left.y(), az = left.z();
  const double bw = right.scalar(), bx = right.x(), by = right.y(), bz = right.z();
  const double w = aw * bw + ax * bx + ay * by + az * bz;
  const double x = aw * bx - ax * bw - ay * bz + az * by;
  const double y = aw * by + ax * bz - ay * bw - az * bx;
  const double z = aw * bz - ax * by + ay * bx - az * bw;
  return 2.0 * std::atan2(std::sqrt(x * x + y * y + z * z), std::abs(w)) *
         180.0 / std::acos(-1.0);
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
  std::array<std::array<double, 4>, 4> horn{{
      {{trace, m[1][2] - m[2][1], m[2][0] - m[0][2], m[0][1] - m[1][0]}},
      {{m[1][2] - m[2][1], m[0][0] - m[1][1] - m[2][2], m[0][1] + m[1][0], m[2][0] + m[0][2]}},
      {{m[2][0] - m[0][2], m[0][1] + m[1][0], -m[0][0] + m[1][1] - m[2][2], m[1][2] + m[2][1]}},
      {{m[0][1] - m[1][0], m[2][0] + m[0][2], m[1][2] + m[2][1], -m[0][0] - m[1][1] + m[2][2]}},
  }};
  // Jacobi diagonalise la matrice symétrique de Horn. Une itération de
  // puissance non décalée peut osciller sur les trajectoires planes : les
  // valeurs propres extrêmes y ont le même module et des signes opposés.
  std::array<std::array<double, 4>, 4> eigenvectors{};
  for (int i = 0; i < 4; ++i) {
    eigenvectors[i][i] = 1.0;
  }
  for (int iteration = 0; iteration < 80; ++iteration) {
    int p = 0;
    int q = 1;
    double scale = 0.0;
    for (int row = 0; row < 4; ++row) {
      scale = std::max(scale, std::abs(horn[row][row]));
      for (int column = row + 1; column < 4; ++column) {
        if (std::abs(horn[row][column]) > std::abs(horn[p][q])) {
          p = row;
          q = column;
        }
      }
    }
    if (std::abs(horn[p][q]) <= 1e-14 * std::max(scale, 1e-30)) {
      break;
    }
    const double angle = 0.5 * std::atan2(2.0 * horn[p][q], horn[q][q] - horn[p][p]);
    const double c = std::cos(angle);
    const double s = std::sin(angle);
    const double pp = horn[p][p];
    const double qq = horn[q][q];
    const double pq = horn[p][q];
    for (int k = 0; k < 4; ++k) {
      if (k != p && k != q) {
        const double kp = horn[k][p];
        const double kq = horn[k][q];
        horn[k][p] = horn[p][k] = c * kp - s * kq;
        horn[k][q] = horn[q][k] = s * kp + c * kq;
      }
      const double vp = eigenvectors[k][p];
      const double vq = eigenvectors[k][q];
      eigenvectors[k][p] = c * vp - s * vq;
      eigenvectors[k][q] = s * vp + c * vq;
    }
    horn[p][p] = c * c * pp - 2.0 * s * c * pq + s * s * qq;
    horn[q][q] = s * s * pp + 2.0 * s * c * pq + c * c * qq;
    horn[p][q] = horn[q][p] = 0.0;
  }
  int largest = 0;
  for (int i = 1; i < 4; ++i) {
    if (horn[i][i] > horn[largest][largest]) {
      largest = i;
    }
  }
  const auto rotation = normalized(QQuaternion(static_cast<float>(eigenvectors[0][largest]),
                                                static_cast<float>(eigenvectors[1][largest]),
                                                static_cast<float>(eigenvectors[2][largest]),
                                                static_cast<float>(eigenvectors[3][largest])));
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
