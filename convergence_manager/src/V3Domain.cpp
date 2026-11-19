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
};
constexpr auto domainSchema = "v3.parametric_domain/1";
constexpr auto bench = "SYNTHETIC_BENCH";
constexpr auto endpointToleranceMm = 1e-6;
using Point = std::array<double, 3>;

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

void validateRoute(const QJsonObject &rules, const QJsonObject &parameters, const Point &pose,
                   const QJsonArray &points, double radius)
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
    if (terminal == "FOLLOW_TRANSLATION") {
        const auto reference = point(rules.value("device_reference_mm"));
        for (size_t axis = 0; axis < end.size(); ++axis)
            end[axis] += pose[axis] - reference[axis];
    } else {
        require(terminal == "FIXED", "Liaison d'extrémité non définie");
    }
    auto previous = point(points.first());
    require(bounded(previous, lower, upper) && coincident(previous, start) && coincident(point(points.last()), end),
            "Extrémité de parcours incompatible avec le port scellé");
    for (qsizetype index = 1; index < points.size(); ++index) {
        const auto current = point(points.at(index));
        require(bounded(current, lower, upper) && current[0] - previous[0] > 1e-5,
                "Parcours hors corridor ou abscisse non croissante");
        previous = current;
    }
    require(aligned(start, point(points.at(1)), point(parameters.value("start_axis"))) &&
            aligned(end, point(points.at(points.size()-2)), point(parameters.value("end_axis"))),
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
    require(positionRules.value("frame") == "ROOT" && moveParameters.value("frame") == "ROOT" &&
            placement.value("rotation_xyzw") == positionRules.value("rotation_xyzw"),
            "Repère ou orientation variables hors de l'autorité");
    placement.insert("translation_mm", values.value("translation_mm"));
    moveParameters.insert("placement", placement);
    move.insert("parameters", moveParameters);
    move.insert("effect", QJsonObject{{"placement", placement}});
    move.insert("expected_after", QJsonObject{{"placement", placement}});
    move.insert("domain_limits", positionRules);
    actions.replace(0, move);

    auto route = actions.at(1).toObject();
    const auto routeRules = domain.value("route").toObject();
    auto routeParameters = route.value("parameters").toObject();
    const auto points = values.value("route_points_mm").toArray();
    const auto radius = number(values.value("bend_radius_mm"));
    validateRoute(routeRules, routeParameters, translation, points, radius);
    routeParameters.insert("points_mm", points);
    routeParameters.insert("bend_radius_mm", radius);
    route.insert("parameters", routeParameters);
    route.insert("effect", QJsonObject{{"points_mm", points}, {"bend_radius_mm", radius}});
    route.insert("expected_after", QJsonObject{{"points_mm", points}});
    route.insert("domain_limits", routeRules);
    actions.replace(1, route);

    return {{"schema", "v3.expanded_mutation_plan/1"}, {"domain", bench}, {"plan_id", id},
            {"authority_sha256", domainSha}, {"domain_sha256", domainSha},
            {"profile_sha256", domain.value("profile_sha256")}, {"actions", actions},
            {"context_sha256", digest(QJsonDocument(plan).toJson(QJsonDocument::Compact))}};
}

} // namespace convergence
