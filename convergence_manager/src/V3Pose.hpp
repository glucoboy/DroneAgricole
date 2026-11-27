#pragma once

#include <QJsonArray>
#include <QJsonObject>

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>

namespace convergence {

using V3Quaternion = std::array<double, 4>;
using V3Angles = std::array<double, 3>;

inline V3Quaternion v3CanonicalRotation(V3Quaternion value)
{
    double squaredNorm = 0;
    for (const auto component : value)
        squaredNorm += component * component;
    if (!std::isfinite(squaredNorm) || std::abs(squaredNorm - 1) > 1e-8)
        throw std::runtime_error("Quaternion XYZW non unitaire ou non fini");
    const double norm = std::sqrt(squaredNorm);
    // Inspect w first. At a half turn use z, then y, then x to select one sign.
    const auto first = std::find_if(value.rbegin(), value.rend(), [](double component) { return component != 0; });
    const double scale = *first < 0 ? -1.0 / norm : 1.0 / norm;
    for (auto &component : value)
        component = component == 0 ? 0 : component * scale;
    return value;
}

inline V3Quaternion v3MultiplyRotation(const V3Quaternion &left, const V3Quaternion &right)
{
    const auto [x, y, z, w] = left;
    const auto [i, j, k, r] = right;
    return {w*i + x*r + y*k - z*j, w*j - x*k + y*r + z*i,
            w*k + x*j - y*i + z*r, w*r - x*i - y*j - z*k};
}

inline QJsonArray v3RotationJson(const V3Quaternion &value)
{
    return {value[0], value[1], value[2], value[3]};
}

inline constexpr double v3RadiansPerDegree = 0.017453292519943295;

struct V3RotationBounds {
    V3Angles min, max;

    static V3RotationBounds read(const QJsonObject &value)
    {
        if (value.keys() != QStringList{"max_deg", "min_deg", "order"} || value.value("order") != "ROOT_XYZ")
            throw std::runtime_error("Domaine d'orientation ROOT_XYZ invalide");
        const auto low = value.value("min_deg").toArray(), high = value.value("max_deg").toArray();
        V3RotationBounds result{};
        if (low.size() != 3 || high.size() != 3)
            throw std::runtime_error("Bornes angulaires XYZ attendues");
        for (std::size_t axis = 0; axis < result.min.size(); ++axis) {
            const auto a = low.at(axis).toDouble(90), b = high.at(axis).toDouble(-90);
            if (!std::isfinite(a) || !std::isfinite(b) || a < -45 || b > 45 || a > b)
                throw std::runtime_error("Bornes angulaires hors domaine sans singularité");
            result.min[axis] = a;
            result.max[axis] = b;
        }
        return result;
    }

    V3Quaternion sample(const V3Quaternion &nominal, const V3Angles &fractions) const
    {
        V3Quaternion result = nominal;
        for (std::size_t axis = 0; axis < min.size(); ++axis) {
            const double half = (min[axis] + fractions[axis] * (max[axis] - min[axis])) * v3RadiansPerDegree / 2;
            V3Quaternion increment{0, 0, 0, std::cos(half)};
            increment[axis] = std::sin(half);
            result = v3MultiplyRotation(increment, result);
        }
        return v3CanonicalRotation(result);
    }

    V3Quaternion admit(const V3Quaternion &nominal, const V3Quaternion &candidate) const
    {
        const auto value = v3CanonicalRotation(candidate);
        const auto [i, j, k, scalar] = v3CanonicalRotation(nominal);
        const auto [x, y, z, w] = v3MultiplyRotation(value, {-i, -j, -k, scalar});
        const V3Angles angles{
            std::atan2(2*(w*x + y*z), 1 - 2*(x*x + y*y)) / v3RadiansPerDegree,
            std::asin(std::clamp(2*(w*y - z*x), -1.0, 1.0)) / v3RadiansPerDegree,
            std::atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z)) / v3RadiansPerDegree};
        constexpr double angularTolerance = 1e-8;
        for (std::size_t axis = 0; axis < min.size(); ++axis)
            if (angles[axis] < min[axis] - angularTolerance || angles[axis] > max[axis] + angularTolerance)
                throw std::runtime_error("Orientation hors domaine ROOT_XYZ scellé");
        return value;
    }
};

} // namespace convergence
