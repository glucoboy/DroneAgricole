#include "V3Search.hpp"
#include "V3Domain.hpp"

#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QSet>
#include <QTextStream>

#include <cmath>
#include <stdexcept>

namespace {

void check(bool condition, const char *message)
{
    if (!condition)
        throw std::runtime_error(message);
}

QJsonObject object(const QString &path)
{
    QFile file(path);
    check(file.open(QIODevice::ReadOnly), "Entrée de test indisponible");
    const auto document = QJsonDocument::fromJson(file.readAll());
    check(document.isObject(), "Entrée de test invalide");
    return document.object();
}

QJsonArray accepted(const QJsonObject &search)
{
    QJsonArray candidates;
    for (const auto proposal : search.value("proposals").toArray())
        if (proposal.toObject().value("screen").toObject().value("status") != "SCREEN_REJECT")
            candidates.append(proposal);
    return candidates;
}

void workholding(const QJsonObject &domain, const QJsonObject &baseline)
{
    const auto direct = convergence::generateV3Proposals(domain, baseline, {}, 2026, "DIRECT");
    check(accepted(direct).isEmpty(), "Un segment droit ne démontre pas un nouveau rayon");
    const auto first = convergence::generateV3Proposals(domain, baseline, {}, 2026, "DETOUR_POSITIVE");
    check(first == convergence::generateV3Proposals(domain, baseline, {}, 2026, "DETOUR_POSITIVE"),
          "Rejeu de la même graine divergent");
    const auto candidates = accepted(first);
    check(candidates.size() >= 3, "Moins de trois propositions distinctes de détour");
    QSet<QString> signatures;
    QSet<QByteArray> poses;
    for (const auto choice : candidates) {
        const auto proposal = choice.toObject();
        signatures.insert(proposal.value("signature").toString());
        const auto pose = proposal.value("values").toObject().value("translation_mm").toArray();
        poses.insert(QJsonDocument(pose).toJson(QJsonDocument::Compact));
    }
    check(signatures.size() == candidates.size() && poses.size() >= 3, "Déduplication de géométrie divergente");
    const auto poseBefore = candidates.first().toObject().value("values").toObject().value("translation_mm").toArray();
    const auto placement = domain.value("placement").toObject();
    const auto minimum = placement.value("translation_min_mm").toArray();
    auto maximum = placement.value("translation_max_mm").toArray();
    maximum.replace(1, (minimum.at(1).toDouble() + poseBefore.at(1).toDouble()) / 2);
    const QJsonObject restriction{{"narrowing", QJsonObject{{"translation_mm", QJsonObject{
        {"min", minimum}, {"max", maximum}}}}}};
    const auto perturbed = accepted(convergence::generateV3Proposals(domain, baseline, restriction, 2026,
                                                                       "DETOUR_POSITIVE"));
    check(!perturbed.isEmpty(), "Aucune alternative après restriction faisable");
    for (const auto choice : perturbed) {
        const auto translation = choice.toObject().value("values").toObject().value("translation_mm").toArray();
        check(translation != poseBefore && translation.at(1).toDouble() <= maximum.at(1).toDouble(),
              "Pose retenue hors restriction");
    }
}

void transfer(const QJsonObject &domain, const QJsonObject &baseline)
{
    const auto candidates = accepted(convergence::generateV3Proposals(domain, baseline, {}, 2026, "DIRECT"));
    check(candidates.size() >= 3, "Moins de trois routes après transfert de la porte");
    for (const auto choice : candidates) {
        const auto values = choice.toObject().value("values").toObject();
        const auto end = values.value("route_points_mm").toArray().last().toArray();
        const auto translation = values.value("translation_mm").toArray();
        check(end.at(1).toDouble() == translation.at(1).toDouble(), "Sortie terminale désolidarisée du port");
    }
    auto damaged = baseline;
    damaged.insert("status", "INCONCLUSIVE");
    const auto refused = convergence::generateV3Proposals(domain, damaged, {}, 2026);
    check(refused.value("status") == "CONSTRAINT_UNKNOWN" && refused.value("proposals").toArray().isEmpty(),
          "Une provenance non mesurée ouvre la recherche");
}

void coupled(const QJsonObject &domain, const QJsonObject &baseline, const QJsonObject &profile)
{
    const auto direct = accepted(convergence::generateV3Proposals(domain, baseline, {}, 2026, "DIRECT"));
    const auto alternatives = accepted(convergence::generateV3Proposals(domain, baseline, {}, 2026, "DIRECT", 1));
    check(direct.size() >= 2 && alternatives.size() >= 2, "Couverture des routes couplées insuffisante");
    const auto first = direct.first().toObject().value("values").toObject();
    bool variantFound = false;
    for (const auto &entry : alternatives) {
        const auto candidate = entry.toObject().value("values").toObject();
        variantFound |= first.value("translation_mm") == candidate.value("translation_mm") &&
                        first.value("route_points_mm") != candidate.value("route_points_mm");
    }
    check(variantFound, "Aucune variante intra-famille à pose identique");
    const QString authorityHash(64, 'a');
    const auto expanded = convergence::validateV3Plan(domain, profile, authorityHash,
        convergence::makeV3Plan("coupled-test", authorityHash, first));
    const auto actions = expanded.value("actions").toArray();
    check(actions.size() == 3, "Composition pose-câble-support incomplète");
    const auto before = profile.value("actions").toArray().at(2).toObject().value("expected_after").toObject()
                            .value("placement").toObject().value("translation_mm").toArray();
    const auto after = actions.at(2).toObject().value("expected_after").toObject().value("placement").toObject()
                           .value("translation_mm").toArray();
    const auto nominal = domain.value("route").toObject().value("device_reference_mm").toArray();
    const auto translated = first.value("translation_mm").toArray();
    for (int axis = 0; axis < 3; ++axis) {
        const auto expected = before.at(axis).toDouble() + translated.at(axis).toDouble() - nominal.at(axis).toDouble();
        check(std::abs(after.at(axis).toDouble() - expected) <= 1e-6, "Appui désolidarisé de son ancrage");
    }

    auto stale = first;
    auto points = first.value("route_points_mm").toArray();
    points.replace(points.size()-1, domain.value("route").toObject().value("end_reference_mm"));
    stale.insert("route_points_mm", points);
    bool refused = false;
    try {
        convergence::validateV3Plan(domain, profile, authorityHash, convergence::makeV3Plan("stale", authorityHash, stale));
    } catch (const std::runtime_error &) {
        refused = true;
    }
    check(refused, "Extrémité obsolète acceptée pour un port mobile");

    auto rotation = first;
    rotation.insert("rotation_xyzw", QJsonArray{0, 0, 0, 1});
    refused = false;
    try {
        convergence::validateV3Plan(domain, profile, authorityHash, convergence::makeV3Plan("rotated", authorityHash, rotation));
    } catch (const convergence::V3UnsupportedPose &) {
        refused = true;
    }
    check(refused, "Une rotation hors périmètre doit être déclarée UNSUPPORTED");
}

void multiharness(const QJsonObject &domain, const QJsonObject &baseline, const QJsonObject &profile)
{
    const QJsonObject problem{{"budget", QJsonObject{{"max_proposals", 48}}}};
    const auto search = convergence::generateV3Proposals(domain, baseline, problem, 2026);
    if (search.value("status") != "GENERATED")
        QTextStream(stderr) << QJsonDocument(search).toJson(QJsonDocument::Compact) << '\n';
    check(search.value("status") == "GENERATED", "Aucune proposition multi-faisceaux");
    check(search == convergence::generateV3Proposals(domain, baseline, problem, 2026), "Graine multi-faisceaux instable");
    const auto rows = search.value("proposals").toArray();
    check(rows.size() <= 48, "Budget de propositions multi-faisceaux dépassé");
    const auto harnesses = domain.value("harnesses").toObject();
    const QString authorityHash(64, 'a');
    QSet<QString> supportIds, signatures;
    QJsonObject witness;
    for (const auto &entry : rows) {
        const auto proposal = entry.toObject();
        const auto screen = proposal.value("screen").toObject();
        const auto status = screen.value("status");
        const auto issues = screen.value("blocking_issues").toArray();
        if (status == "SCREEN_REJECT")
            continue;
        check((status == "SCREEN_PASS" && issues.isEmpty()) || (status == "NEEDS_NATIVE_CHECK" && !issues.isEmpty()),
              "Un obstacle du criblage a été effacé");
        const auto values = proposal.value("values").toObject();
        const auto signature = proposal.value("signature").toString();
        check(!signature.isEmpty() && !signatures.contains(signature), "Proposition géométrique dupliquée");
        signatures.insert(signature);
        supportIds.insert(values.value("support_option").toString());
        const auto routes = values.value("harnesses").toObject();
        check(routes.keys() == harnesses.keys(), "Proposition omettant un câble");
        const auto plan = convergence::makeV3Plan("multiharness-test", authorityHash, values);
        const auto expanded = convergence::validateV3Plan(domain, profile, authorityHash, plan);
        const auto actions = expanded.value("actions").toArray();
        QSet<QString> rebuilt;
        for (const auto &item : actions) {
            const auto action = item.toObject();
            if (action.value("operation") == "REROUTE_HARNESS")
                rebuilt.insert(action.value("occurrence").toString());
        }
        check(plan.value("schema") == convergence::v3MultiHarnessPlanSchema && actions.size() == harnesses.size() + 2 &&
              rebuilt.size() == harnesses.size() &&
              actions.first().toObject().value("operation") == "REPOSITION_DEVICE" &&
              actions.last().toObject().value("occurrence") == values.value("support_option"), "Plan atomique incomplet");
        witness = values;
    }
    check(supportIds.size() >= 2 && !witness.isEmpty(), "Deux options d'appui attendues");
    const auto option = witness.value("support_option");
    auto restricted = problem;
    restricted.insert("narrowing", QJsonObject{{"support_zones", QJsonArray{option}}});
    const auto narrowed = accepted(convergence::generateV3Proposals(domain, baseline, restricted, 2026));
    check(!narrowed.isEmpty(), "Aucune alternative sous l'appui restreint");
    for (const auto &entry : narrowed)
        check(entry.toObject().value("values").toObject().value("support_option") == option,
              "Proposition hors du catalogue d'appuis restreint");
    const auto id = harnesses.keys().last();
    auto routes = witness.value("harnesses").toObject();
    auto route = routes.value(id).toObject();
    auto points = route.value("route_points_mm").toArray();
    points.replace(points.size() - 1, harnesses.value(id).toObject().value("route").toObject().value("end_reference_mm"));
    route.insert("route_points_mm", points);
    routes.insert(id, route);
    auto stale = witness;
    stale.insert("harnesses", routes);
    auto unsupported = witness;
    unsupported.insert("support_option", "unsealed-support");
    auto incomplete = witness;
    routes.remove(id);
    incomplete.insert("harnesses", routes);
    for (const auto &invalid : {stale, unsupported, incomplete}) {
        bool refused = false;
        try {
            convergence::validateV3Plan(domain, profile, authorityHash, convergence::makeV3Plan("invalid", authorityHash, invalid));
        } catch (const std::runtime_error &) {
            refused = true;
        }
        check(refused, "Un plan incomplet ou sans autorité a été accepté");
    }
}

} // namespace

