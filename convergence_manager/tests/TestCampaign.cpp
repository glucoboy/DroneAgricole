#include "Campaign.hpp"

#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QTemporaryDir>
#include <cstdio>
#include <stdexcept>
#include <utility>

namespace {

using namespace convergence;

const QString referenceHash(64, 'a');

void check(bool condition, const char *message)
{
    if (!condition) {
        throw std::runtime_error(message);
    }
}

QByteArray read(const QString &path)
{
    QFile file(path);
    check(file.open(QIODevice::ReadOnly), "Lecture du témoin de campagne impossible");
    return file.readAll();
}

QJsonObject object(const QString &path)
{
    const auto doc = QJsonDocument::fromJson(read(path));
    check(doc.isObject(), "Objet de campagne JSON attendu");
    return doc.object();
}

QString sha(const QByteArray &data)
{
    return QString::fromLatin1(QCryptographicHash::hash(data, QCryptographicHash::Sha256).toHex());
}

enum class Fault { None, Save, MissingCoverage, WrongNative, InterruptLastReservation, LaterSave, IncompatibleConnector };

struct SimulatedInterruption {};

class Bench final : public Backend {
public:
    Bench(const QDir &root, Fault fault) : root_(root), fault_(fault) {}

    QJsonObject inventory() override
    {
        return {{"reference_sha256", referenceHash}};
    }

    QJsonObject research(const QString &issue, const QDir &) override
    {
        ++researchCalls;
        const bool incompatible = fault_ == Fault::IncompatibleConnector;
        return {{"issue_id", issue}, {"outcome", incompatible ? "RESOLVED" : "UNKNOWN"},
                {"value", QJsonObject{{"value", incompatible ? QJsonValue(false) : QJsonValue(QJsonValue::Null)}}},
                {"technical_evidence", QJsonArray{}}};
    }

    QJsonObject explore(const QDir &) override
    {
        ++exploreCalls;
        return {{"alternatives", QJsonArray{
            QJsonObject{{"id", "lateral-screen"}, {"family", "LATERAL_CORRIDOR"}, {"status", "PASS"}},
            QJsonObject{{"id", "upper-screen"}, {"family", "UPPER_CORRIDOR"}, {"status", "PASS"}},
            QJsonObject{{"id", "connector"}, {"family", "CONNECTOR"}, {"status", "INCONCLUSIVE"}}}}};
    }

    QJsonObject build(const QJsonObject &assignments, const QDir &operation) override
    {
        const bool consolidated = operation.absolutePath().contains("/consolidations/");
        if (consolidated) {
            ++consolidationBuilds;
        }
        check(operation.mkpath("."), "Création du dossier du témoin impossible");
        const auto bytes = QJsonDocument(assignments).toJson(QJsonDocument::Compact);
        QFile native(operation.filePath("candidate.FCStd"));
        if (consolidated && (fault_ == Fault::Save ||
            (fault_ == Fault::LaterSave && operation.absolutePath().contains("/upper-service/")))) {
            check(native.open(QIODevice::WriteOnly | QIODevice::NewOnly) && native.write("incomplete") == 10,
                  "L’écriture incomplète doit rester dans une copie propre");
            native.close();
            failedNatives.append(native.fileName());
            throw std::runtime_error("FC_SAVE_INJECTED");
        }
        if (consolidated && fault_ == Fault::InterruptLastReservation &&
            operation.absolutePath().contains("/lateral-service/")) {
            check(native.open(QIODevice::WriteOnly | QIODevice::NewOnly) && native.write("incomplete") == 10,
                  "La réservation interrompue conserve son fichier partiel");
            native.close();
            failedNatives.append(native.fileName());
            fault_ = Fault::None;
            throw SimulatedInterruption{};
        }
        check(native.open(QIODevice::WriteOnly | QIODevice::NewOnly) && native.write(bytes) == bytes.size(),
              "Le backend de test ne doit jamais écraser un natif");
        native.close();
        const auto route = assignments.value("route:L1").toString();
        const bool localCollision = route == "l1-direct" || route.startsWith("l1-offset-");
        const auto findings = localCollision ? QJsonArray{QJsonObject{{"code", "V2.PAIR"}, {"status", "FAIL"},
            {"subjects", QJsonArray{"L1", "Obstacle"}}, {"state", "S-NOMINAL"}}} : QJsonArray{};
        const auto height = route == "l1-upper" ? 24.0 : 11.0;
        return {{"status", localCollision ? "FAIL" : "PASS"}, {"findings", findings},
                {"metrics", QJsonObject{{"total_length_mm", route == "l1-upper" ? 225.0 : 230.0},
                                        {"max_cable_z_mm", height}}},
                {"path", root_.relativeFilePath(native.fileName())}, {"sha256", sha(bytes)},
                {"reference_sha256", referenceHash}, {"coverage", QJsonArray{"L1", "L2"}}};
    }

