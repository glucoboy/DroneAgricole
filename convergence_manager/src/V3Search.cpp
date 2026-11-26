#include "V3Search.hpp"
#include "V3Domain.hpp"
#include "V3SpatialGeometry.hpp"

#include <QByteArray>
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
#include <tuple>
#include <utility>
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

using Bounds = V3Box;

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
    bool followsDevice;
};

struct SupportAnchor {
    Vector reference;
    bool followsDevice;
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
    std::vector<SupportAnchor> anchors;
    QString device;
    bool followsDevice;
    bool coupled;
    double supportLimit;
    double cableRadius;
    double bendRadius;
    int minPoints;
    int maxPoints;
    std::vector<Bounds> polycorridors;
    double minLength;
    double maxLength;
    QSet<QString> terminalContacts;
};

Scene readScene(const QJsonObject &domain, const QJsonObject &baseline, const QJsonObject &problem)
{
    require(domain.value("domain").toString() == "SYNTHETIC_BENCH" &&
            baseline.value("status").toString() == "MEASURED" &&
            baseline.value("model_id") == domain.value("model_id"), "Domaine et mesure de banc incompatibles");
    const auto scene = domain.value("scene").toObject();
    const auto placement = domain.value("placement").toObject();
    const auto route = domain.value("route").toObject();
    const auto mode = route.value("terminal_mode").toString();
    const bool coupled = mode == v3NativePortMode;
    const auto observations = baseline.value("occurrences").toObject();
    const auto ports = baseline.value("ports").toObject();
    const auto portIds = scene.value("ports").toArray();
    require(portIds.size() == 2 && placement.value("frame").toString() == "ROOT", "Repères de domaine incomplets");
    const auto startPort = ports.value(portIds.at(0).toString()).toObject();
    const auto endPort = ports.value(portIds.at(1).toString()).toObject();
    const auto measuredStart = origin(numbers<16>(startPort.value("matrix")));
    const auto measuredEnd = origin(numbers<16>(endPort.value("matrix")));
    const auto authorizedStart = numbers<3>(route.value("start_mm"));
    const auto authorizedEnd = numbers<3>(route.value("end_reference_mm"));
    require(norm(subtract(measuredStart, authorizedStart)) <= epsilon &&
            norm(subtract(measuredEnd, authorizedEnd)) <= epsilon,
            "Repères d’interface mesurés divergents du domaine");
    const auto start = coupled ? measuredStart : authorizedStart;
    const auto end = coupled ? measuredEnd : authorizedEnd;
    const auto frame = routeFrame(start, numbers<3>(startPort.value("outward")), numbers<3>(endPort.value("outward")));
    const auto device = scene.value("device_occurrence").toString();
    const auto cable = scene.value("cable_occurrence").toString();
    const auto deviceRow = observations.value(device).toObject();
    const auto matrix = numbers<16>(deviceRow.value("matrix"));
    const auto rotation = numbers<4>(placement.value("rotation_xyzw"));
    if (coupled) {
        const auto portEquipment = numbers<16>(endPort.value("equipment_matrix"));
        bool matrixMatchesDevice = true;
        for (std::size_t index = 0; index < matrix.size(); ++index)
            matrixMatchesDevice &= std::abs(portEquipment[index] - matrix[index]) <= epsilon;
        require(matrixMatchesDevice && startPort.value("datum").isString() &&
                endPort.value("datum").toString().startsWith(device + '/'),
                "La mesure de référence ne rattache pas le datum au corps mobile");
        for (std::size_t axis = 0; axis < 3; ++axis) {
            Vector probe = origin(matrix);
            probe[axis] += 1;
            if (norm(subtract(probe, movedPoint(probe, matrix, origin(matrix), rotation))) > epsilon)
                throw V3UnsupportedPose();
        }
        if (placement.contains("rotation_bounds"))
            throw V3UnsupportedPose();
    }
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
    QSet<QString> companions;
    for (const auto &value : scene.value("moving_with").toArray())
        companions.insert(value.toString());
    std::vector<SupportAnchor> anchors;
    for (const auto &supportValue : domain.value("supports").toArray()) {
        const auto support = supportValue.toObject();
        const auto anchorPath = support.value("anchor_path").toString();
        const auto anchor = observations.value(anchorPath).toObject();
        const auto carrier = observations.value(support.value("carrier_path").toString()).toObject();
        require(carrier.value("volume_mm3").toDouble() > 0, "Porteur d’ancrage non mesuré");
        const auto anchorPosition = origin(numbers<16>(anchor.value("matrix")));
        supportLimit = std::min(supportLimit, frame.local(anchorPosition)[0]);
        anchors.push_back({anchorPosition, companions.contains(anchorPath)});
        alternateSupports.insert(support.value("support_path").toString());
    }
    std::vector<Obstacle> obstacles;
    QSet<QString> physical;
    if (coupled) {
        for (const auto &pair : baseline.value("pairs").toArray())
            for (const auto &subject : pair.toObject().value("pair").toArray())
                physical.insert(subject.toString());
    }
    for (auto item = observations.begin(); item != observations.end(); ++item) {
        const auto row = item.value().toObject();
        const bool deviceMember = item.key() == device || (coupled && item.key().startsWith(device + '/'));
        if (row.value("visible").toBool() && row.value("volume_mm3").toDouble() > 0 &&
            (!coupled || physical.contains(item.key())) && !deviceMember && item.key() != cable &&
            !alternateSupports.contains(item.key()))
            obstacles.push_back({item.key(), readBounds(row.value("bounds_mm")), companions.contains(item.key())});
    }
    const auto routes = baseline.value("routes").toObject();
    require(routes.size() == 1 && (mode == "FIXED" || mode == "FOLLOW_TRANSLATION" || coupled),
            "Câble ou mode de déplacement terminal non caractérisé");
    const double cableRadius = routes.begin().value().toObject().value("diameter_mm").toDouble() / 2;
    const double bendRadius = route.value("radius_min_mm").toDouble();
    require(bendRadius > cableRadius && cableRadius > 0 && bendRadius <= route.value("radius_max_mm").toDouble(),
            "Rayon ou diamètre non caractérisé");
    const auto reference = numbers<3>(route.value("device_reference_mm"));
    require(norm(subtract(origin(matrix), reference)) <= epsilon, "Pose nominale du corps divergente du domaine");
    std::vector<Bounds> volumes;
    for (const auto &value : route.value("polycorridors").toArray()) {
        const auto box = value.toObject();
        volumes.push_back({numbers<3>(box.value("min_mm")), numbers<3>(box.value("max_mm"))});
    }
    QSet<QString> terminalContacts;
    if (!volumes.empty()) {
        const auto classification = baseline.value("interference_classification").toObject();
        for (const auto &entry : classification.value("surface_contacts").toArray()) {
            const auto contact = entry.toObject();
            const auto pair = contact.value("pair").toArray();
            if (contact.value("role") == "NATIVE_WIRE_EXIT" && pair.size() == 2 && pair.contains(cable))
                terminalContacts.insert((pair.first() == cable ? pair.last() : pair.first()).toString());
        }
    }
    return {frame, end, reference, matrix, rotation,
            readBounds(deviceRow.value("bounds_mm")), translation, corridor, localCorridor,
            obstacles, anchors, device, mode == "FOLLOW_TRANSLATION", coupled, supportLimit, cableRadius, bendRadius,
            route.value("min_points").toInt(), route.value("max_points").toInt(), volumes,
            route.value("minimum_length_mm").toDouble(), route.value("maximum_length_mm").toDouble(), terminalContacts};
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
    const auto advances = scene.coupled ? std::vector<double>{0.0, 0.05, 0.10, 0.16, 0.22, 0.32}
                                       : std::vector<double>{0.0, 0.10, 0.22};
    for (const double progress : advances) {
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

QJsonObject blockedPose(Vector pose, const QString &family, const QString &reason)
{
    return {{"family", family}, {"sample_translation_mm", json(pose)}, {"screen", QJsonObject{
                {"status", "SCREEN_REJECT"}, {"blocking_issues", QJsonArray{reason}}, {"route_trials", 0}}}};
}

QJsonObject makeProposal(Scene scene, Vector pose, const QString &family, int routeAlternative)
{
    const auto movedWithDevice = [&scene, pose](Vector point) {
        return movedPoint(point, scene.deviceMatrix, pose, scene.rotation);
    };
    const auto end = scene.frame.local(scene.coupled ? movedWithDevice(scene.endReference) : scene.followsDevice ?
              add(scene.endReference, subtract(pose, scene.deviceReference)) : scene.endReference);
    if (scene.coupled) {
        if (norm(subtract(pose, scene.deviceReference)) <= epsilon)
            return blockedPose(pose, family, "UNCHANGED_DEVICE_POSE");
        if (std::abs(end[2]) > epsilon || end[0] <= epsilon)
            return blockedPose(pose, family, "PORT_OUTSIDE_ROUTE_PLANE");
        for (auto &obstacle : scene.obstacles)
            if (obstacle.followsDevice)
                obstacle.box = transformBounds(obstacle.box, movedWithDevice);
        scene.supportLimit = end[0];
        for (const auto &anchor : scene.anchors) {
            const auto current = anchor.followsDevice ? movedWithDevice(anchor.reference) : anchor.reference;
            scene.supportLimit = std::min(scene.supportLimit, scene.frame.local(current)[0]);
        }
    }
    require(std::abs(end[2]) <= epsilon && end[0] > epsilon,
            "Sortie déplacée hors plan du corridor ou derrière le départ");
    const auto moved = transformBounds(scene.deviceBounds, movedWithDevice);
    QStringList placementIssues;
    double placementClearance = std::numeric_limits<double>::infinity();
    for (const auto &obstacle : scene.obstacles) {
        if (scene.coupled && obstacle.followsDevice)
            continue;
        placementClearance = std::min(placementClearance, boxGap(moved, obstacle.box));
        if (volumeOverlap(moved, obstacle.box))
            placementIssues.push_back(QString("pose/%1/%2").arg(scene.device, obstacle.name));
    }
    const auto routes = searchRoutes(scene, {end[0], end[1], 0}, family);
    struct ScreenedRoute {
        RouteSample route;
        QStringList issues;
        double clearance;
    };
    std::vector<ScreenedRoute> screened;
    for (const auto &route : routes) {
        double clearance = placementClearance;
        screened.push_back({route, placementIssues + routeIssues(scene, route, end, clearance), clearance});
    }
    std::stable_sort(screened.begin(), screened.end(), [routeAlternative](const auto &first, const auto &second) {
        if (first.issues.size() != second.issues.size())
            return first.issues.size() < second.issues.size();
        if (routeAlternative > 0 && first.clearance != second.clearance)
            return first.clearance > second.clearance;
        return first.route.length < second.route.length;
    });
    if (screened.empty())
        return blockedPose(pose, family, "NO_FILLETED_ROUTE_IN_CORRIDOR");
    const auto selected = std::min(static_cast<std::size_t>(routeAlternative), screened.size() - 1);
    const auto &best = screened[selected];
    QJsonArray points;
    for (const auto &point : best.route.points)
        points.append(json(point));
    QJsonObject values{{"translation_mm", json(pose)}, {"route_points_mm", points}, {"bend_radius_mm", scene.bendRadius}};
    return {{"family", family}, {"values", values}, {"screen", QJsonObject{
                {"status", best.issues.isEmpty() ? "SCREEN_PASS" : scene.coupled ? "NEEDS_NATIVE_CHECK" : "SCREEN_REJECT"},
                {"blocking_issues", QJsonArray::fromStringList(best.issues)},
                {"minimum_clearance_mm", std::isfinite(best.clearance) ? QJsonValue(best.clearance) : QJsonValue(QJsonValue::Null)},
                {"estimated_route_length_mm", best.route.length}, {"route_trials", static_cast<int>(routes.size())}}}};
}

QString signature(const QJsonObject &values)
{
    auto quantize = [](const QJsonValue &value) {
        auto point = numbers<3>(value);
        for (double &coordinate : point)
            coordinate = std::round(coordinate / epsilon);
        return json(point);
    };
    const auto pathGeometry = [&quantize](const QJsonObject &route) {
        QJsonArray points;
        for (const auto &point : route.value("route_points_mm").toArray())
            points.append(quantize(point));
        return QJsonObject{{"path", points},
            {"radius", std::round(route.value("bend_radius_mm").toDouble() / epsilon)}};
    };
    QJsonObject geometry{{"translation", quantize(values.value("translation_mm"))}};
    if (values.contains("harnesses")) {
        const auto harnesses = values.value("harnesses").toObject();
        QJsonObject paths;
        for (auto it = harnesses.begin(); it != harnesses.end(); ++it)
            paths.insert(it.key(), pathGeometry(it.value().toObject()));
        geometry.insert("harnesses", paths);
        geometry.insert("support_option", values.value("support_option"));
    } else {
        const auto path = pathGeometry(values);
        geometry.insert("path", path.value("path"));
        geometry.insert("radius", path.value("radius"));
    }
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(geometry).toJson(QJsonDocument::Compact),
                                                       QCryptographicHash::Sha256).toHex());
}

