#include "ProblemSpec.hpp"

#include <QJsonArray>
#include <QJsonDocument>
#include <QList>
#include <QMap>
#include <QRegularExpression>
#include <QSet>
#include <array>
#include <cmath>
#include <stdexcept>

namespace architecture_decision {
namespace {

void require(bool condition, const QString &message)
{
    if (!condition) {
        throw std::runtime_error(message.toStdString());
    }
}

void fields(const QJsonObject &object, const QStringList &required, const QStringList &optional, const QString &name)
{
    for (const auto &key : required) {
        require(object.contains(key), name + " : champ manquant " + key);
    }
    for (auto it = object.begin(); it != object.end(); ++it) {
        require(required.contains(it.key()) || optional.contains(it.key()), name + " : champ inconnu " + it.key());
    }
}

bool digest(const QJsonValue &value)
{
    static const QRegularExpression pattern(QStringLiteral("\\A[0-9a-f]{64}\\z"));
    return pattern.match(value.toString()).hasMatch();
}

qint64 integer(const QJsonValue &value, qint64 minimum, qint64 maximum, const QString &name)
{
    const auto result = value.toInteger(-1);
    require(result >= minimum && result <= maximum, "Entier hors limites : " + name);
    return result;
}

using Point = std::array<double, 3>;

Point point(const QJsonValue &value, const QString &name)
{
    const auto array = value.toArray();
    require(array.size() == 3, "Vecteur XYZ attendu : " + name);
    Point result{};
    for (qsizetype axis = 0; axis < 3; ++axis) {
        require(array.at(axis).isDouble() && std::isfinite(array.at(axis).toDouble()), "Coordonnée non finie : " + name);
        result.at(axis) = array.at(axis).toDouble();
    }
    return result;
}

struct Box {
    Point low;
    Point high;
};

Box box(const QJsonValue &minimum, const QJsonValue &maximum, const QString &name)
{
    const Box result{point(minimum, name + ".min"), point(maximum, name + ".max")};
    for (std::size_t axis = 0; axis < result.low.size(); ++axis) {
        require(result.low[axis] <= result.high[axis], "Bornes inversées : " + name);
    }
    return result;
}

bool inside(const Box &candidate, const Box &limit)
{
    for (std::size_t axis = 0; axis < candidate.low.size(); ++axis) {
        if (candidate.low[axis] < limit.low[axis] || candidate.high[axis] > limit.high[axis]) {
            return false;
        }
    }
    return true;
}

QSet<QString> supportZones(const QJsonObject &narrowing, const QSet<QString> &authorized)
{
    const auto value = narrowing.value("support_zones");
    if (value.isUndefined()) {
        return authorized;
    }
    const auto zones = value.toArray();
    require(!zones.isEmpty(), "Restriction d'ancrage vide");
    QSet<QString> result;
    for (const auto &zone : zones) {
        const auto id = zone.toString();
        require(authorized.contains(id) && !result.contains(id), "Ancrage non autorisé ou dupliqué : " + id);
        result.insert(id);
    }
    return result;
}

struct ProblemGeometry {
    Box translation;
    QSet<QString> supportZones;
};

ProblemGeometry problemGeometry(const QJsonObject &request, const QJsonObject &domain)
{
    const auto narrowing = request.value("narrowing").toObject();
    fields(narrowing, {"translation_mm"}, {"support_zones"}, "Restriction");
    const auto translation = narrowing.value("translation_mm").toObject();
    fields(translation, {"min", "max"}, {}, "Translation");
    const auto permitted = domain.value("placement").toObject();
    const auto bounds = box(permitted.value("translation_min_mm"), permitted.value("translation_max_mm"), "Domaine scellé");
    const auto restricted = box(translation.value("min"), translation.value("max"), "Translation");
    require(inside(restricted, bounds), "Restriction hors domaine de translation scellé");
    QSet<QString> authorizedZones;
    for (const auto &support : domain.value("supports").toArray()) {
        const auto anchor = support.toObject().value("anchor").toString();
        require(!anchor.isEmpty() && !authorizedZones.contains(anchor), "Ancrage ambigu dans le domaine scellé");
        authorizedZones.insert(anchor);
    }
    return {restricted, supportZones(narrowing, authorizedZones)};
}

void validateObjectives(const QJsonArray &objectives)
{
    static const QMap<QString, QString> directions{{"route_length_mm", "MIN"}, {"service_clearance_mm", "MAX"},
        {"support_count", "MIN"}};
    require(!objectives.isEmpty(), "Au moins un objectif Pareto est requis");
    QSet<QString> metrics;
    for (const auto &value : objectives) {
        const auto objective = value.toObject();
        fields(objective, {"metric", "direction"}, {}, "Objectif Pareto");
        const auto metric = objective.value("metric").toString();
        require(directions.contains(metric) && directions.value(metric) == objective.value("direction").toString() &&
                !metrics.contains(metric), "Objectif Pareto inconnu, inversé ou dupliqué : " + metric);
        metrics.insert(metric);
    }
}

ProblemGeometry validate(const QJsonObject &request, const ProblemSources &sources)
{
    fields(request, {"schema", "phase", "domain_sha256", "model_sha256", "observation_sha256",
                     "seed", "budget", "narrowing", "objectives"}, {"base_problem_sha256"}, "Problème V3");
    require(request.value("schema") == "v3.problem_spec/1", "Version du problème V3 inconnue");
    const auto phase = request.value("phase").toString();
    require(QStringList{"T0", "T1", "T2", "T3"}.contains(phase), "Phase de généralisation inconnue");
    require((phase == "T2") == request.contains("base_problem_sha256"), "Référence T1 requise seulement pour T2");
    require(phase != "T2" || digest(request.value("base_problem_sha256")), "Empreinte de référence T1 invalide");
    require(digest(request.value("domain_sha256")) && request.value("domain_sha256") == sources.domainSha256,
            "Empreinte du domaine scellé divergente");
    require(digest(request.value("model_sha256")) && request.value("model_sha256") == sources.modelSha256,
            "Empreinte du modèle XLink divergente");
    require(digest(request.value("observation_sha256")) && request.value("observation_sha256") == sources.observationSha256,
            "Empreinte de l'observation divergente");
    integer(request.value("seed"), 0, 2147483647, "graine");
    const auto budget = request.value("budget").toObject();
    fields(budget, {"max_proposals", "max_native"}, {}, "Budget");
    const auto proposals = integer(budget.value("max_proposals"), 3, 512, "max_proposals");
    const auto nativeBuilds = integer(budget.value("max_native"), 1, 16, "max_native");
    require(nativeBuilds <= proposals, "Budget max_native supérieur à max_proposals");
    validateObjectives(request.value("objectives").toArray());
    return problemGeometry(request, sources.domain);
}

} // namespace

QJsonObject parseProblemObject(const QByteArray &bytes, const QString &source)
{
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(bytes, &error);
    require(document.isObject(), source + " : objet JSON attendu (" + error.errorString() + ')');
    QList<QSet<QString>> objects;
    // Qt valide les jetons puis fusionne les noms égaux. Garder leurs limites pour refuser cette ambiguïté.
    for (qsizetype index = 0; index < bytes.size(); ++index) {
        const auto token = bytes.at(index);
        if (token == '{') {
            objects.emplaceBack();
        } else if (token == '}') {
            objects.removeLast();
        } else if (token == '"') {
            const auto start = index++;
            while (bytes.at(index) != '"') {
                index += bytes.at(index) == '\\' ? 2 : 1;
            }
            auto next = index + 1;
            while (next < bytes.size() && QByteArrayView(" \t\r\n").contains(bytes.at(next))) {
                ++next;
            }
            if (next < bytes.size() && bytes.at(next) == ':') {
                const auto encoded = bytes.sliced(start, index - start + 1);
                const auto key = QJsonDocument::fromJson('[' + encoded + ']').array().at(0).toString();
                require(!objects.last().contains(key), source + " : champ JSON dupliqué " + key);
                objects.last().insert(key);
            }
        }
    }
    return document.object();
}

QJsonObject validateProblemSpec(const QJsonObject &request, const ProblemSources &sources,
                                const std::optional<BaseProblem> &base)
{
    require(sources.domain.value("schema") == "v3.parametric_domain/1" &&
            sources.domain.value("domain") == "SYNTHETIC_BENCH", "Domaine paramétrique de banc requis");
    const auto geometry = validate(request, sources);
    require((request.value("phase") == "T2") == base.has_value(), "Fichier de référence T1 requis seulement pour T2");
    if (!base) {
        return request;
    }
    require(request.value("base_problem_sha256") == base->sha256 && base->spec.value("phase") == "T1",
            "La phase T2 doit référencer la preuve T1 exacte");
    const auto baseline = validate(base->spec, sources);
    for (const auto &field : {"seed", "budget", "objectives"}) {
        require(request.value(field) == base->spec.value(field), "Politique de recherche modifiée en T2 : " + QString(field));
    }
    require(inside(geometry.translation, baseline.translation) && baseline.supportZones.contains(geometry.supportZones),
            "Restriction T2 hors périmètre T1");
    require(geometry.translation.low != baseline.translation.low || geometry.translation.high != baseline.translation.high ||
            geometry.supportZones != baseline.supportZones, "La phase T2 exige une restriction stricte");
    return request;
}

} // namespace architecture_decision