    QJsonObject validate(const QJsonObject &built, const QDir &) override
    {
        ++validationCalls;
        const auto digest = built.value("sha256").toString();
        const auto native = root_.filePath(built.value("path").toString());
        const auto bytes = read(native);
        check(digest == sha(bytes),
              "Le validateur reçoit les octets de la transaction");
        const auto assignments = QJsonDocument::fromJson(bytes).object();
        const bool sharedCollision = assignments.value("route:L1") == "l1-shared" && assignments.value("route:L2") == "l2-direct";
        const auto findings = sharedCollision ? QJsonArray{QJsonObject{{"code", "V2.PAIR"}, {"status", "FAIL"},
            {"subjects", QJsonArray{"L1", "L2"}}, {"state", "S-NOMINAL"}}} : QJsonArray{};
        const auto coverage = fault_ == Fault::MissingCoverage ? QJsonArray{"L1"} : QJsonArray{"L1", "L2"};
        return {{"status", sharedCollision ? "FAIL" : "PASS"}, {"findings", findings}, {"coverage", coverage},
                {"metrics", built.value("metrics")}, {"reference_sha256", referenceHash},
                {"native_sha256", fault_ == Fault::WrongNative ? QString(64, 'b') : digest}};
    }

    int consolidationBuilds = 0;
    int validationCalls = 0;
    int researchCalls = 0;
    int exploreCalls = 0;
    QStringList failedNatives;

private:
    QDir root_;
    Fault fault_;
};

QJsonObject manifest(const QJsonObject &config)
{
    return {{"schema_version", 1}, {"configuration_sha256", sha(QJsonDocument(config).toJson())},
            {"reference_sha256", referenceHash}};
}

void exercise(const QDir &output, const QJsonObject &config, Fault fault)
{
    check(output.mkpath("."), "Dossier de test de campagne indisponible");
    Bench backend(output, fault);
    const auto frozen = manifest(config);
    {
        Campaign first(output, config, frozen, backend);
        check(first.run(1) == 4, "Une étape doit laisser une campagne reprenable");
    }
    const auto manifestBytes = read(output.filePath("manifest.json"));
    const auto initial = object(output.filePath("checkpoint.json"));
    Campaign resumed(output, config, frozen, backend);
    const auto code = resumed.run();
    const auto checkpoint = object(output.filePath("checkpoint.json"));
    check(checkpoint.value("state") == "VERDICT", "La campagne doit s’arrêter sur un verdict");
    check(read(output.filePath("manifest.json")) == manifestBytes, "La reprise doit conserver le manifeste");
    const auto before = initial.value("transitions").toArray();
    const auto after = checkpoint.value("transitions").toArray();
    check(after.size() >= before.size(), "L’historique ne doit pas être tronqué");
    for (qsizetype index = 0; index < before.size(); ++index) {
        check(after.at(index) == before.at(index), "L’historique de transitions doit être appendu");
    }
    check(backend.consolidationBuilds > 0 && backend.consolidationBuilds <= 2, "Consolidation bornée à deux essais");
    if (fault == Fault::None) {
        check(code == 0 && checkpoint.value("last_consolidated").isObject(), "Seul un résultat révalidé est promu");
        check(backend.researchCalls >= 1 && backend.exploreCalls >= 1, "Le défaut répété déclenche L1 et L3");
        return;
    }
    check(code == 2 || code == 3, "Un défaut de transaction produit un verdict borné");
    check(checkpoint.value("last_consolidated").isNull(), "Un défaut de transaction ne doit promouvoir aucun natif");
    if (fault == Fault::Save) {
        check(backend.validationCalls == 0, "Le validateur ne reçoit pas de résultat après un échec de sauvegarde");
        check(QJsonDocument(checkpoint).toJson().contains("FC_SAVE_INJECTED"), "L’échec de sauvegarde reste traçable");
        check(!backend.failedNatives.isEmpty(), "Un natif partiel existe dans le banc de défaut");
        for (const auto &partial : backend.failedNatives) {
            check(read(partial) == "incomplete", "Les nouvelles tentatives ne réutilisent pas une sauvegarde interrompue");
        }
    } else {
        check(backend.validationCalls > 0, "Le reçu insuffisant a effectivement été présenté au contrôle");
    }
}

void verifyLastReservationResumes(const QDir &output, const QJsonObject &config)
{
    check(output.mkpath("."), "Dossier du témoin d’interruption indisponible");
    Bench backend(output, Fault::InterruptLastReservation);
    const auto frozen = manifest(config);
    bool interrupted = false;
    try {
        Campaign first(output, config, frozen, backend);
        first.run();
    } catch (const SimulatedInterruption &) {
        interrupted = true;
    }
    check(interrupted, "Le témoin a été interrompu pendant la deuxième consolidation");
    const auto before = object(output.filePath("checkpoint.json"));
    check(before.value("consolidation_used") == 2, "La dernière réservation est durable avant le build");
    check(before.value("pending_consolidation").toObject().value("id") == "lateral-service",
          "La consolidation interrompue reste identifiable");
    Campaign resumed(output, config, frozen, backend);
    check(resumed.run() == 0, "La dernière consolidation réservée doit reprendre sans débit supplémentaire");
    const auto after = object(output.filePath("checkpoint.json"));
    check(after.value("consolidation_used") == 2, "Une reprise ne consomme pas une nouvelle consolidation");
    check(after.value("last_consolidated").toObject().value("id") == "lateral-service",
          "Le deuxième essai de build peut être promu après la rétrovalidation");
    check(backend.failedNatives.size() == 1 && read(backend.failedNatives.first()) == "incomplete",
          "Les octets d’un build interrompu ne sont pas réutilisés");
}

void verifyRollbackPreservesCandidate(const QDir &output, QJsonObject config)
{
    check(output.mkpath("."), "Dossier du témoin de rollback indisponible");
    auto budgets = config.value("budgets").toObject();
    budgets.insert("consolidation_attempts", 3);
    config.insert("budgets", budgets);
    auto portfolios = config.value("portfolios").toArray();
    const auto lateral = portfolios.takeAt(2);
    portfolios.prepend(lateral);
    config.insert("portfolios", portfolios);
    Bench backend(output, Fault::LaterSave);
    Campaign campaign(output, config, manifest(config), backend);
    check(campaign.run() == 0, "Le dernier candidat valide reste disponible après le rollback");
    const auto checkpoint = object(output.filePath("checkpoint.json"));
    const auto accepted = checkpoint.value("last_consolidated").toObject();
    check(accepted.value("id") == "lateral-service", "L’échec ultérieur ne remplace pas le candidat publié");
    const auto saved = read(output.filePath(accepted.value("path").toString()));
    check(accepted.value("sha256") == sha(saved), "Le natif publié conserve ses octets après rollback");
    const auto last = checkpoint.value("portfolios").toArray().last().toObject();
    check(last.value("id") == "upper-service" && last.value("rollback") == true,
          "Le dernier échec est consigné avec rollback");
    check(backend.failedNatives.size() == 1 && read(backend.failedNatives.first()) == "incomplete",
          "La sauvegarde partielle reste isolée du candidat publié");
}

void verifyDigitalEvidenceCannotAuthorizePhysicalGo(const QDir &output, QJsonObject config)
{
    check(output.mkpath("."), "Dossier du témoin de jalon physique indisponible");
    config.insert("milestone", "PHYSICAL");
    Bench backend(output, Fault::None);
    Campaign campaign(output, config, manifest(config), backend);
    check(campaign.run() == 2, "Le banc numérique ne peut autoriser un GO physique");
    const auto outcome = object(output.filePath("campaign.json"));
    check(outcome.value("decision") == "NO_GO_MOTIVE" && outcome.value("physical_go") == false,
          "Le verdict distingue le périmètre physique");
    check(outcome.value("consolidated").isObject(), "La candidate numérique reste disponible comme preuve du banc");
    check(QJsonDocument(outcome).toJson().contains("PHYSICAL_EVIDENCE_REQUIRED"), "La raison du refus physique est conservée");
}

void verifyKnownIncompatibilityStaysOpen(const QDir &output, QJsonObject config)
{
    check(output.mkpath("."), "Dossier du témoin d’incompatibilité indisponible");
    const QString id("L3-F31-MATE-COMPATIBILITY");
    auto issues = config.value("issues").toObject();
    auto issue = issues.value(id).toObject();
    issue.insert("expected_value", true);
    issue.insert("impact", "CONDITION");
    issues.insert(id, issue);
    config.insert("issues", issues);
    Bench backend(output, Fault::IncompatibleConnector);
    Campaign campaign(output, config, manifest(config), backend);
    check(campaign.run() == 3, "Une preuve négative maintient la condition de compatibilité");
    const auto outcome = object(output.filePath("campaign.json"));
    check(outcome.value("consolidated").isObject(), "La preuve négative n’empêche pas la consolidation indépendante");
    const auto reasons = outcome.value("reasons").toArray();
    check(reasons.size() == 1 && reasons.first().toObject().value("code") == id &&
          reasons.first().toObject().value("reason").toString().contains("valeur requise"),
          "Le motif indique la contradiction avec la valeur requise");
}

void verifyShortLocalSequenceEscalates(const QDir &output, QJsonObject config)
{
    check(output.mkpath("."), "Dossier du témoin de série locale courte indisponible");
    QJsonArray candidates;
    for (const auto &entry : config.value("candidates").toArray()) {
        if (entry.toObject().value("id") != "local-offset-3") {
            candidates.append(entry);
        }
    }
    config.insert("candidates", candidates);
    Bench backend(output, Fault::None);
    Campaign campaign(output, config, manifest(config), backend);
    check(campaign.run() == 0 && backend.exploreCalls == 1,
          "Une série locale épuisée avant son budget ouvre l’exploration alternative");
    const auto progress = object(output.filePath("checkpoint.json")).value("problem_state").toObject()
                              .value("obstacle").toObject();
    check(progress.value("local_used") == 2 && progress.value("escalation_reason") == "LOCAL_SEQUENCE_EXHAUSTED",
          "Le motif distingue l’épuisement de la série du plafond de budget");
}

void verifyPortfolioAndLocalBuildHaveSeparateReceipts(const QDir &output, QJsonObject config)
{
    check(output.mkpath("."), "Dossier du témoin des reçus indisponible");
    auto portfolios = config.value("portfolios").toArray();
    auto portfolio = portfolios.at(2).toObject();
    portfolio.insert("id", "lateral");
    portfolios.replace(2, portfolio);
    config.insert("portfolios", portfolios);
    Bench backend(output, Fault::None);
    Campaign campaign(output, config, manifest(config), backend);
    check(campaign.run() == 0 && backend.consolidationBuilds == 2,
          "Un portefeuille et une variante de même nom doivent être construits séparément");
    const auto checkpoint = object(output.filePath("checkpoint.json"));
    const auto accepted = checkpoint.value("last_consolidated").toObject();
    check(accepted.value("path").toString().startsWith("consolidations/lateral/"),
          "Le reçu promu correspond à la fusion et au natif consolidé");
}

} // namespace