double pointSegmentDistance(Vector point, Vector first, Vector last)
{
    const auto step = subtract(last, first);
    const auto projection = dot(subtract(point, first), step) / dot(step, step);
    return norm(subtract(point, add(first, scale(step, std::clamp(projection, 0.0, 1.0)))));
}

double segmentDistance(Vector a, Vector b, Vector c, Vector d)
{
    const auto u = subtract(b, a), v = subtract(d, c), offset = subtract(a, c);
    const auto uu = dot(u, u), vv = dot(v, v), uv = dot(u, v);
    const auto determinant = uu * vv - uv * uv;
    if (determinant > epsilon * uu * vv) {
        const auto du = dot(u, offset), dv = dot(v, offset);
        const auto s = (uv * dv - vv * du) / determinant;
        const auto t = (uu * dv - uv * du) / determinant;
        if (s >= 0 && s <= 1 && t >= 0 && t <= 1)
            return norm(subtract(add(a, scale(u, s)), add(c, scale(v, t))));
    }
    return std::min({pointSegmentDistance(a, c, d), pointSegmentDistance(b, c, d),
                     pointSegmentDistance(c, a, b), pointSegmentDistance(d, a, b)});
}

double routeGap(const QJsonArray &left, const QJsonArray &right, double radii)
{
    double distance = std::numeric_limits<double>::infinity();
    for (qsizetype i = 1; i < left.size(); ++i)
        for (qsizetype j = 1; j < right.size(); ++j)
            distance = std::min(distance, segmentDistance(numbers<3>(left.at(i - 1)), numbers<3>(left.at(i)),
                                                          numbers<3>(right.at(j - 1)), numbers<3>(right.at(j))));
    return distance - radii;
}

