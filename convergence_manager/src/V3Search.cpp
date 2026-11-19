#include "V3Search.hpp"

#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QSet>

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <optional>
#include <random>
#include <stdexcept>
#include <vector>

namespace convergence {
namespace {

constexpr double epsilon = 1e-7;
using Vector = std::array<double, 3>;
using Matrix = std::array<double, 16>;
using Quaternion = std::array<double, 4>;

void require(bool ok, const char *reason)
{
    if (!ok)
        throw std::runtime_error(reason);
}

template<std::size_t N>
std::array<double, N> numbers(const QJsonValue &value)
{
    const auto sequence = value.toArray();
    require(sequence.size() == static_cast<qsizetype>(N), "Coordonnées ou matrice manquantes");
    std::array<double, N> result{};
    for (std::size_t index = 0; index < N; ++index) {
        result[index] = sequence.at(index).toDouble(std::numeric_limits<double>::quiet_NaN());
        require(std::isfinite(result[index]), "Coordonnée non finie");
    }
    return result;
}

QJsonArray json(Vector value)
{
    return {value[0], value[1], value[2]};
}

Vector add(Vector a, Vector b)
{
    return {a[0] + b[0], a[1] + b[1], a[2] + b[2]};
}

Vector subtract(Vector a, Vector b)
{
    return {a[0] - b[0], a[1] - b[1], a[2] - b[2]};
}

Vector scale(Vector value, double factor)
{
    return {factor * value[0], factor * value[1], factor * value[2]};
}

double dot(Vector first, Vector second)
{
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2];
}

Vector cross(Vector first, Vector second)
{
    return {first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0]};
}

double norm(Vector value)
{
    return std::sqrt(dot(value, value));
}

Vector unit(Vector value)
{
    const double length = norm(value);
    require(length > epsilon, "Direction de sortie ou axe indéterminé");
    return scale(value, 1.0 / length);
}

Vector origin(const Matrix &matrix)
{
    return {matrix[3], matrix[7], matrix[11]};
}

struct Bounds {
    Vector min;
    Vector max;
};

Bounds readBounds(const QJsonValue &value)
{
    const auto corners = value.toArray();
    require(corners.size() == 2, "Enveloppe de solide absente");
    return {numbers<3>(corners.at(0)), numbers<3>(corners.at(1))};
}

bool contains(const Bounds &box, Vector point)
{
    for (int axis = 0; axis < 3; ++axis)
        if (point[axis] < box.min[axis] - epsilon || point[axis] > box.max[axis] + epsilon)
            return false;
    return true;
}

template<typename Transform>
Bounds transformBounds(const Bounds &box, Transform transform)
{
    Bounds result{transform(box.min), transform(box.min)};
    for (int corner = 1; corner < 8; ++corner) {
        const Vector point = transform({corner & 1 ? box.max[0] : box.min[0],
                                        corner & 2 ? box.max[1] : box.min[1],
                                        corner & 4 ? box.max[2] : box.min[2]});
        for (int axis = 0; axis < 3; ++axis) {
            result.min[axis] = std::min(result.min[axis], point[axis]);
            result.max[axis] = std::max(result.max[axis], point[axis]);
        }
    }
    return result;
}

Vector movedPoint(Vector point, const Matrix &original, Vector location, const Quaternion &rotation)
{
    const Vector delta = subtract(point, origin(original));
    const Vector local{dot(delta, {original[0], original[4], original[8]}),
                       dot(delta, {original[1], original[5], original[9]}),
                       dot(delta, {original[2], original[6], original[10]})};
    const Vector axis{rotation[0], rotation[1], rotation[2]};
    const Vector product = scale(cross(axis, local), 2.0);
    return add(location, add(local, add(scale(product, rotation[3]), cross(axis, product))));
}

struct RouteFrame {
    Vector start;
    Vector forward;
    Vector side;
    Vector normal;

    Vector local(Vector point) const
    {
        const Vector offset = subtract(point, start);
        return {dot(offset, forward), dot(offset, side), dot(offset, normal)};
    }

    Vector world(Vector point) const
    {
        return add(start, add(scale(forward, point[0]), add(scale(side, point[1]), scale(normal, point[2]))));
    }
};

