#include "Admission.hpp"
#include "Files.hpp"
#include "ProcessBackend.hpp"

#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QSet>
#include <algorithm>

namespace convergence {
namespace {

const QString go3a = "docs/verification/go3a/";
const QString go3b = "docs/verification/go3b/";
const QString policyPath = "convergence_manager/fixtures/v21_evidence_plan.json";
const QSet<QString> statuses{"UNKNOWN", "INCONCLUSIVE", "NOT_RUN", "FAIL", "PASS"};

struct Authority {
    QJsonObject hashes;
    QJsonObject sources;
    QJsonObject history;
    QJsonObject gaps;
    QString candidate;
    QString reference;
    int budget;
};

QJsonObject checked(const QDir &root, const QString &name, const QJsonValue &sha)
{
    const auto bytes = read(fileInside(root, name));
    require(sha == digest(bytes), "Empreinte divergente : " + name);
    return parse(bytes, name);
}

void verifyFiles(const QDir &root, const QJsonObject &files)
{
    for (auto it = files.begin(); it != files.end(); ++it) {
        require(it.value() == fileDigest(fileInside(root, it.key())), "Source modifiée : " + it.key());
    }
}

Authority loadAuthority(const QDir &root)
{
    Authority result;
    const auto sourcesPath = go3b + "GO3B_SOURCE_MANIFEST.json";
    const auto historyPath = go3b + "GO3B_ADMISSION.json";
    const auto manifestPath = go3a + "GO3A_MANIFEST.json";
    const auto requirementsPath = go3a + "GO3A_REQUIREMENTS.yaml";
    const auto decisionsPath = go3a + "GO3A_DECISIONS.json";
    const auto modelPath = go3a + "GO3A_SYSTEM_MODEL.json";
    const QString sourcesSha = "56416edb6caa2f6601baf0fe68b619e9ac6d33408a901b24d899ba99393cf29d";
    const QString historySha = "b5bb1d3ab901e300b12558ba9cd33558210a9dee343520a0f0085257a7d58521";
    result.sources = checked(root, sourcesPath, sourcesSha).value("files").toObject();
    require(!result.sources.isEmpty(), "Inventaire GO3B absent");
    verifyFiles(root, result.sources);
    const auto manifest = checked(root, manifestPath, result.sources.value(manifestPath));
    const auto requirements = checked(root, requirementsPath, result.sources.value(requirementsPath));
    const auto decisions = checked(root, decisionsPath, result.sources.value(decisionsPath));
    const auto archive = checked(root, historyPath, historySha);
    require(manifest.value("schema") == "cartographe.go3a.receipt.v1" &&
            archive.value("schema") == "cartographe.go3b.admission.v1" &&
            decisions.value("schema") == "cartographe.go3a.decisions.v1" &&
            manifest.value("statut") == decisions.value("statut"), "Contrats historiques incompatibles");

    const auto deliverables = manifest.value("livrables").toObject();
    for (const auto &path : {requirementsPath, decisionsPath, modelPath}) {
        require(deliverables.value(QFileInfo(path).fileName()) == result.sources.value(path),
                "Livrable GO3A divergent : " + path);
    }
    const QJsonObject frozen{{"design_requirements.yaml", result.sources.value(requirementsPath)},
                             {"system_model.json", result.sources.value(modelPath)}};
    const auto seal = manifest.value("gel").toObject();
    result.reference = digest(QJsonDocument(frozen).toJson(QJsonDocument::Compact));
    require(seal.value("empreintes") == frozen && seal.value("reference_sha256") == result.reference &&
            archive.value("references").toObject().value("reference_sha256") == result.reference,
            "Gel GO3A divergent");

    result.candidate = identifier(decisions.value("cible_unique"));
    const auto status = decisions.value("statut");
    const auto authorization = decisions.value("autorisation_go3b");
    const auto front = decisions.value("front_admissible_cartographe");
    const auto archivedCheck = archive.value("controles_admission").toObject().value("admissibilite_go3a").toObject();
    const bool blocked = status == "GO3A_CONDITIONNEL" && authorization == false && front == QJsonArray{};
    require(blocked && archive.value("verdict") == "NO_GO_MOTIVE" && archivedCheck.value("statut") == "FAIL" &&
            archivedCheck.value("statut_go3a") == status && archivedCheck.value("autorisation_go3b") == authorization &&
            archivedCheck.value("front_admissible_cartographe") == front, "Le rejeu contredit le reçu GO3B");
    const auto budget = archive.value("cloture").toObject().value("budget_go3b").toObject();
    result.budget = budget.value("variantes_detaillees_max").toInt();
    require(result.budget > 0 && budget.value("consommation").toObject().value("variantes") == 0,
            "Comptabilité GO3B incohérente");
    result.history = {{"verdict", "NO_GO_MOTIVE"}, {"status", status}, {"autorisation_go3b", authorization},
        {"front_admissible_cartographe", front}, {"built", 0}, {"build_limit", result.budget}};

    const auto policy = load(fileInside(root, policyPath));
    require(policy.value("schema") == "drone_agricole.evidence_plan.v2.1", "Plan de preuve incompatible");
    const auto activities = policy.value("evidence_gap").toObject();
    QJsonObject recorded;
    for (const auto &item : archive.value("preconditions_ouvertes").toArray()) {
        const auto row = item.toObject();
        for (const auto &id : row.value("exigences").toArray()) {
            const auto key = identifier(id);
            require(!recorded.contains(key) && statuses.contains(row.value("statut").toString()) &&
                    row.value("statut") != "PASS", "État historique invalide : " + key);
            recorded.insert(key, row);
        }
    }
    for (const auto &item : requirements.value("exigences_imperatives").toArray()) {
        const auto requirement = item.toObject();
        const auto id = identifier(requirement.value("id"));
        const auto observation = recorded.value(id).toObject();
        auto activity = activities.value(id).toObject();
        require(!observation.isEmpty() && !activity.isEmpty() && !result.gaps.contains(id) &&
                activity.value("budget").toInt() > 0, "Activité ou provenance manquante : " + id);
        activity.insert("status", observation.value("statut"));
        activity.insert("known_value_or_hypothesis", observation.value("constat"));
        activity.insert("provenance", observation.value("preuve"));
        activity.insert("final_criterion", requirement.value("critere"));
        activity.insert("final_validation", requirement.value("controle"));
        result.gaps.insert(id, activity);
    }
    require(result.gaps.size() == 8 && recorded.size() == 8 && activities.size() == 8,
            "Couverture incomplète des exigences GO3A");
    for (const auto &path : {sourcesPath, manifestPath, requirementsPath, modelPath, decisionsPath, historyPath, policyPath}) {
        result.hashes.insert(path, fileDigest(fileInside(root, path)));
    }
    return result;
}

QJsonArray explorationBlocks(const QDir &output, const QJsonObject &plan)
{
    QJsonArray blocks;
    for (const auto &field : {"preserve_connectivity", "constraints_enabled", "unpowered", "private_copy"}) {
        if (plan.value(field) != true) {
            blocks.append(field);
        }
    }
    const QFileInfo target(output.filePath("candidate"));
    if (plan.value("write_target") != "candidate" || target.exists() || target.isSymLink() || target.isJunction()) {
        blocks.append("UNSAFE_WRITE_TARGET");
    }
    if (!QStringList{"PARAMETRIC_ENVELOPE", "UNPOWERED_LAYOUT", "RADIUS_SENSITIVITY"}.contains(
            plan.value("trial").toString())) {
        blocks.append("UNSAFE_TRIAL");
    }
    const auto findings = plan.value("trial_findings");
    require(findings.isObject(), "Constats de la variante requis");
    for (const auto &entry : findings.toObject().keys()) {
        const auto status = findings.toObject().value(entry).toString();
        require(statuses.contains(status), "État de constat invalide : " + entry);
        if (status == "FAIL") {
            blocks.append("KNOWN_VIOLATION:" + entry);
        }
    }
    return blocks;
}

QJsonObject finalReception(const QDir &root, const Authority &authority, const QString &receiptPath)
{
    QJsonObject result{{"verdict", "FINAL_NO_GO"}, {"reason", "INTEGRATED_CANDIDATE_AND_INDEPENDENT_EVIDENCE_REQUIRED"}};
    if (receiptPath.isEmpty()) {
        return result;
    }
    const auto receiptFile = fileInside(root, receiptPath);
    const auto receipt = load(receiptFile);
    require(receipt.value("schema") == "drone_agricole.final_reception.v2.1" &&
            receipt.value("reference_sha256") == authority.reference &&
            receipt.value("candidate_id") == authority.candidate &&
            receipt.value("authority_sha256") == authority.hashes, "Reçu final incompatible avec le gel");
    const auto native = fileInside(root, receipt.value("native").toString());
    const auto nativeSha = fileDigest(native);
    const auto nativeLocation = relative(root, native);
    require(receipt.value("native_sha256") == nativeSha && QFileInfo(native).suffix().compare("FCStd", Qt::CaseInsensitive) == 0 &&
            (nativeLocation.startsWith(".runtime/") || nativeLocation.startsWith("results/")) &&
            !authority.sources.contains(nativeLocation) &&
            !std::any_of(authority.sources.begin(), authority.sources.end(),
                [&](const auto &sha) { return sha == nativeSha; }), "Le natif doit être une copie intégrée distincte");

    const auto terminal = fileInside(root, receipt.value("l4_terminal").toString());
    require(QFileInfo(terminal).fileName() == "t0_run_manifest.json" &&
            receipt.value("l4_terminal_sha256") == fileDigest(terminal), "Preuve L4 divergente");
    const auto dir = QFileInfo(terminal).absoluteDir();
    const auto evidence = verifyEvidence(dir, "L4");
    const auto campaign = evidence.value("campaign").toObject();
    const auto artifacts = evidence.value("artifacts").toObject();
    const auto caseId = identifier(receipt.value("l4_case"));
    const auto name = "cases/" + caseId + ".json";
    const auto report = checked(dir, name, artifacts.value(name));
    const auto lockPath = receipt.value("l4_lock").toString();
    const auto lockFile = fileInside(root, lockPath);
    const auto fingerprints = report.value("fingerprints").toObject();
    const auto summary = campaign.value("cases").toObject().value(caseId).toObject();
    require(summary.value("report") == name && summary.value("sha256") == artifacts.value(name) &&
            report.value("case_id") == caseId && report.value("candidate_sha256") == nativeSha &&
            report.value("finalized") == true &&
            report.value("validation_report").toObject().value("candidate_id") == authority.candidate &&
            fingerprints == campaign.value("fingerprints") &&
            fingerprints.value("reference_sha256") == fileDigest(lockFile), "Rapport L4 hors candidat ou gel");
    const auto locked = load(lockFile).value("files").toObject();
    for (const auto &path : {go3a + "GO3A_REQUIREMENTS.yaml", go3a + "GO3A_SYSTEM_MODEL.json"}) {
        bool matched = false;
        for (const auto &entry : locked) {
            const auto file = entry.toObject();
            matched |= file.value("path") == path && file.value("sha256") == authority.hashes.value(path);
        }
        require(matched, "Autorité GO3A absente du gel L4 : " + path);
    }

    bool failure = report.value("verdict") == "FAIL" || campaign.value("verdict") == "L4_FAIL";
    QJsonObject observed;
    for (const auto &entry : report.value("findings").toArray()) {
        const auto finding = entry.toObject();
        const auto id = finding.value("l0").toObject().value("requirement_id").toString();
        const auto status = finding.value("status").toString();
        require(statuses.contains(status), "État L4 inconnu : " + status);
        failure |= status == "FAIL";
        if (authority.gaps.contains(id)) {
            auto states = observed.value(id).toArray();
            states.append(status);
            observed.insert(id, states);
        }
    }
    const auto observationName = "cases/" + caseId + "-native-observation.json";
    const auto observation = artifacts.contains(observationName)
        ? checked(dir, observationName, artifacts.value(observationName)).value("native_evidence").toObject() : QJsonObject{};
    const bool freshNative = observation.value("repeat_exact") == true && observation.value("sources_unchanged") == true &&
        observation.value("copies_unchanged") == true && observation.value("native_sha256") == nativeSha &&
        report.value("native_sha256") == nativeSha;
    // L4 labels come from its case definition. They cannot establish that the
    // case actually measures the frozen GO3A criteria. No approved mapping
    // from those criteria to executable acceptance checks exists for H-01.
    result.insert("reason", failure ? "CANDIDATE_REJECTED" :
        freshNative ? "APPROVED_ACCEPTANCE_MAPPING_REQUIRED" : "MANDATORY_EVIDENCE_INCOMPLETE");
    result.insert("candidate_state", failure ? "CANDIDATE_REJECTED" : "CANDIDATE_CONDITIONAL");
    result.insert("observed_l4_statuses", observed);
    result.insert("receipt_sha256", fileDigest(receiptFile));
    result.insert("native_sha256", nativeSha);
    result.insert("l4_report_sha256", artifacts.value(name));
    return result;
}

} // namespace

QJsonObject preflight(const QDir &root, const QDir &output, const QString &mode,
                      const QString &planPath, const QString &receiptPath, int steps)
{
    const auto authority = loadAuthority(root);
    QJsonObject result{{"schema", "drone_agricole.preflight.v2.1"}, {"mode", mode},
        {"candidate_id", authority.candidate}, {"authority_sha256", authority.hashes},
        {"reference_sha256", authority.reference}, {"historical", authority.history},
        {"source_files_verified", authority.sources.size()}, {"evidence_gap", authority.gaps}};
    if (mode == "historical") {
        result.insert("verdict", authority.history.value("verdict"));
    } else if (mode == "final") {
        const auto reception = finalReception(root, authority, receiptPath);
        for (auto it = reception.begin(); it != reception.end(); ++it) {
            result.insert(it.key(), it.value());
        }
    } else {
        const auto path = fileInside(root, planPath);
        const auto bytes = read(path);
        const auto plan = parse(bytes, path);
        require(plan.value("schema") == "drone_agricole.exploration_request.v2.1" &&
                plan.value("candidate_id") == authority.candidate &&
                plan.value("reference_sha256") == authority.reference, "Demande hors périmètre du gel");
        const auto blocks = explorationBlocks(output, plan);
        result.insert("plan_sha256", digest(bytes));
        result.insert("blocks", blocks);
        result.insert("trial_findings", plan.value("trial_findings"));
        result.insert("verdict", blocks.isEmpty() ? "EXPLORATION_ALLOWED" : "EXPLORATION_BLOCKED");
        result.insert("budget", QJsonObject{{"variant_limit", authority.budget}, {"variants_built", 0}});
        const auto checkpoint = output.filePath("preflight.json");
        QJsonArray queue;
        if (QFileInfo::exists(checkpoint)) {
            const auto previous = load(checkpoint);
            queue = previous.value("queue").toArray();
            auto identity = previous;
            identity.remove("queue");
            identity.remove("campaign_state");
            require(identity == result, "Reprise refusée : demande, gel ou contraintes modifiés");
        }
        const auto ids = authority.gaps.keys();
        require(queue.size() <= ids.size(), "File d'activités incohérente");
        for (qsizetype i = 0; blocks.isEmpty() && i < ids.size(); ++i) {
            const auto activity = authority.gaps.value(ids[i]).toObject();
            const QJsonObject row{{"requirement_id", ids[i]}, {"action", activity.value("next_experiment")},
                {"state", activity.value("required_before_trial").toBool() ? "RESEARCH_REQUIRED" : "READY_ON_COPY"},
                {"status", activity.value("status")}, {"budget_spent", 0}};
            if (i < queue.size()) {
                require(queue.at(i) == row, "Point de reprise altéré");
            } else if (steps != 0) {
                queue.append(row);
                if (steps > 0) {
                    --steps;
                }
            }
        }
        result.insert("queue", queue);
        result.insert("campaign_state", !blocks.isEmpty() ? "BLOCKED" : queue.size() < ids.size() ? "PAUSED" : "PLANNED");
    }
    verifyFiles(root, authority.sources);
    verifyFiles(root, authority.hashes);
    return result;
}

} // namespace convergence