struct HarnessScene {
    QString id;
    Scene scene;
};

// The window and transverse offsets are derived from the sealed corridors and measured scene.
// The search remains restricted to forward, two-transition paths with tangent leads.
struct SpatialRoute {
    RouteSample route;
    QJsonArray points;
    QStringList issues;
    double gap;
    double externalGap;
    double excursion;
    qsizetype nonTerminalHints;
};

std::optional<RouteSample> filletSpatial(const Scene &scene, const std::vector<Vector> &knots)
{
    if (knots.size() < static_cast<std::size_t>(scene.minPoints) ||
        knots.size() > static_cast<std::size_t>(scene.maxPoints))
        return {};
    RouteSample result;
    for (const auto &knot : knots)
        result.points.push_back(scene.frame.world(knot));
    for (std::size_t index = 1; index < knots.size(); ++index) {
        if (knots[index][0] <= knots[index - 1][0] + epsilon ||
            !v3SegmentInBoxes(result.points[index - 1], result.points[index], scene.polycorridors))
            return {};
    }
    std::vector<double> trims(knots.size());
    for (std::size_t index = 1; index + 1 < knots.size(); ++index) {
        const auto corner = result.points[index];
        const auto in = unit(subtract(corner, result.points[index - 1]));
        const auto out = unit(subtract(result.points[index + 1], corner));
        const auto cosine = std::clamp(dot(in, out), -1.0, 1.0);
        const auto sweep = std::acos(cosine);
        const auto half = sweep / 2;
        const auto turnNormal = subtract(out, scale(in, cosine));
        if (norm(turnNormal) <= epsilon) {
            if (cosine < 0)
                return {};
            continue;
        }
        trims[index] = scene.bendRadius * std::tan(half);
        const auto radial = scale(unit(turnNormal), -scene.bendRadius);
        const auto start = subtract(corner, scale(in, trims[index]));
        if (!v3ArcInBoxes(subtract(start, radial), radial, scale(in, scene.bendRadius),
                         sweep, scene.polycorridors))
            return {};
        result.rounding = std::max(result.rounding, scene.bendRadius * (1 - std::cos(half)));
        result.length += 2 * (scene.bendRadius * half - trims[index]);
    }
    for (std::size_t index = 1; index < knots.size(); ++index) {
        const auto length = norm(subtract(knots[index], knots[index - 1]));
        if (length <= trims[index - 1] + trims[index] + epsilon)
            return {};
        result.length += length;
    }
    if (result.length + epsilon < scene.minLength || result.length - epsilon > scene.maxLength)
        return {};
    return result;
}

