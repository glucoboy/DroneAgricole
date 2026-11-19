#include "V3Search.hpp"

#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QSet>
#include <QTextStream>

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

} // namespace

int main(int argc, char **argv)
{
    try {
        check(argc == 5, "Usage : test_v3_search <domaine workholding> <observation> <domaine C4> <observation>");
        workholding(object(QString::fromLocal8Bit(argv[1])), object(QString::fromLocal8Bit(argv[2])));
        transfer(object(QString::fromLocal8Bit(argv[3])), object(QString::fromLocal8Bit(argv[4])));
        QTextStream(stdout) << "Recherche, restriction, reproductibilité et transfert vérifiés\n";
        return 0;
    } catch (const std::exception &error) {
        QTextStream(stderr) << error.what() << '\n';
        return 1;
    }
}