RouteFrame routeFrame(Vector start, Vector startAxis, Vector endAxis)
{
    const auto forward = unit(startAxis);
    require(dot(forward, unit(endAxis)) < -1 + epsilon, "Terminaisons non opposées dans ce corridor");
    // Choose the most stable lateral axis, using the normal of the usual horizontal plane when possible.
    const Vector reference = std::abs(forward[2]) < 0.9 ? Vector{0, 0, 1} : Vector{0, 1, 0};
    const auto side = unit(cross(reference, forward));
    return {start, forward, side, cross(forward, side)};
}

double boxGap(const Bounds &a, const Bounds &b)
{
    Vector separation{};
    for (int axis = 0; axis < 3; ++axis)
        separation[axis] = std::max({0.0, a.min[axis] - b.max[axis], b.min[axis] - a.max[axis]});
    return norm(separation);
}

bool volumeOverlap(const Bounds &a, const Bounds &b)
{
    for (int axis = 0; axis < 3; ++axis)
        if (std::min(a.max[axis], b.max[axis]) <= std::max(a.min[axis], b.min[axis]) + epsilon)
            return false;
    return true;
}

Vector pointOutsideBox(Vector point, const Bounds &box)
{
    for (int axis = 0; axis < 3; ++axis)
        point[axis] -= std::clamp(point[axis], box.min[axis], box.max[axis]);
    return point;
}

double segmentGap(Vector start, Vector end, const Bounds &box)
{
    // The derivative of squared distance to a convex box is monotone on a line segment.
    const auto delta = subtract(end, start);
    double lower = 0;
    double upper = 1;
    for (int iteration = 0; iteration < 42; ++iteration) {
        const double middle = (lower + upper) / 2;
        if (dot(pointOutsideBox(add(start, scale(delta, middle)), box), delta) < 0)
            lower = middle;
        else
            upper = middle;
    }
    return norm(pointOutsideBox(add(start, scale(delta, (lower + upper) / 2)), box));
}

struct Obstacle {
    QString name;
    Bounds box;
};

struct Scene {
    RouteFrame frame;
    Vector endReference;
    Vector deviceReference;
    Matrix deviceMatrix;
    Quaternion rotation;
    Bounds deviceBounds;
    Bounds translation;
    Bounds corridor;
    Bounds localCorridor;
    std::vector<Obstacle> obstacles;
    QString device;
    bool followsDevice;
    double supportLimit;
    double cableRadius;
    double bendRadius;
    int minPoints;
    int maxPoints;
};