std::vector<SpatialRoute> spatialRoutes(Scene scene, Vector pose, const QString &strategy)
{
    const auto move = [&scene, pose](Vector point) {
        return movedPoint(point, scene.deviceMatrix, pose, scene.rotation);
    };
    const auto end = scene.frame.local(move(scene.endReference));
    for (auto &obstacle : scene.obstacles)
        if (obstacle.followsDevice)
            obstacle.box = transformBounds(obstacle.box, move);
    // The polycorridor bounds the return to the landing plane. The OCCT
    // checks decide actual retention on the selected support surface.
    const double landing = end[0] - 2 * scene.bendRadius;
    const auto lead = scene.bendRadius + scene.cableRadius;
    if (landing <= 3 * lead)
        return {};

    std::vector<std::pair<double, double>> windows;
    for (const auto fraction : {0.30, 0.45, 0.58})
        windows.emplace_back(fraction * landing, std::min(fraction * landing + 2 * lead, 0.78 * landing));
    double firstBlock = landing, lastBlock = 0;
    for (const auto &obstacle : scene.obstacles) {
        const auto local = transformBounds(obstacle.box, [&scene](Vector point) { return scene.frame.local(point); });
        if (local.min[0] < 1.5 * lead || local.max[0] >= landing - lead)
            continue;
        const auto nominal = scale(end, ((local.min[0] + local.max[0]) / 2) / end[0]);
        if (nominal[1] + lead < local.min[1] || nominal[1] - lead > local.max[1])
            continue;
        firstBlock = std::min(firstBlock, local.min[0]);
        lastBlock = std::max(lastBlock, local.max[0]);
        windows.emplace_back(local.min[0] - scene.cableRadius, local.max[0] + scene.cableRadius);
    }
    if (firstBlock < lastBlock)
        windows.emplace_back(firstBlock - scene.cableRadius, lastBlock + scene.cableRadius);

    std::vector<SpatialRoute> samples;
    QSet<QString> unique;
    const auto consider = [&](std::vector<Vector> knots, double excursion) {
        auto route = filletSpatial(scene, knots);
        if (!route && knots.size() > 4) {
            // Preserve the signed exit tangent while advancing the final bend.
            // Each step is proportional to the radius and checked against the
            // actual corridor planes, including any planar landing strip.
            auto &lastTurn = knots[knots.size() - 2];
            const double step = scene.bendRadius / 16;
            for (int advance = 0; advance < 16 && !route; ++advance) {
                lastTurn[0] -= step;
                if (lastTurn[0] <= knots[knots.size() - 3][0] + epsilon)
                    break;
                route = filletSpatial(scene, knots);
            }
        }
        if (!route)
            return;
        QJsonArray points;
        for (const auto &point : route->points)
            points.append(json(point));
        const auto encoded = QString::fromLatin1(QJsonDocument(points).toJson(QJsonDocument::Compact));
        if (unique.contains(encoded))
            return;
        unique.insert(encoded);
        double gap = std::numeric_limits<double>::infinity();
        auto issues = routeIssues(scene, *route, end, gap);
        auto externalGap = std::numeric_limits<double>::infinity();
        for (const auto &obstacle : scene.obstacles) {
            if (obstacle.name != "external-obstacle")
                continue;
            for (std::size_t index = 1; index < route->points.size(); ++index)
                externalGap = std::min(externalGap, segmentGap(route->points[index - 1], route->points[index], obstacle.box));
            externalGap -= scene.cableRadius + route->rounding;
            if (externalGap < 0 && !issues.contains("route/external-obstacle"))
                issues.append("route/external-obstacle");
        }
        const auto hints = std::count_if(issues.begin(), issues.end(), [&](const auto &issue) {
            return !scene.terminalContacts.contains(issue.mid(6));
        });
        samples.push_back({std::move(*route), points, issues, gap, externalGap, excursion, hints});
    };

    for (const double approach : {1.0, 1.5, 2.0}) {
        const auto leave = approach * lead;
        for (const double finish : {0.98, 0.94, 0.84, 0.72, 0.62}) {
            const auto arrive = finish * landing;
            const Vector approachPoint{leave, 0, 0};
            const Vector arrivalPoint{arrive, end[1], end[2]};
            consider({{0, 0, 0}, approachPoint, arrivalPoint, end}, std::abs(end[2]));
            for (const auto &[near, far] : windows) {
                if (near <= leave || far >= arrive || near >= far)
                    continue;
                for (const double side : {-0.5, 0.0, 0.5}) {
                    const auto nominalSide = 0.5 * end[1];
                    const auto width = side < 0 ? nominalSide - scene.localCorridor.min[1] :
                                                  scene.localCorridor.max[1] - nominalSide;
                    const auto y = nominalSide + side * width;
                    for (const double lift : {-0.50, 0.0, 0.27, 0.42, 0.62, 0.82}) {
                        const auto nominalHeight = 0.5 * end[2];
                        const auto height = lift < 0 ? nominalHeight - scene.localCorridor.min[2] :
                                                       scene.localCorridor.max[2] - nominalHeight;
                        const auto z = nominalHeight + lift * height;
                        if (std::abs(y - nominalSide) < epsilon && std::abs(z - nominalHeight) < epsilon)
                            continue;
                        consider({{0, 0, 0}, approachPoint, {near, y, z}, {far, y, z}, arrivalPoint, end},
                                 std::max(std::abs(z), std::abs(end[2])));
                    }
                }
            }
        }
    }
    std::stable_sort(samples.begin(), samples.end(), [&strategy](const auto &a, const auto &b) {
        const auto key = [&strategy](const auto &route) {
            const auto preference = strategy == "SPATIAL_CLEARANCE" ? -route.gap :
                strategy == "SPATIAL_EXCURSION" ? -route.excursion : route.route.length;
            return std::tuple{route.externalGap < 0, route.nonTerminalHints, route.issues.size(), preference, route.route.length};
        };
        return key(a) < key(b);
    });
    return samples;
}

