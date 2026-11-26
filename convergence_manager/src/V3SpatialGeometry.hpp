#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <utility>
#include <vector>

namespace convergence {

using V3Point = std::array<double, 3>;

struct V3Box {
    V3Point min;
    V3Point max;
};

inline bool v3SegmentInBoxes(const V3Point &start, const V3Point &end, const std::vector<V3Box> &boxes)
{
    constexpr double tolerance = 1e-7;
    std::vector<std::pair<double, double>> intervals;
    for (const auto &box : boxes) {
        double first = 0, last = 1;
        for (int axis = 0; axis < 3 && first <= last; ++axis) {
            const auto delta = end[axis] - start[axis];
            if (delta == 0) {
                if (start[axis] < box.min[axis] - tolerance || start[axis] > box.max[axis] + tolerance)
                    first = 2;
                continue;
            }
            const auto a = (box.min[axis] - tolerance - start[axis]) / delta;
            const auto b = (box.max[axis] + tolerance - start[axis]) / delta;
            first = std::max(first, std::min(a, b));
            last = std::min(last, std::max(a, b));
        }
        if (first <= last)
            intervals.emplace_back(first, last);
    }
    std::sort(intervals.begin(), intervals.end());
    double covered = 0;
    for (const auto &[first, last] : intervals) {
        if (first > covered)
            return false;
        covered = std::max(last, covered);
    }
    return covered == 1;
}

// Between successive crossings of a box plane, membership in the union is constant.
inline bool v3ArcInBoxes(const V3Point &center, const V3Point &radial, const V3Point &tangent,
                         double sweep, const std::vector<V3Box> &boxes)
{
    constexpr double tolerance = 1e-7;
    constexpr double turn = 6.2831853071795864769;
    std::vector<double> events{0, sweep};
    for (const auto &box : boxes) {
        for (int axis = 0; axis < 3; ++axis) {
            const auto amplitude = std::hypot(radial[axis], tangent[axis]);
            if (amplitude == 0)
                continue;
            const auto phase = std::atan2(tangent[axis], radial[axis]);
            for (const auto boundary : {box.min[axis] - tolerance, box.max[axis] + tolerance}) {
                const auto ratio = (boundary - center[axis]) / amplitude;
                if (std::abs(ratio) > 1)
                    continue;
                const auto angle = std::acos(ratio);
                for (const auto root : {phase - angle, phase + angle}) {
                    for (const auto shift : {-turn, 0.0, turn}) {
                        const auto parameter = root + shift;
                        if (parameter > 0 && parameter < sweep)
                            events.push_back(parameter);
                    }
                }
            }
        }
    }
    std::sort(events.begin(), events.end());
    for (std::size_t index = 1; index < events.size(); ++index) {
        const auto middle = (events[index - 1] + events[index]) / 2;
        const auto cosine = std::cos(middle), sine = std::sin(middle);
        V3Point point{};
        for (int axis = 0; axis < 3; ++axis)
            point[axis] = center[axis] + radial[axis] * cosine + tangent[axis] * sine;
        const auto inside = std::any_of(boxes.begin(), boxes.end(), [&](const auto &box) {
            for (int axis = 0; axis < 3; ++axis)
                if (point[axis] < box.min[axis] - tolerance || point[axis] > box.max[axis] + tolerance)
                    return false;
            return true;
        });
        if (!inside)
            return false;
    }
    return true;
}

} // namespace convergence