Scene readScene(const QJsonObject &domain, const QJsonObject &baseline, const QJsonObject &problem)
{
    require(domain.value("domain").toString() == "SYNTHETIC_BENCH" &&
            baseline.value("status").toString() == "MEASURED" &&
            baseline.value("model_id") == domain.value("model_id"), "Domaine et mesure de banc incompatibles");
    const auto scene = domain.value("scene").toObject();
    const auto placement = domain.value("placement").toObject();
    const auto route = domain.value("route").toObject();
    const auto observations = baseline.value("occurrences").toObject();
    const auto ports = baseline.value("ports").toObject();
    const auto portIds = scene.value("ports").toArray();
    require(portIds.size() == 2 && placement.value("frame").toString() == "ROOT", "Repères de domaine incomplets");
    const auto startPort = ports.value(portIds.at(0).toString()).toObject();
    const auto endPort = ports.value(portIds.at(1).toString()).toObject();
    const auto start = numbers<3>(route.value("start_mm"));
    const auto end = numbers<3>(route.value("end_reference_mm"));
    require(norm(subtract(origin(numbers<16>(startPort.value("matrix"))), start)) <= epsilon &&
            norm(subtract(origin(numbers<16>(endPort.value("matrix"))), end)) <= epsilon,
            "Repères d’interface mesurés divergents du domaine");
    const auto frame = routeFrame(start, numbers<3>(startPort.value("outward")), numbers<3>(endPort.value("outward")));
    const auto device = scene.value("device_occurrence").toString();
    const auto cable = scene.value("cable_occurrence").toString();
    const auto deviceRow = observations.value(device).toObject();
    Bounds translation{numbers<3>(placement.value("translation_min_mm")),
                       numbers<3>(placement.value("translation_max_mm"))};
    const auto narrowing = problem.value("narrowing").toObject().value("translation_mm").toObject();
    if (!narrowing.isEmpty()) {
        const Bounds requested{numbers<3>(narrowing.value("min")), numbers<3>(narrowing.value("max"))};
        require(contains(translation, requested.min) && contains(translation, requested.max),
                "Restriction de pose hors domaine");
        translation = requested;
    }
    for (int axis = 0; axis < 3; ++axis)
        require(translation.min[axis] <= translation.max[axis], "Restriction de pose vide");
    const Bounds corridor{numbers<3>(route.value("corridor_min_mm")), numbers<3>(route.value("corridor_max_mm"))};
    const auto localCorridor = transformBounds(corridor, [&frame](Vector point) { return frame.local(point); });
    double supportLimit = frame.local(end)[0];
    QSet<QString> alternateSupports;
    for (const auto &supportValue : domain.value("supports").toArray()) {
        const auto support = supportValue.toObject();
        const auto anchor = observations.value(support.value("anchor_path").toString()).toObject();
        const auto carrier = observations.value(support.value("carrier_path").toString()).toObject();
        require(carrier.value("volume_mm3").toDouble() > 0, "Porteur d’ancrage non mesuré");
        supportLimit = std::min(supportLimit, frame.local(origin(numbers<16>(anchor.value("matrix"))))[0]);
        alternateSupports.insert(support.value("support_path").toString());
    }
    std::vector<Obstacle> obstacles;
    for (auto item = observations.begin(); item != observations.end(); ++item) {
        const auto row = item.value().toObject();
        if (row.value("visible").toBool() && row.value("volume_mm3").toDouble() > 0 &&
            item.key() != device && item.key() != cable && !alternateSupports.contains(item.key()))
            obstacles.push_back({item.key(), readBounds(row.value("bounds_mm"))});
    }
    const auto mode = route.value("terminal_mode").toString();
    const auto routes = baseline.value("routes").toObject();
    require(routes.size() == 1 && (mode == "FIXED" || mode == "FOLLOW_TRANSLATION"),
            "Câble ou mode de déplacement terminal non caractérisé");
    const double cableRadius = routes.begin().value().toObject().value("diameter_mm").toDouble() / 2;
    const double bendRadius = route.value("radius_min_mm").toDouble();
    require(bendRadius > cableRadius && cableRadius > 0 && bendRadius <= route.value("radius_max_mm").toDouble(),
            "Rayon ou diamètre non caractérisé");
    const auto matrix = numbers<16>(deviceRow.value("matrix"));
    const auto reference = numbers<3>(route.value("device_reference_mm"));
    require(norm(subtract(origin(matrix), reference)) <= epsilon, "Pose nominale du corps divergente du domaine");
    return {frame, end, reference, matrix, numbers<4>(placement.value("rotation_xyzw")),
            readBounds(deviceRow.value("bounds_mm")), translation, corridor, localCorridor,
            obstacles, device, mode == "FOLLOW_TRANSLATION", supportLimit, cableRadius, bendRadius,
            route.value("min_points").toInt(), route.value("max_points").toInt()};
}

struct PoseSample {
    Vector point;
    double displacement;
    std::uint32_t tie;
};

std::vector<PoseSample> samplePoses(const Bounds &region, int seed)
{
    constexpr std::array<double, 5> fractions{0, 0.25, 0.5, 0.75, 1};
    std::array<std::vector<double>, 3> positions;
    for (int axis = 0; axis < 3; ++axis) {
        const double range = region.max[axis] - region.min[axis];
        if (range > epsilon)
            positions[axis].assign(fractions.begin(), fractions.end());
        else
            positions[axis].push_back(0.5);
    }
    const auto range = subtract(region.max, region.min);
    std::mt19937 random(seed);
    std::vector<PoseSample> result;
    for (const double x : positions[0])
        for (const double y : positions[1])
            for (const double z : positions[2])
                result.push_back({add(region.min, {x * range[0], y * range[1], z * range[2]}),
                                  norm(subtract({x, y, z}, {0.5, 0.5, 0.5})),
                                  static_cast<std::uint32_t>(random())});
    std::sort(result.begin(), result.end(), [](const PoseSample &a, const PoseSample &b) {
        return a.displacement < b.displacement || (a.displacement == b.displacement && a.tie < b.tie);
    });
    return result;
}