QJsonObject spatialProposals(const std::vector<HarnessScene> &scenes, const std::vector<PoseSample> &poses,
                             const QJsonObject &problem, const QStringList &supportIds,
                             const QString &strategy, double requiredGap)
{
    require(v3SpatialStrategies().contains(strategy), "Stratégie spatiale inconnue");
    const auto budget = problem.value("budget").toObject().value("max_proposals").toInt();
    QSet<QString> signatures;
    QJsonArray proposals;
    int eligible = 0, routeTrials = 0;
    std::vector<QJsonArray> rankedByPose;
    const auto poseLimit = std::min(poses.size(), static_cast<std::size_t>(budget));
    for (std::size_t poseIndex = 0; poseIndex < poseLimit; ++poseIndex) {
        const auto &pose = poses[poseIndex];
        QJsonArray ranked;
        std::vector<std::vector<SpatialRoute>> routes;
        for (const auto &harness : scenes) {
            auto choices = spatialRoutes(harness.scene, pose.point, strategy);
            routeTrials += static_cast<int>(choices.size());
            if (choices.size() > 5)
                choices.resize(5);
            routes.push_back(std::move(choices));
        }
        if (std::any_of(routes.begin(), routes.end(), [](const auto &entries) { return entries.empty(); })) {
            ranked.append(blockedPose(pose.point, strategy, "NO_GENERATED_ROUTE_IN_SEALED_POLYCORRIDOR"));
            rankedByPose.push_back(ranked);
            continue;
        }

        struct Combination {
            QJsonObject routes;
            QStringList issues;
            double length;
            double gap;
            int priority;
            qsizetype nonTerminalHints;
        };
        std::vector<Combination> choices;
        for (std::size_t first = 0; first < routes[0].size(); ++first) {
            for (std::size_t second = 0; second < routes[1].size(); ++second) {
                const auto &a = routes[0][first];
                const auto &b = routes[1][second];
                QStringList issues;
                for (const auto &issue : a.issues)
                    issues.append(scenes[0].id + '/' + issue);
                for (const auto &issue : b.issues)
                    issues.append(scenes[1].id + '/' + issue);
                const auto separation = routeGap(a.points, b.points, scenes[0].scene.cableRadius +
                    scenes[1].scene.cableRadius + a.route.rounding + b.route.rounding);
                const bool tight = separation + epsilon < requiredGap;
                if (tight)
                    issues.append("inter-harness/" + scenes[0].id + '/' + scenes[1].id);
                const QJsonObject values{
                    {scenes[0].id, QJsonObject{{"route_points_mm", a.points}, {"bend_radius_mm", scenes[0].scene.bendRadius}}},
                    {scenes[1].id, QJsonObject{{"route_points_mm", b.points}, {"bend_radius_mm", scenes[1].scene.bendRadius}}}};
                choices.push_back({values, issues, a.route.length + b.route.length, separation,
                                   static_cast<int>(first + second), a.nonTerminalHints + b.nonTerminalHints + tight});
            }
        }
        std::stable_sort(choices.begin(), choices.end(), [](const auto &left, const auto &right) {
            return std::tuple{left.nonTerminalHints, left.issues.size(), left.priority} <
                   std::tuple{right.nonTerminalHints, right.issues.size(), right.priority};
        });
        int perPose = 0;
        for (const auto &choice : choices) {
            if (perPose >= std::max<qsizetype>(3, supportIds.size()))
                break;
            const auto pos = v3SpatialStrategies().indexOf(strategy) + perPose + poseIndex;
            const auto support = supportIds.at(pos % supportIds.size());
            const QJsonObject values{{"translation_mm", json(pose.point)}, {"harnesses", choice.routes},
                                     {"support_option", support}};
            const auto identity = signature(values);
            if (signatures.contains(identity))
                continue;
            signatures.insert(identity);
            ++perPose;
            ranked.append(QJsonObject{{"family", strategy}, {"values", values}, {"signature", identity},
                {"screen", QJsonObject{{"status", choice.issues.isEmpty() ? "SCREEN_PASS" : "NEEDS_NATIVE_CHECK"},
                    {"blocking_issues", QJsonArray::fromStringList(choice.issues)},
                    {"non_terminal_hints", choice.nonTerminalHints}, {"estimated_route_length_mm", choice.length}, {"polyline_inter_harness_gap_mm", choice.gap}}}});
        }
        rankedByPose.push_back(ranked);
    }
    std::vector<QJsonObject> rankedProposals;
    for (qsizetype index = 0; index < std::max<qsizetype>(3, supportIds.size()); ++index)
        for (const auto &ranked : rankedByPose)
            if (index < ranked.size())
                rankedProposals.push_back(ranked.at(index).toObject());
    // Keep the pose interleaving for equal risk. Spend the native budget
    // first on alternatives with no non-terminal obstacle or separation hint.
    const auto hints = [](const QJsonObject &row) {
        return row.value("screen").toObject().value("non_terminal_hints").toInt(std::numeric_limits<int>::max());
    };
    std::stable_sort(rankedProposals.begin(), rankedProposals.end(), [&hints](const auto &left, const auto &right) {
        return hints(left) < hints(right);
    });
    for (const auto &row : rankedProposals) {
        if (proposals.size() >= budget)
            break;
        proposals.append(row);
        eligible += row.contains("values");
    }
    return {{"status", eligible ? "GENERATED" : "NO_FEASIBLE_CANDIDATE_FOUND"}, {"proposals", proposals},
            {"coverage", QJsonObject{{"route_screen", "SPATIAL_LINE_ARC_POLYCORRIDOR_AND_AABB_HINTS"},
                {"route_trials_within_domain", routeTrials}, {"eligible", eligible},
                {"sampled_poses", static_cast<int>(poseLimit)}, {"possible_pose_count", static_cast<int>(poses.size())},
                {"budget_limited", proposals.size() == budget}, {"determination", "SCREEN_ONLY"}}},
            {"unknowns", QJsonArray{"SERVICE_SWEEPS", "CONTACT_ENGAGEMENT", "BRep_INTERFERENCE"}}};
}

