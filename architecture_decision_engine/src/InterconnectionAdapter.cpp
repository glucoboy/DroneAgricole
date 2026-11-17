#include "InterconnectionAdapter.hpp"
#include "Interconnection.hpp"

#include <QMap>
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace architecture_decision {
namespace {

using Point = std::array<double, 3>;
using Box = std::array<double, 6>;
using Matrix = std::array<std::array<double, 4>, 4>;

double number(const QJsonValue &value, const QString &name)
{
    if (!value.isDouble() || !std::isfinite(value.toDouble())) {
        throw std::runtime_error((name + " : nombre fini attendu").toStdString());
    }
    return value.toDouble();
}

double parameter(const QJsonObject &parameters, const QString &name)
{
    return parameters.contains(name) ? number(parameters.value(name), name) : 0;
}

template <std::size_t N>
std::array<double, N> coordinates(const QJsonValue &value, const QString &name)
{
    const auto entries = value.toArray();
    if (entries.size() != N) {
        throw std::runtime_error((name + " : dimensions invalides").toStdString());
    }
    std::array<double, N> result{};
    for (std::size_t i = 0; i < N; ++i) {
        result[i] = number(entries[i], name);
    }
    return result;
}

template <std::size_t N>
QJsonArray array(const std::array<double, N> &coordinates)
{
    QJsonArray result;
    for (double coordinate : coordinates) {
        result.append(coordinate);
    }
    return result;
}

Box box(const QJsonValue &value, const QString &name)
{
    const auto result = coordinates<6>(value, name);
    for (std::size_t axis = 0; axis < 3; ++axis) {
        if (result[axis] >= result[axis + 3]) {
            throw std::runtime_error((name + " : boîte sans volume").toStdString());
        }
    }
    return result;
}

Matrix matrix(const QJsonValue &value)
{
    const auto rows = value.toArray();
    if (rows.size() != 4) {
        throw std::runtime_error("Pose L2 de dimension invalide");
    }
    Matrix result{};
    for (std::size_t row = 0; row < 4; ++row) {
        result[row] = coordinates<4>(rows[row], "Pose L2");
    }
    return result;
}

QJsonArray array(const Matrix &matrix)
{
    QJsonArray result;
    for (const auto &row : matrix) {
        result.append(array(row));
    }
    return result;
}

QJsonValue labelBench(const QJsonValue &value)
{
    static const QMap<QString, QString> labels{
        {"device-a", "PM08"}, {"device-b", "PORTEUSE"},
        {"port-a", "PM08-CAN"}, {"port-b", "CAN1"}, {"cordon", "F31"},
        {"BANC-fiche", "BENCH-F31-STRAIGHT"}, {"BANC-EQUIPEMENT-a", "BENCH-PM08"},
        {"BANC-EQUIPEMENT-b", "BENCH-CAN1-HOST"}, {"banc-1", "bench-1"}
    };
    if (value.isObject()) {
        QJsonObject renamed;
        const auto object = value.toObject();
        for (auto it = object.constBegin(); it != object.constEnd(); ++it) {
            renamed.insert(labels.value(it.key(), it.key()), labelBench(it.value()));
        }
        return renamed;
    }
    if (value.isArray()) {
        QJsonArray renamed;
        for (const auto &item : value.toArray()) {
            renamed.append(labelBench(item));
        }
        return renamed;
    }
    return value.isString() ? QJsonValue(labels.value(value.toString(), value.toString())) : value;
}

void shiftFrame(interconnection::Index &frames, const QString &id, double dy)
{
    auto frame = frames.value(id);
    auto pose = matrix(frame.value("parent_from_local"));
    pose[1][3] += dy;
    frame.insert("parent_from_local", array(pose));
    frames.insert(id, frame);
}

struct Exit {
    Point position;
    Point axis;
};

Exit exit(const interconnection::Index &frames, const QString &id, const QString &mate)
{
    const auto frame = frames.value(id);
    const auto mating = frames.value(mate);
    if (frame.value("parent_frame_id") != mate || mating.value("parent_frame_id") != "root") {
        throw std::runtime_error("Le banc F31 attend une sortie fille de la fiche et une fiche exprimée dans root");
    }
    const auto local = matrix(frame.value("parent_from_local"));
    const auto world = matrix(mating.value("parent_from_local"));
    Exit result{};
    for (std::size_t row = 0; row < 3; ++row) {
        result.position[row] = world[row][3];
        for (std::size_t k = 0; k < 3; ++k) {
            result.position[row] += world[row][k] * local[k][3];
            result.axis[row] += world[row][k] * local[k][2];
        }
    }
    return result;
}

QJsonArray makeRoute(const interconnection::Index &frames, const QJsonObject &projection,
                     double height, double lateralExtension)
{
    const auto start = exit(frames, "exit-a", "mate-a-frame");
    const auto finish = exit(frames, "exit-b", "mate-b-frame");
    auto lead = start.position;
    for (std::size_t i = 0; i < lead.size(); ++i) {
        lead[i] += lateralExtension * start.axis[i];
    }
    const auto rise = number(projection.value("route_rise_x_mm"), "route_rise_x_mm");
    const auto descend = number(projection.value("route_return_x_mm"), "route_return_x_mm");
    const auto join = number(projection.value("route_join_x_mm"), "route_join_x_mm");
    if (!(lead[0] < rise && rise < descend && descend < join && join < finish.position[0])) {
        throw std::runtime_error("Ordre des abscisses du corridor F31 invalide");
    }
    const Point takeoff{rise, lead[1], lead[2]};
    const Point above{rise, lead[1], lead[2] + height};
    const Point crossing{descend, lead[1], lead[2] + height};
    const Point approach{join, finish.position[1], finish.position[2]};
    QJsonArray points;
    for (const auto &point : {start.position, lead, takeoff, above, crossing, approach, finish.position}) {
        if (points.isEmpty() || points.last() != array(point)) {
            points.append(array(point));
        }
    }
    return points;
}

void specifyUnknownMate(QJsonObject &dossier, QJsonObject &records, QJsonObject &interface)
{
    const auto catalogId = QStringLiteral("fiche-laterale-inconnue");
    auto mates = interconnection::index(records.value("connector_mates"), "connector_mates");
    auto mate = mates.value("mate-a");
    auto reference = mate.value("part_reference").toObject();
    reference.insert("value", QJsonValue::Null);
    reference.insert("status", "UNKNOWN");
    reference.insert("evidence_ids", QJsonArray{});
    reference.insert("revision", QJsonValue::Null);
    reference.insert("method", QJsonValue::Null);
    reference.insert("limits", "Fiche latérale hypothétique ; référence et accouplement à établir par L1.");
    mate.insert("part_reference", reference);
    mates.insert("mate-a", mate);
    QJsonArray selectedMates;
    for (const auto &entry : mates) {
        selectedMates.append(entry);
    }
    records.insert("connector_mates", selectedMates);

    auto catalog = dossier.value("catalog").toObject();
    auto parts = catalog.value("parts").toArray();
    parts.append(QJsonObject{{"id", catalogId}, {"role", "PLUG"}, {"origin", "UNKNOWN"},
        {"reference", reference}, {"attributes", QJsonObject{}}});
    catalog.insert("parts", parts);
    dossier.insert("catalog", catalog);
    interface.insert("mate_part_id", catalogId);
}

double distance(const Point &a, const Point &b)
{
    return std::hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

double signedClearance(const Box &a, const Box &b)
{
    Point gaps{};
    for (std::size_t axis = 0; axis < gaps.size(); ++axis) {
        gaps[axis] = std::max(a[axis] - b[axis + 3], b[axis] - a[axis + 3]);
    }
    const double separation = *std::max_element(gaps.cbegin(), gaps.cend());
    if (separation <= 0) {
        return separation;
    }
    return std::hypot(std::max(0.0, gaps[0]), std::max(0.0, gaps[1]), std::max(0.0, gaps[2]));
}

struct Obstacle {
    QString id;
    Box bounds;
};

QList<Obstacle> readObstacles(const QJsonArray &entries)
{
    QList<Obstacle> obstacles;
    for (const auto &value : entries) {
        const auto obstacle = value.toObject();
        const auto id = obstacle.value("id").toString();
        obstacles.append({id, box(obstacle.value("box_mm"), id)});
    }
    return obstacles;
}

QJsonObject serviceMargin(const QJsonValue &volume, const QList<Obstacle> &obstacles, double threshold)
{
    if (!volume.isArray()) {
        return {{"minimum_margin_mm", QJsonValue::Null}, {"obstacle_id", QJsonValue::Null},
            {"obstacle_margins", QJsonArray{}}};
    }
    const auto envelope = box(volume, "Enveloppe de service L2");
    double minimum = std::numeric_limits<double>::infinity();
    QString nearest;
    QJsonArray margins;
    for (const auto &obstacle : obstacles) {
        const auto margin = signedClearance(envelope, obstacle.bounds) - threshold;
        margins.append(QJsonObject{{"obstacle_id", obstacle.id}, {"margin_mm", margin}});
        if (margin < minimum) {
            minimum = margin;
            nearest = obstacle.id;
        }
    }
    return {{"minimum_margin_mm", minimum}, {"obstacle_id", nearest}, {"obstacle_margins", margins}};
}

QJsonObject routeChecks(const QJsonArray &points, const QList<Obstacle> &obstacles,
                        double radius, double clearance, double availableLength)
{
    if (points.size() < 2 || radius <= 0 || clearance <= 0 || availableLength <= 0) {
        throw std::runtime_error("Critères synthétiques de trajectoire F31 incomplets ou invalides");
    }
    QList<Box> segmentEnvelopes;
    double length = 0;
    auto previous = coordinates<3>(points.first(), "Trajectoire F31");
    for (qsizetype i = 1; i < points.size(); ++i) {
        const auto point = coordinates<3>(points[i], "Trajectoire F31");
        Box segment{};
        for (std::size_t axis = 0; axis < 3; ++axis) {
            segment[axis] = std::min(previous[axis], point[axis]) - radius;
            segment[axis + 3] = std::max(previous[axis], point[axis]) + radius;
        }
        segmentEnvelopes.append(segment);
        length += distance(previous, point);
        previous = point;
    }

    double minimum = std::numeric_limits<double>::infinity();
    QJsonArray blockers;
    QJsonArray margins;
    for (const auto &obstacle : obstacles) {
        double closest = std::numeric_limits<double>::infinity();
        for (const auto &segment : segmentEnvelopes) {
            closest = std::min(closest, signedClearance(segment, obstacle.bounds));
        }
        minimum = std::min(minimum, closest);
        margins.append(QJsonObject{{"obstacle_id", obstacle.id}, {"margin_mm", closest - clearance}});
        if (closest < clearance) {
            blockers.append(obstacle.id);
        }
    }
    return {{"status", blockers.isEmpty() && length <= availableLength ? "PASS" : "FAIL"},
        {"method", "Dégagement des réservations AABB de segments, dilatées du rayon de banc, et longueur de polyligne"},
        {"minimum_clearance_mm", std::max(0.0, minimum)}, {"signed_clearance_mm", minimum},
        {"minimum_margin_mm", minimum - clearance},
        {"required_clearance_mm", clearance},
        {"blocking_obstacle_ids", blockers}, {"obstacle_margins", margins}, {"length_mm", length},
        {"length_margin_mm", availableLength - length}};
}

} // namespace

QJsonObject validateInterconnection(const QJsonObject &source, const QJsonObject &parameters,
                                    const QJsonObject &projection, const QJsonArray &research)
{
    const auto configuration = projection.value("configuration_id").toString();
    if (source.value("mode") != "SYNTHETIC_BENCH" || projection.value("schema_version") != "1.0.0" ||
        source.value("model").toObject().value("configuration_id") != "banc-l2" || configuration.isEmpty()) {
        throw std::runtime_error("La projection F31 accepte seulement le banc synthétique L2 et sa configuration L3");
    }
    const auto displacement = parameter(parameters, "pm08_y_mm");
    const auto height = parameter(parameters, "f31_route_z_mm");
    const auto neighbor = parameter(parameters, "f35_y_mm");
    const auto plug = parameters.contains("can1_plug") ? parameters.value("can1_plug").toString()
                                                       : QStringLiteral("STRAIGHT");
    const bool lateral = plug == "LATERAL_UNKNOWN";
    if (plug != "STRAIGHT" && !lateral) {
        throw std::runtime_error("Variante de fiche F31 inconnue");
    }

    auto dossier = labelBench(source).toObject();
    auto model = dossier.value("model").toObject();
    auto records = model.value("records").toObject();
    if (lateral && !research.isEmpty()) {
        const auto report = research.first().toObject();
        auto questions = records.value("research_questions").toArray();
        questions.append(report.value("question"));
        records.insert("research_questions", questions);
        auto evidence = records.value("technical_evidence").toArray();
        for (const auto &item : report.value("technical_evidence").toArray()) {
            evidence.append(item);
        }
        records.insert("technical_evidence", evidence);
    }
    auto frames = interconnection::index(model.value("frames"), "frames");
    auto interfaces = interconnection::index(dossier.value("interfaces"), "interfaces");
    auto interface = interfaces.value("interface-a");
    shiftFrame(frames, "equipment-a", displacement);
    shiftFrame(frames, "mate-a-frame", displacement);

    double lateralExtension = 0;
    if (lateral) {
        const auto hypothesis = projection.value("lateral_hypothesis").toObject();
        for (const auto &key : {"plug_body_box_local_mm", "extraction_box_local_mm", "tool_box_local_mm"}) {
            box(hypothesis.value(key), key);
            interface.insert(key, hypothesis.value(key));
        }
        const auto nominalTravel = number(hypothesis.value("extraction_travel_mm"), "extraction_travel_mm");
        const auto studied = parameters.value("lateral_exit_mm");
        const auto travel = studied.isUndefined() || studied.isNull() ? nominalTravel
                                                                     : number(studied, "lateral_exit_mm");
        if (travel <= 0 || nominalTravel <= 0) {
            throw std::runtime_error("Course synthétique de retrait non positive");
        }
        auto envelope = box(interface.value("extraction_box_local_mm"), "Extraction latérale");
        envelope[5] += travel - nominalTravel;
        interface.insert("extraction_box_local_mm", array(envelope));
        interface.insert("extraction_travel_mm", travel);
        auto exitFrame = frames.value("exit-a");
        exitFrame.insert("parent_from_local", hypothesis.value("exit_parent_from_local"));
        frames.insert("exit-a", exitFrame);
        lateralExtension = number(hypothesis.value("exit_extension_mm"), "exit_extension_mm");
        if (lateralExtension <= 0 || projection.value("research_issue_id").toString().isEmpty()) {
            throw std::runtime_error("Hypothèse de sortie latérale ou question L1 incomplète");
        }
        specifyUnknownMate(dossier, records, interface);
    }
    dossier.insert("research_issue_ids", lateral ? QJsonArray{projection.value("research_issue_id")} : QJsonArray{});
    dossier.insert("interfaces", QJsonArray{interface, interfaces.value("interface-b")});

    auto route = interconnection::index(records.value("routes"), "routes").value("route-nominal");
    if (route.value("frame_id") != "root" || route.value("cable_ids") != QJsonArray{"F31"} ||
        route.value("geometry_kind") != "POLYLINE") {
        throw std::runtime_error("La projection attend la route nominale F31 du banc L2 dans root");
    }
    const auto points = makeRoute(frames, projection, height, lateralExtension);
    route.insert("points_mm", points);
    records.insert("routes", QJsonArray{route});
    model.insert("records", records);
    QJsonArray projectedFrames;
    for (const auto &frame : frames) {
        projectedFrames.append(frame);
    }
    model.insert("frames", projectedFrames);
    model.insert("states", QJsonArray{interconnection::index(model.value("states"), "states").value("nominal")});
    model.insert("configuration_id", configuration);
    dossier.insert("model", model);

    const auto availableLength = number(projection.value("cordon_length_mm"), "cordon_length_mm");
    auto cableParts = dossier.value("cable_parts").toObject();
    auto cablePart = cableParts.value("F31").toObject();
    auto specifications = cablePart.value("specifications").toObject();
    auto length = specifications.value("length_mm").toObject();
    length.insert("value", availableLength);
    length.insert("method", "Longueur disponible déclarée par la fixture synthétique L3");
    specifications.insert("length_mm", length);
    cablePart.insert("specifications", specifications);
    cableParts.insert("F31", cablePart);
    dossier.insert("cable_parts", cableParts);

    auto geometry = dossier.value("geometry").toObject();
    const auto serviceClearance = number(projection.value("service_clearance_mm"), "service_clearance_mm");
    if (serviceClearance <= 0 || projection.value("obstacles").toArray().isEmpty()) {
        throw std::runtime_error("Dégagement ou inventaire synthétique des obstacles incomplet");
    }
    auto obstacleIndex = interconnection::index(projection.value("obstacles"), "obstacles F31");
    if (!obstacleIndex.contains("F35")) {
        throw std::runtime_error("La boîte de F35 est requise");
    }
    auto f35 = obstacleIndex.value("F35");
    auto f35Box = box(f35.value("box_mm"), "F35");
    f35Box[1] += neighbor;
    f35Box[4] += neighbor;
    f35.insert("box_mm", array(f35Box));
    obstacleIndex.insert("F35", f35);
    QJsonArray obstacleRecords;
    for (const auto &obstacle : obstacleIndex) {
        obstacleRecords.append(obstacle);
    }
    const auto obstacles = readObstacles(obstacleRecords);
    geometry.insert("service_clearance_mm", serviceClearance);
    geometry.insert("obstacles_complete", true);
    geometry.insert("obstacles", obstacleRecords);
    dossier.insert("geometry", geometry);

    const auto report = interconnection::validate(dossier, "nominal", research);
    QJsonObject nativeInterface;
    for (const auto &entry : report.value("native_plan").toObject().value("interfaces").toArray()) {
        const auto native = entry.toObject();
        if (native.value("port_id") == "PM08-CAN") {
            nativeInterface = native;
            break;
        }
    }
    const auto cable = interconnection::index(records.value("cables"), "cables").value("F31");
    const auto radius = number(cable.value("outer_diameter_mm").toObject().value("value"), "Diamètre F31") / 2;
    const auto routeClearance = number(projection.value("route_clearance_mm"), "route_clearance_mm");
    return {{"dossier", dossier}, {"report", report},
        {"route_checks", routeChecks(points, obstacles, radius, routeClearance, availableLength)},
        {"service_checks", QJsonObject{
            {"extraction", serviceMargin(nativeInterface.value("extraction_box_mm"), obstacles, serviceClearance)},
            {"tool", serviceMargin(nativeInterface.value("tool_box_mm"), obstacles, serviceClearance)}}}};
}

} // namespace architecture_decision