struct RouteSample {
    std::vector<Vector> points;
    double rounding = 0;
    double length = 0;
};

std::optional<RouteSample> sampledRoute(const Scene &scene, Vector end, double transition,
                                        std::optional<double> shelf, double plateauNear, double plateauFar)
{
    const double lead = 2 * scene.bendRadius;
    std::vector<Vector> points{{0, 0, 0}, {transition, 0, 0}};
    if (shelf) {
        const double exit = plateauFar + std::max(1.5 * scene.bendRadius, 0.8 * std::abs(end[1] - *shelf));
        points.insert(points.end(), {{plateauNear, *shelf, 0}, {plateauFar, *shelf, 0}, {exit, end[1], 0}});
    } else {
        const double exit = transition + std::max(1.5 * scene.bendRadius, 0.8 * std::abs(end[1]));
        points.push_back({exit, end[1], 0});
    }
    points.push_back(end);
    if (points.size() < static_cast<std::size_t>(scene.minPoints) ||
        points.size() > static_cast<std::size_t>(scene.maxPoints) ||
        points[points.size() - 2][0] > scene.supportLimit - lead / 2)
        return {};
    for (std::size_t index = 1; index < points.size(); ++index)
        if (points[index][0] <= points[index - 1][0] + epsilon)
            return {};
    std::vector<double> tangent(points.size(), 0.0);
    RouteSample result;
    for (std::size_t index = 1; index + 1 < points.size(); ++index) {
        const auto incoming = unit(subtract(points[index], points[index - 1]));
        const auto outgoing = unit(subtract(points[index + 1], points[index]));
        const double half = std::acos(std::clamp(dot(incoming, outgoing), -1.0, 1.0)) / 2;
        tangent[index] = scene.bendRadius * std::tan(half);
        // Upper bound of the deviation of the rounded centreline from the broken line.
        result.rounding = std::max(result.rounding, scene.bendRadius * (1 - std::cos(half)));
    }
    for (std::size_t index = 1; index < points.size(); ++index) {
        const double length = norm(subtract(points[index], points[index - 1]));
        if (length <= tangent[index] + tangent[index - 1] + epsilon)
            return {};
        result.length += length;
    }
    for (const auto &point : points) {
        auto global = scene.frame.world(point);
        for (int axis = 0; axis < 3; ++axis)
            if (scene.corridor.min[axis] == scene.corridor.max[axis] &&
                std::abs(global[axis] - scene.corridor.min[axis]) <= epsilon)
                global[axis] = scene.corridor.min[axis];
        if (!contains(scene.corridor, global))
            return {};
        result.points.push_back(global);
    }
    return result;
}

QStringList routeIssues(const Scene &scene, const RouteSample &route, Vector end, double &clearance)
{
    QStringList issues;
    for (const auto &obstacle : scene.obstacles) {
        const auto projected = transformBounds(obstacle.box, [&scene](Vector point) { return scene.frame.local(point); });
        // The connector end faces delimit a flat tube cap. Its intended face contact is verified natively.
        if (projected.max[0] <= epsilon || projected.min[0] >= end[0] - epsilon)
            continue;
        double gap = std::numeric_limits<double>::infinity();
        for (std::size_t index = 1; index < route.points.size(); ++index)
            gap = std::min(gap, segmentGap(route.points[index - 1], route.points[index], obstacle.box));
        gap -= scene.cableRadius + route.rounding;
        clearance = std::min(clearance, gap);
        if (gap < -epsilon)
            issues.push_back(QString("route/%1").arg(obstacle.name));
    }
    return issues;
}