QJsonObject multiharness(const QJsonObject &domain, const QJsonObject &baseline, const QJsonObject &problem,
                         int seed, const QString &family, int routeAlternative)
{
    const bool spatial = domain.value("schema") == v3SpatialDomainSchema;
    const auto families = spatial ? v3SpatialStrategies() : QStringList{"DIRECT", "DETOUR_POSITIVE", "DETOUR_NEGATIVE"};
    require(family.isEmpty() || families.contains(family), "Famille multi-faisceaux inconnue");
    require(routeAlternative >= 0 && routeAlternative <= 1, "Raffinement multi-faisceaux hors budget");
    const auto harnesses = domain.value("harnesses").toObject();
    const auto options = domain.value("support_options").toObject();
    require(harnesses.size() >= 2 && harnesses.size() <= (spatial ? 2 : 6) && options.size() >= (spatial ? 1 : 2) && options.size() <= 8,
            "Domaine multi-faisceaux incomplet");
    const auto restricted = problem.value("narrowing").toObject().value("support_zones").toArray();
    QStringList supportIds;
    QJsonArray supports;
    for (auto it = options.begin(); it != options.end(); ++it) {
        supports.append(it.value());
        if (restricted.isEmpty() || restricted.contains(it.key()))
            supportIds.append(it.key());
    }
    require(!supportIds.isEmpty() && (restricted.isEmpty() || supportIds.size() == restricted.size()),
            "Restriction de support hors du domaine scellé");
    const auto observations = baseline.value("routes").toObject();
    require(observations.keys() == harnesses.keys(), "Observation multi-faisceaux incomplète");
    std::vector<HarnessScene> scenes;
    for (auto it = harnesses.begin(); it != harnesses.end(); ++it) {
        const auto cable = it.value().toObject();
        auto scene = domain.value("scene").toObject();
        scene.insert("cable_occurrence", cable.value("occurrence_path"));
        scene.insert("ports", cable.value("ports"));
        auto projection = domain;
        projection.insert("scene", scene);
        projection.insert("supports", supports);
        auto bounds = cable.value("route").toObject();
        if (spatial) {
            bounds.insert("minimum_length_mm", cable.value("minimum_length_mm"));
            bounds.insert("maximum_length_mm", cable.value("maximum_length_mm"));
        }
        projection.insert("route", bounds);
        auto measured = baseline;
        const auto route = observations.value(it.key());
        require(route.toObject().value("diameter_mm") == cable.value("diameter_mm"),
                "Diamètre natif divergent du faisceau scellé");
        measured.insert("routes", QJsonObject{{it.key(), route}});
        auto obstacles = baseline.value("occurrences").toObject();
        for (const auto &other : harnesses)
            obstacles.remove(other.toObject().value("occurrence_path").toString());
        measured.insert("occurrences", obstacles);
        auto routeScene = readScene(projection, measured, problem);
        require(routeScene.coupled, "Port mobile indépendant requis pour chaque faisceau");
        // A plate can retain a curved segment. Only the independent native
        // contact check is authoritative for the selected multi-harness support.
        if (!spatial) {
            routeScene.anchors.clear();
        } else {
            require(!routeScene.polycorridors.empty() && routeScene.minLength > 0 && routeScene.maxLength >= routeScene.minLength,
                    "Contrat de parcours spatial incomplet");
            const auto obstacle = problem.value("external_obstacle").toObject();
            if (!obstacle.isEmpty()) {
                validateV3ExternalObstacle(obstacle);
                routeScene.obstacles.push_back({"external-obstacle",
                    {numbers<3>(obstacle.value("min_mm")), numbers<3>(obstacle.value("max_mm"))}, false});
            }
            for (const auto &value : baseline.value("service_volumes").toArray()) {
                const auto volume = value.toObject();
                if (volume.value("obstacles").toArray().contains(it.key()))
                    routeScene.obstacles.push_back({"service/" + volume.value("id").toString(),
                        readBounds(volume.value("bounds_mm")), volume.value("follows_device").toBool()});
            }
        }
        scenes.push_back({it.key(), std::move(routeScene)});
    }
    const auto poses = samplePoses(scenes.front().scene.translation, seed);
    const auto budget = problem.value("budget").toObject().value("max_proposals").toInt();
    require(budget > 0 && budget <= 512, "Budget de propositions multi-faisceaux invalide");
    if (spatial)
        return spatialProposals(scenes, poses, problem, supportIds, family.isEmpty() ? families.first() : family,
                                domain.value("minimum_clearance_mm").toDouble());
    const auto activeFamilies = family.isEmpty() ? families : QStringList{family};
    QSet<QString> signatures;
    QJsonArray proposals;
    int eligible = 0;
    for (const auto &pose : poses) {
        if (proposals.size() >= budget)
            break;
        for (const auto &primary : activeFamilies) {
            if (proposals.size() >= budget)
                break;
            const auto priority = families.indexOf(primary);
            const auto first = makeProposal(scenes.front().scene, pose.point, primary, routeAlternative);
            if (!first.contains("values")) {
                auto rejected = first;
                auto screen = rejected.value("screen").toObject();
                screen.insert("status", "SCREEN_REJECT");
                rejected.insert("screen", screen);
                proposals.append(rejected);
                continue;
            }
            QVector<QJsonObject> combinations;
            for (qsizetype strategy = 0; strategy < families.size(); ++strategy) {
                QJsonObject routes;
                QStringList issues;
                double estimatedLength = 0;
                double minimumGap = std::numeric_limits<double>::infinity();
                int trials = 0;
                for (std::size_t index = 0; index < scenes.size(); ++index) {
                    const auto &harness = scenes[index];
                    const auto sign = families.at((priority + strategy + static_cast<qsizetype>(index) - 1 + families.size())
                                                  % families.size());
                    const auto proposal = index == 0 ? first : makeProposal(harness.scene, pose.point, sign, routeAlternative);
                    const auto screen = proposal.value("screen").toObject();
                    trials += screen.value("route_trials").toInt();
                    for (const auto &issue : screen.value("blocking_issues").toArray())
                        issues.append(harness.id + '/' + issue.toString());
                    if (!proposal.contains("values"))
                        break;
                    auto route = proposal.value("values").toObject();
                    route.remove("translation_mm");
                    for (std::size_t other = 0; other < index; ++other) {
                        const auto gap = routeGap(route.value("route_points_mm").toArray(),
                            routes.value(scenes[other].id).toObject().value("route_points_mm").toArray(),
                            harness.scene.cableRadius + scenes[other].scene.cableRadius);
                        minimumGap = std::min(gap, minimumGap);
                        if (gap <= epsilon)
                            issues.append("inter-harness/" + scenes[other].id + '/' + harness.id);
                    }
                    routes.insert(harness.id, route);
                    estimatedLength += screen.value("estimated_route_length_mm").toDouble();
                }
                if (routes.size() != harnesses.size())
                    continue;
                const QJsonObject screen{{"status", issues.isEmpty() ? "SCREEN_PASS" : "NEEDS_NATIVE_CHECK"},
                    {"blocking_issues", QJsonArray::fromStringList(issues)}, {"route_trials", trials},
                    {"estimated_route_length_mm", estimatedLength}, {"polyline_inter_harness_gap_mm", minimumGap}};
                combinations.append(QJsonObject{{"family", primary}, {"routes", routes}, {"screen", screen}});
            }
            std::stable_sort(combinations.begin(), combinations.end(), [](const auto &left, const auto &right) {
                const auto first = left.value("screen").toObject();
                const auto second = right.value("screen").toObject();
                return std::pair{first.value("blocking_issues").toArray().size(), first.value("estimated_route_length_mm").toDouble()}
                     < std::pair{second.value("blocking_issues").toArray().size(), second.value("estimated_route_length_mm").toDouble()};
            });
            if (combinations.isEmpty()) {
                auto rejected = blockedPose(pose.point, primary, "NO_COMPLETE_HARNESS_COMPOSITION");
                auto screen = rejected.value("screen").toObject();
                screen.insert("status", "SCREEN_REJECT");
                rejected.insert("screen", screen);
                proposals.append(rejected);
            }
            for (const auto &candidate : combinations) {
                for (qsizetype option = 0; option < supportIds.size() && proposals.size() < budget; ++option) {
                    const auto choice = supportIds.at((option + priority + routeAlternative) % supportIds.size());
                    const QJsonObject values{{"translation_mm", json(pose.point)},
                        {"harnesses", candidate.value("routes")}, {"support_option", choice}};
                    const auto identity = signature(values);
                    if (signatures.contains(identity))
                        continue;
                    signatures.insert(identity);
                    auto portfolio = candidate;
                    portfolio.insert("values", values);
                    portfolio.insert("signature", identity);
                    portfolio.remove("routes");
                    proposals.append(portfolio);
                    ++eligible;
                }
            }
        }
    }
    return {{"status", eligible ? "GENERATED" : "NO_FEASIBLE_CANDIDATE_FOUND"}, {"proposals", proposals},
            {"coverage", QJsonObject{{"route_screen", "TUBE_ENVELOPE_AND_POLYLINE_GAP"},
                {"eligible", eligible}, {"possible_pose_count", static_cast<int>(poses.size())},
                {"budget_limited", proposals.size() == budget}, {"determination", "SCREEN_ONLY"}}},
            {"unknowns", QJsonArray{"SERVICE_SWEEPS", "CONTACT_ENGAGEMENT", "BRep_INTERFERENCE"}}};
}

} // namespace