int main(int argc, char **argv)
{
    const QCoreApplication application(argc, argv);
    try {
        check(application.arguments().size() == 2, "Indiquer la configuration du banc de campagne");
        const auto config = object(application.arguments().at(1));
        check(QDir::current().mkpath(".runtime"), "Dossier .runtime indisponible");
        const QTemporaryDir work(QDir::current().filePath(".runtime/l5-api-test-XXXXXX"));
        check(work.isValid(), "Espace de test temporaire indisponible");
        for (const auto &[name, fault] : {std::pair{"nominal", Fault::None}, std::pair{"save", Fault::Save},
                std::pair{"missing-coverage", Fault::MissingCoverage}, std::pair{"wrong-native", Fault::WrongNative}}) {
            exercise(QDir(QDir(work.path()).filePath(name)), config, fault);
        }
        verifyLastReservationResumes(QDir(QDir(work.path()).filePath("interrupted-last")), config);
        verifyRollbackPreservesCandidate(QDir(QDir(work.path()).filePath("rollback")), config);
        verifyDigitalEvidenceCannotAuthorizePhysicalGo(QDir(QDir(work.path()).filePath("physical")), config);
        verifyKnownIncompatibilityStaysOpen(QDir(QDir(work.path()).filePath("incompatible")), config);
        verifyShortLocalSequenceEscalates(QDir(QDir(work.path()).filePath("short-local")), config);
        verifyPortfolioAndLocalBuildHaveSeparateReceipts(QDir(QDir(work.path()).filePath("receipts")), config);
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
    return 0;
}