std::vector<RouteSample> searchRoutes(const Scene &scene, Vector end, const QString &family)
{
    std::vector<RouteSample> routes;
    const double baseLead = 2 * scene.bendRadius + scene.cableRadius;
    for (const double progress : {0.0, 0.10, 0.22}) {
        const double transition = baseLead + progress * (scene.supportLimit - baseLead);
        if (family == "DIRECT") {
            if (std::abs(end[1]) > epsilon)
                if (const auto route = sampledRoute(scene, end, transition, {}, 0, 0))
                    routes.push_back(*route);
            continue;
        }
        const double sign = family == "DETOUR_POSITIVE" ? 1 : -1;
        const double limit = sign > 0 ? scene.localCorridor.max[1] : -scene.localCorridor.min[1];
        // Project obstacles that cut the direct line to place the detour before and beyond their footprints.
        double obstacleExtent = 0;
        double shelfMinimum = std::max(scene.cableRadius, sign * end[1]);
        for (const auto &obstacle : scene.obstacles) {
            const auto bounds = transformBounds(obstacle.box, [&scene](Vector point) { return scene.frame.local(point); });
            if (bounds.min[0] <= baseLead || bounds.max[0] >= scene.supportLimit || bounds.min[2] > scene.cableRadius ||
                bounds.max[2] < -scene.cableRadius)
                continue;
            const double routeY = end[1] * (bounds.min[0] + bounds.max[0]) / (2 * end[0]);
            if (routeY + scene.cableRadius >= bounds.min[1] && routeY - scene.cableRadius <= bounds.max[1]) {
                obstacleExtent = std::max(obstacleExtent, bounds.max[0] + scene.cableRadius);
                shelfMinimum = std::max(shelfMinimum, (sign > 0 ? bounds.max[1] : -bounds.min[1]) +
                                                     scene.cableRadius + scene.bendRadius / 2);
            }
        }
        for (const double width : {0.30, 0.48, 0.64}) {
            if (shelfMinimum >= limit)
                continue;
            const double shelf = sign * (shelfMinimum + width * (limit - shelfMinimum));
            const double plateauNear = transition + std::max(1.5 * scene.bendRadius, 0.8 * std::abs(shelf));
            const double plateauFar = std::max(plateauNear + 1.5 * scene.bendRadius, obstacleExtent);
            if (const auto route = sampledRoute(scene, end, transition, shelf, plateauNear, plateauFar))
                routes.push_back(*route);
        }
    }
    return routes;
}

QJsonObject makeProposal(const Scene &scene, Vector pose, const QString &family)
{
    const auto end = scene.frame.local(scene.followsDevice ?
                add(scene.endReference, subtract(pose, scene.deviceReference)) : scene.endReference);
    require(std::abs(end[2]) <= epsilon && end[0] > epsilon,
            "Sortie déplacée hors plan du corridor ou derrière le départ");
    const auto moved = transformBounds(
        scene.deviceBounds, [&scene, pose](Vector point) {
            return movedPoint(point, scene.deviceMatrix, pose, scene.rotation);
        });
    QStringList placementIssues;
    double placementClearance = std::numeric_limits<double>::infinity();
    for (const auto &obstacle : scene.obstacles) {
        placementClearance = std::min(placementClearance, boxGap(moved, obstacle.box));
        if (volumeOverlap(moved, obstacle.box))
            placementIssues.push_back(QString("pose/%1/%2").arg(scene.device, obstacle.name));
    }
    const auto routes = searchRoutes(scene, {end[0], end[1], 0}, family);
    std::optional<RouteSample> best;
    QStringList bestIssues;
    double bestClearance = 0;
    for (const auto &route : routes) {
        double clearance = placementClearance;
        const auto issues = placementIssues + routeIssues(scene, route, end, clearance);
        if (!best || issues.size() < bestIssues.size() ||
            (issues.size() == bestIssues.size() && route.length < best->length)) {
            best = route;
            bestIssues = issues;
            bestClearance = clearance;
        }
    }
    if (!best)
        return {{"family", family}, {"sample_translation_mm", json(pose)}, {"screen", QJsonObject{
                    {"status", "BLOCKED"}, {"blocking_issues", QJsonArray{"NO_FILLETED_ROUTE_IN_CORRIDOR"}},
                    {"route_trials", 0}}}};
    QJsonArray points;
    for (const auto &point : best->points)
        points.append(json(point));
    QJsonObject values{{"translation_mm", json(pose)}, {"route_points_mm", points}, {"bend_radius_mm", scene.bendRadius}};
    return {{"family", family}, {"values", values}, {"screen", QJsonObject{
                {"status", bestIssues.isEmpty() ? "ELIGIBLE" : "BLOCKED"},
                {"blocking_issues", QJsonArray::fromStringList(bestIssues)},
                {"minimum_clearance_mm", std::isfinite(bestClearance) ? QJsonValue(bestClearance) : QJsonValue(QJsonValue::Null)},
                {"estimated_route_length_mm", best->length}, {"route_trials", static_cast<int>(routes.size())}}}};
}

