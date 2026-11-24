#include "V3Domain.hpp"

#include "Files.hpp"

#include <QFileInfo>
#include <QJsonDocument>
#include <QMap>
#include <array>
#include <cmath>
#include <filesystem>

namespace convergence {
namespace {

const QMap<QString, QString> domainPins{
    {"55e53b66a0f28f02750ee2b9fe8a93b832ff377415573b2605e097a1c3200cc7", "docs/electromechanical_v3/domains/workholding.json"},
    {"cbdeb65419ee71b08806990171f58f060a605896af7b5747480b9a0c68e98e43", "docs/electromechanical_v3/domains/c4.json"},
    {"12997df87840fd5fb929a54da42945d009b1c10ec4f1cd81e70c7310b5889b76", "docs/electromechanical_v3/domains/c1_coupled.json"},
    {"2de090aa20940fad9651d3d3b185857721aeec19ed535f1cc76faf316e7914d1", "docs/electromechanical_v3/domains/c1_coupled_secondary.json"},
};
constexpr auto domainSchema = "v3.parametric_domain/1";
constexpr auto bench = "SYNTHETIC_BENCH";
constexpr auto endpointToleranceMm = 1e-6;
using Point = std::array<double, 3>;
using Quaternion = std::array<double, 4>;

double number(const QJsonValue &value)
{
    require(value.isDouble() && std::isfinite(value.toDouble()), "Valeur paramétrique non finie");
    return value.toDouble();
}

Point point(const QJsonValue &value)
{
    const auto coordinates = value.toArray();
    require(coordinates.size() == 3, "Triplet paramétrique requis");
    return {number(coordinates.at(0)), number(coordinates.at(1)), number(coordinates.at(2))};
}

Quaternion quaternion(const QJsonValue &value)
{
    const auto values = value.toArray();
    require(values.size() == 4, "Quaternion XYZW requis");
    const Quaternion rotation{number(values.at(0)), number(values.at(1)),
                              number(values.at(2)), number(values.at(3))};
    double squaredLength = 0;
    for (const auto component : rotation)
        squaredLength += component * component;
    require(std::abs(squaredLength - 1) <= endpointToleranceMm, "Quaternion non unitaire");
    return rotation;
}

Point rotate(const Quaternion &rotation, const Point &local)
{
    const auto [x, y, z, w] = rotation;
    return {(1-2*(y*y+z*z))*local[0] + 2*(x*y-z*w)*local[1] + 2*(x*z+y*w)*local[2],
            2*(x*y+z*w)*local[0] + (1-2*(x*x+z*z))*local[1] + 2*(y*z-x*w)*local[2],
            2*(x*z-y*w)*local[0] + 2*(y*z+x*w)*local[1] + (1-2*(x*x+y*y))*local[2]};
}

Point add(const Point &left, const Point &right)
{
    return {left[0]+right[0], left[1]+right[1], left[2]+right[2]};
}

Point subtract(const Point &left, const Point &right)
{
    return {left[0]-right[0], left[1]-right[1], left[2]-right[2]};
}

double dot(const Point &left, const Point &right)
{
    return left[0]*right[0] + left[1]*right[1] + left[2]*right[2];
}

bool bounded(const Point &value, const Point &lower, const Point &upper)
{
    for (size_t axis = 0; axis < value.size(); ++axis)
        if (value[axis] < lower[axis] || value[axis] > upper[axis])
            return false;
    return true;
}

bool coincident(const Point &first, const Point &second)
{
    return std::hypot(first[0] - second[0], first[1] - second[1], first[2] - second[2]) <= endpointToleranceMm;
}

bool aligned(const Point &origin, const Point &next, const Point &axis)
{
    const Point displacement{next[0] - origin[0], next[1] - origin[1], next[2] - origin[2]};
    const double length = std::hypot(displacement[0], displacement[1], displacement[2]);
    if (length <= endpointToleranceMm)
        return false;
    const Point direction{displacement[0] / length, displacement[1] / length, displacement[2] / length};
    return coincident(direction, axis);
}

QJsonArray templateActions(const QJsonObject &domain, const QJsonObject &profile)
{
    const auto order = domain.value("composition").toArray();
    require(order.size() >= 2 && profile.value("compositions").toArray().contains(order),
            "Composition paramétrique hors profil scellé");
    QMap<QString, QJsonObject> byId;
    for (const auto &value : profile.value("actions").toArray()) {
        const auto action = value.toObject();
        byId.insert(identifier(action.value("id")), action);
    }
    QJsonArray actions;
    for (const auto &name : order) {
        const auto id = identifier(name);
        require(byId.contains(id), "Action paramétrique hors profil : " + id);
        actions.append(byId.value(id));
    }
    require(actions.at(0).toObject().value("operation") == "REPOSITION_DEVICE" &&
            actions.at(1).toObject().value("operation") == "REROUTE_HARNESS",
            "Composition paramétrique sans pose et cheminement ordonnés");
    return actions;
}

void verifyScene(const QJsonObject &domain, const QJsonObject &profile, const QJsonArray &actions)
{
    const auto model = profile.value("model").toObject();
    const auto occurrences = model.value("occurrences").toObject();
    const auto device = actions.at(0).toObject().value("occurrence").toString();
    const auto cable = actions.at(1).toObject().value("occurrence").toString();
    const auto ports = model.value("validation").toObject().value("routes").toObject().value(cable).toObject().value("ports");
    QJsonArray companions;
    for (const auto &key : model.value("moving_with").toObject().value(device).toArray())
        companions.append(occurrences.value(key.toString()));
    const auto scene = domain.value("scene").toObject();
    require(scene.value("device_occurrence") == occurrences.value(device) &&
            scene.value("cable_occurrence") == occurrences.value(cable) &&
            scene.value("moving_with") == companions && scene.value("ports") == ports,
            "Projection de scène distincte du profil scellé");
    if (domain.value("route").toObject().value("terminal_mode") == v3NativePortMode) {
        const auto interfaces = model.value("validation").toObject().value("ports").toObject();
        const auto ids = ports.toArray();
        require(ids.size() == 2, "Paire de ports natifs requise");
        const auto fixed = interfaces.value(ids.first().toString()).toObject();
        const auto attached = interfaces.value(ids.last().toString()).toObject();
        const auto moving = model.value("moving_with").toObject().value(device).toArray();
        require(fixed.value("equipment").toString() != device && attached.value("equipment") == device &&
                !moving.contains(fixed.value("equipment")) &&
                !fixed.value("datum").toString().isEmpty() && !attached.value("datum").toString().isEmpty(),
                "Ports de construction natifs indépendants incompatibles");
        const auto affected = actions.at(0).toObject().value("affected").toArray();
        require(affected.contains(cable) && affected.contains(ids.last()),
                "Fermeture de pose incomplète pour câble et port couplés");
        for (const auto &subject : moving)
            require(affected.contains(subject), "Fermeture de pose incomplète pour un volume ou ancrage attaché");
    }

    const auto supports = domain.value("supports").toArray();
    require(supports.size() == actions.size() - 2, "Ancrages du domaine et composition incohérents");
    for (qsizetype index = 0; index < supports.size(); ++index) {
        const auto authority = supports.at(index).toObject();
        const auto action = actions.at(index + 2).toObject();
        const auto operation = action.value("operation").toString();
        const auto occurrence = action.value("occurrence").toString();
        const auto parameters = action.value("parameters").toObject();
        require(operation == "RELOCATE_SUPPORT" || operation == "CREATE_SUPPORT",
                "Opérateur hors domaine paramétrique");
        const auto support = operation == "CREATE_SUPPORT" ? parameters.value("support").toString() : occurrence;
        const auto anchor = parameters.value("anchor").toString();
        const auto carrier = parameters.value("carrier").toString();
        require(authority.value("operation") == operation && authority.value("occurrence") == occurrence &&
                authority.value("anchor") == anchor && authority.value("anchor_path") == occurrences.value(anchor) &&
                authority.value("support_path") == occurrences.value(support) &&
                authority.value("carrier_path") == occurrences.value(carrier),
                "Support ou ancrage différent de la composition scellée");
    }
}

void validateRoute(const QJsonObject &rules, const QJsonObject &parameters, const QJsonObject &placement,
                   const QJsonObject &attachedPort, const QJsonArray &points, double radius)
{
    const auto minimum = number(rules.value("radius_min_mm"));
    require(minimum >= number(parameters.value("minimum_radius_mm")) &&
            radius >= minimum && radius <= number(rules.value("radius_max_mm")),
            "Rayon de proposition hors des limites scellées");
    require(points.size() >= 2 && points.size() >= rules.value("min_points").toInt() &&
            points.size() <= rules.value("max_points").toInt() && points.size() <= 16,
            "Nombre de points hors du domaine scellé");
    const auto lower = point(rules.value("corridor_min_mm"));
    const auto upper = point(rules.value("corridor_max_mm"));
    const auto start = point(rules.value("start_mm"));
    auto end = point(rules.value("end_reference_mm"));
    const auto terminal = rules.value("terminal_mode").toString();
    const auto pose = point(placement.value("translation_mm"));
    const auto startAxis = point(parameters.value("start_axis"));
    auto endAxis = point(parameters.value("end_axis"));
    if (terminal == "FOLLOW_TRANSLATION") {
        const auto reference = point(rules.value("device_reference_mm"));
        end = add(end, subtract(pose, reference));
    } else if (terminal == v3NativePortMode) {
        const auto local = attachedPort.value("local_pose").toObject();
        const auto rotation = quaternion(placement.value("rotation_xyzw"));
        const auto offset = rotate(rotation, point(local.value("translation_mm")));
        const auto reference = point(rules.value("device_reference_mm"));
        require(coincident(end, add(reference, offset)), "Origine du port native incompatible avec le repère nominal scellé");
        end = add(pose, offset);
        const auto tangent = attachedPort.contains("tangent_local") ? attachedPort.value("tangent_local") :
                                                                    attachedPort.value("outward_local");
        const auto localAxis = rotate(quaternion(local.value("rotation_xyzw")), point(tangent));
        endAxis = rotate(rotation, localAxis);
        require(coincident(endAxis, point(parameters.value("end_axis"))) &&
                coincident(add(startAxis, endAxis), {0, 0, 0}),
                "Tangentes natives et profil de route incompatibles");
    } else {
        require(terminal == "FIXED", "Liaison d'extrémité non définie");
    }
    auto previous = point(points.first());
    require(bounded(previous, lower, upper) && coincident(previous, start) && coincident(point(points.last()), end),
            "Extrémité de parcours incompatible avec le port scellé");
    for (qsizetype index = 1; index < points.size(); ++index) {
        const auto current = point(points.at(index));
        const auto step = subtract(current, previous);
        const double progress = terminal == v3NativePortMode ? dot(step, startAxis) : step[0];
        require(bounded(current, lower, upper) && progress > 1e-5,
                "Parcours hors corridor ou abscisse non croissante");
        previous = current;
    }
    require(aligned(start, point(points.at(1)), startAxis) &&
            aligned(end, point(points.at(points.size()-2)), endAxis),
            "Tangentes signées différentes du profil scellé");
}

} // namespace

QString v3DomainPath(const QString &sha)
{
    const auto path = domainPins.value(sha);
    require(!path.isEmpty(), "Autorité de domaine V3 inconnue");
    return path;
}

QJsonObject loadV3Domain(const QDir &root, const QString &sha)
{
    const auto name = v3DomainPath(sha);
    const auto absolute = root.absoluteFilePath(name);
    const auto canonical = fileInside(root, name);
    require(canonical == absolute && !hasRedirectedComponent(root, absolute) &&
            std::filesystem::hard_link_count(QFileInfo(canonical).filesystemFilePath()) == 1,
            "Autorité de domaine V3 partagée ou redirigée");
    const auto bytes = read(canonical);
    require(digest(bytes) == sha, "Empreinte de l'autorité paramétrique divergente");
    const auto domain = parseUniqueObject(bytes, canonical);
    require(domain.value("schema") == domainSchema && domain.value("domain") == bench,
            "Contrat de domaine V3 incompatible");
    return domain;
}

QJsonObject makeV3Plan(const QString &planId, const QString &domainSha, const QJsonObject &values)
{
    return {{"schema", v3ParametricPlanSchema}, {"domain", bench}, {"plan_id", identifier(planId)},
            {"authority_sha256", domainSha}, {"domain_sha256", domainSha}, {"values", values}};
}

QJsonObject validateV3Plan(const QJsonObject &domain, const QJsonObject &profile, const QString &domainSha,
                          const QJsonObject &plan)
{
    const auto id = identifier(plan.value("plan_id"));
    const auto values = plan.value("values").toObject();
    const auto routeRules = domain.value("route").toObject();
    const bool coupled = routeRules.value("terminal_mode") == v3NativePortMode;
    if (coupled && values.contains("rotation_xyzw"))
        throw V3UnsupportedPose();
    require(plan == makeV3Plan(id, domainSha, values) &&
            values.keys() == QStringList{"bend_radius_mm", "route_points_mm", "translation_mm"},
            "Plan paramétrique divergent du contrat v2");
    require(domain.value("schema") == domainSchema && domain.value("domain") == bench &&
            domain.value("model_id") == profile.value("model_id"), "Modèle hors de l'autorité paramétrique");
    auto actions = templateActions(domain, profile);
    verifyScene(domain, profile, actions);
    const auto positionRules = domain.value("placement").toObject();
    const auto translation = point(values.value("translation_mm"));
    require(bounded(translation, point(positionRules.value("translation_min_mm")),
                    point(positionRules.value("translation_max_mm"))),
            "Translation hors des limites scellées");
    auto move = actions.at(0).toObject();
    auto moveParameters = move.value("parameters").toObject();
    auto placement = moveParameters.value("placement").toObject();
    const auto nominal = move.value("expected_before").toObject().value("placement").toObject();
    require(positionRules.value("frame") == "ROOT" && moveParameters.value("frame") == "ROOT" &&
            placement.value("rotation_xyzw") == positionRules.value("rotation_xyzw"),
            "Repère ou orientation variables hors de l'autorité");
    if (coupled && (nominal.value("rotation_xyzw") != placement.value("rotation_xyzw") ||
                   positionRules.contains("rotation_bounds")))
        throw V3UnsupportedPose();
    placement.insert("translation_mm", values.value("translation_mm"));
    moveParameters.insert("placement", placement);
    move.insert("parameters", moveParameters);
    move.insert("effect", QJsonObject{{"placement", placement}});
    move.insert("expected_after", QJsonObject{{"placement", placement}});
    move.insert("domain_limits", positionRules);
    actions.replace(0, move);

    auto route = actions.at(1).toObject();
    auto routeParameters = route.value("parameters").toObject();
    const auto points = values.value("route_points_mm").toArray();
    const auto radius = number(values.value("bend_radius_mm"));
    const auto model = profile.value("model").toObject();
    const auto portIds = domain.value("scene").toObject().value("ports").toArray();
    const auto attachedPort = model.value("validation").toObject().value("ports").toObject().value(portIds.last().toString()).toObject();
    validateRoute(routeRules, routeParameters, placement, attachedPort, points, radius);
    routeParameters.insert("points_mm", points);
    routeParameters.insert("bend_radius_mm", radius);
    route.insert("parameters", routeParameters);
    route.insert("effect", QJsonObject{{"points_mm", points}, {"bend_radius_mm", radius}});
    route.insert("expected_after", QJsonObject{{"points_mm", points}});
    route.insert("domain_limits", routeRules);
    actions.replace(1, route);

    if (coupled) {
        const auto companions = model.value("moving_with").toObject().value(move.value("occurrence").toString()).toArray();
        const auto delta = subtract(translation, point(nominal.value("translation_mm")));
        for (qsizetype index = 2; index < actions.size(); ++index) {
            auto support = actions.at(index).toObject();
            const auto parameters = support.value("parameters").toObject();
            if (!companions.contains(parameters.value("anchor")))
                continue;
            auto expected = support.value("expected_after").toObject();
            auto supportPlacement = expected.value("placement").toObject();
            const auto after = add(point(supportPlacement.value("translation_mm")), delta);
            supportPlacement.insert("translation_mm", QJsonArray{after[0], after[1], after[2]});
            expected.insert("placement", supportPlacement);
            support.insert("expected_after", expected);
            actions.replace(index, support);
        }
    }

    return {{"schema", "v3.expanded_mutation_plan/1"}, {"domain", bench}, {"plan_id", id},
            {"authority_sha256", domainSha}, {"domain_sha256", domainSha},
            {"profile_sha256", domain.value("profile_sha256")}, {"actions", actions},
            {"context_sha256", digest(QJsonDocument(plan).toJson(QJsonDocument::Compact))}};
}

} // namespace convergence