QStringList v3SpatialStrategies()
{
    return {"SPATIAL_SHORTEST", "SPATIAL_CLEARANCE", "SPATIAL_EXCURSION"};
}

QJsonObject generateV3Proposals(const QJsonObject &domain, const QJsonObject &baseline,
                               const QJsonObject &problem, int seed, const QString &family, int routeAlternative)
{
    try {
        if (isV3MultiHarnessDomain(domain.value("schema")))
            return multiharness(domain, baseline, problem, seed, family, routeAlternative);
        const QStringList families{"DIRECT", "DETOUR_POSITIVE", "DETOUR_NEGATIVE"};
        require(family.isEmpty() || families.contains(family), "Famille de recherche inconnue");
        const auto scene = readScene(domain, baseline, problem);
        require(routeAlternative >= 0 && (routeAlternative == 0 || scene.coupled), "Variante de parcours hors contrat");
        const auto poses = samplePoses(scene.translation, seed);
        int eligible = 0;
        int totalTested = 0;
        QSet<QString> signatures;
        QJsonArray proposals;
        const int budget = problem.value("budget").toObject().value("max_proposals").toInt(64);
        require(budget > 0 && budget <= 1024, "Budget de propositions invalide");
        const auto activeFamilies = family.isEmpty() ? families : QStringList{family};
        const bool refining = routeAlternative > 0;
        QVector<QJsonObject> screened;
        for (const auto &pose : poses) {
            for (const auto &name : activeFamilies) {
                if (!refining && proposals.size() >= budget)
                    break;
                auto proposal = makeProposal(scene, pose.point, name, routeAlternative);
                ++totalTested;
                if (proposal.contains("values")) {
                    const auto id = signature(proposal.value("values").toObject());
                    if (signatures.contains(id))
                        continue;
                    signatures.insert(id);
                    proposal.insert("signature", id);
                }
                if (refining) {
                    screened.append(proposal);
                } else {
                    if (proposal.value("screen").toObject().value("status") != "SCREEN_REJECT")
                        ++eligible;
                    proposals.append(proposal);
                }
            }
            if (!refining && proposals.size() >= budget)
                break;
        }
        if (refining) {
            const auto risk = [](const QJsonObject &proposal) {
                const auto report = proposal.value("screen").toObject();
                return std::pair{report.value("status") == "SCREEN_REJECT",
                                 report.value("blocking_issues").toArray().size()};
            };
            std::stable_sort(screened.begin(), screened.end(), [&risk](const auto &first, const auto &second) {
                return risk(first) < risk(second);
            });
            for (const auto &proposal : screened) {
                if (proposals.size() == budget)
                    break;
                if (proposal.value("screen").toObject().value("status") != "SCREEN_REJECT")
                    ++eligible;
                proposals.append(proposal);
            }
        }
        return {{"status", eligible ? "GENERATED" : "NO_FEASIBLE_CANDIDATE_FOUND"}, {"proposals", proposals},
                {"coverage", QJsonObject{{"region_min_mm", json(scene.translation.min)},
                                         {"region_max_mm", json(scene.translation.max)},
                                         {"grid_levels_per_variable_axis", 5},
                                         {"possible_pose_count", static_cast<int>(poses.size())},
                                         {"evaluated_pose_family_count", totalTested}, {"eligible", eligible},
                                         {"route_screen", "TUBE_ENVELOPE_VS_OBSERVED_AABB"},
                                         {"budget_limited", totalTested < static_cast<int>(poses.size() * activeFamilies.size()) ||
                                                            screened.size() > proposals.size()},
                                         {"determination", "SCREEN_ONLY"}}},
                {"unknowns", QJsonArray{"SERVICE_SWEEPS", "CONTACT_ENGAGEMENT", "BRep_INTERFERENCE"}}};
    } catch (const V3UnsupportedPose &error) {
        return {{"status", "UNSUPPORTED"}, {"proposals", QJsonArray{}},
                {"unknowns", QJsonArray{QString::fromUtf8(error.what())}}};
    } catch (const std::runtime_error &error) {
        return {{"status", "CONSTRAINT_UNKNOWN"}, {"proposals", QJsonArray{}},
                {"unknowns", QJsonArray{QString::fromUtf8(error.what())}}};
    }
}

} // namespace convergence