QString signature(const QJsonObject &values)
{
    auto quantize = [](const QJsonValue &value) {
        auto point = numbers<3>(value);
        for (double &coordinate : point)
            coordinate = std::round(coordinate / epsilon);
        return json(point);
    };
    QJsonArray points;
    for (const auto value : values.value("route_points_mm").toArray())
        points.append(quantize(value));
    const QJsonObject geometry{{"translation", quantize(values.value("translation_mm"))}, {"path", points},
                               {"radius", std::round(values.value("bend_radius_mm").toDouble() / epsilon)}};
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(geometry).toJson(QJsonDocument::Compact),
                                                       QCryptographicHash::Sha256).toHex());
}

} // namespace

QJsonObject generateV3Proposals(const QJsonObject &domain, const QJsonObject &baseline,
                               const QJsonObject &problem, int seed, const QString &family)
{
    try {
        const QStringList families{"DIRECT", "DETOUR_POSITIVE", "DETOUR_NEGATIVE"};
        require(family.isEmpty() || families.contains(family), "Famille de recherche inconnue");
        const auto scene = readScene(domain, baseline, problem);
        const auto poses = samplePoses(scene.translation, seed);
        int eligible = 0;
        int totalTested = 0;
        QSet<QString> signatures;
        QJsonArray proposals;
        const int budget = problem.value("budget").toObject().value("max_proposals").toInt(64);
        require(budget > 0 && budget <= 1024, "Budget de propositions invalide");
        const auto activeFamilies = family.isEmpty() ? families : QStringList{family};
        for (const auto &pose : poses) {
            for (const auto &name : activeFamilies) {
                if (proposals.size() >= budget)
                    break;
                auto proposal = makeProposal(scene, pose.point, name);
                ++totalTested;
                if (proposal.contains("values")) {
                    const auto id = signature(proposal.value("values").toObject());
                    if (signatures.contains(id))
                        continue;
                    signatures.insert(id);
                    proposal.insert("signature", id);
                }
                if (proposal.value("screen").toObject().value("status") == "ELIGIBLE")
                    ++eligible;
                proposals.append(proposal);
            }
            if (proposals.size() >= budget)
                break;
        }
        return {{"status", eligible ? "GENERATED" : "NO_FEASIBLE_CANDIDATE_FOUND"}, {"proposals", proposals},
                {"coverage", QJsonObject{{"region_min_mm", json(scene.translation.min)},
                                         {"region_max_mm", json(scene.translation.max)},
                                         {"grid_levels_per_variable_axis", 5},
                                         {"possible_pose_count", static_cast<int>(poses.size())},
                                         {"evaluated_pose_family_count", totalTested}, {"eligible", eligible},
                                         {"route_screen", "TUBE_ENVELOPE_VS_OBSERVED_AABB"},
                                         {"budget_limited", totalTested < static_cast<int>(poses.size() * activeFamilies.size())},
                                         {"determination", "SCREEN_ONLY"}}},
                {"unknowns", QJsonArray{"SERVICE_SWEEPS", "CONTACT_ENGAGEMENT", "BRep_INTERFERENCE"}}};
    } catch (const std::runtime_error &error) {
        return {{"status", "CONSTRAINT_UNKNOWN"}, {"proposals", QJsonArray{}},
                {"unknowns", QJsonArray{QString::fromUtf8(error.what())}}};
    }
}

} // namespace convergence
