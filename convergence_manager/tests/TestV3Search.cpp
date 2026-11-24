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
        if (proposal.toObject().value("screen").toObject().value("status") == "ELIGIBLE")
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

} // namespace

int main(int argc, char **argv)
{
    try {
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
