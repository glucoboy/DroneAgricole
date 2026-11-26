#pragma once

#include <algorithm>
#include <array>
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

} // namespace convergence