int main(int argc, char **argv)
{
    try {
        if (argc == 5 && QString::fromLocal8Bit(argv[1]) == "--multiharness") {
            multiharness(object(QString::fromLocal8Bit(argv[2])), object(QString::fromLocal8Bit(argv[3])),
                         object(QString::fromLocal8Bit(argv[4])));
            QTextStream(stdout) << "Composition et refus multi-faisceaux vérifiés\n";
            return 0;
        }
        check(argc == 5 || argc == 8,
              "Usage : test_v3_search <domaine workholding> <observation> <domaine C4> <observation> [domaine C.1, observation, profil]");
        workholding(object(QString::fromLocal8Bit(argv[1])), object(QString::fromLocal8Bit(argv[2])));
        transfer(object(QString::fromLocal8Bit(argv[3])), object(QString::fromLocal8Bit(argv[4])));
        if (argc == 8)
            coupled(object(QString::fromLocal8Bit(argv[5])), object(QString::fromLocal8Bit(argv[6])),
                    object(QString::fromLocal8Bit(argv[7])));
        QTextStream(stdout) << "Recherche, restriction, reproductibilité et transfert vérifiés\n";
        return 0;
    } catch (const std::exception &error) {
        QTextStream(stderr) << error.what() << '\n';
        return 1;
    }
}
