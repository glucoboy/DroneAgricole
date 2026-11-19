#include "Campaign.hpp"

#include "AdmissionScope.hpp"
#include "Evidence.hpp"
#include "Files.hpp"
#include "ProcessBackend.hpp"
#include "V3Domain.hpp"
#include "V3Search.hpp"

#include <QCoreApplication>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QProcess>
#include <QSet>
#include <QStandardPaths>
#include <algorithm>
#include <cmath>
#include <limits>

namespace convergence {
namespace {

const QString measurer = "convergence_manager/native/v3_cross_measure.py";
const QString crossReplay = "convergence_manager/tests/replay_v3_b2.py";

QString executable(const QString &value)
{
    const QFileInfo file(value);
    const auto path = file.isFile() ? file.canonicalFilePath() : QStandardPaths::findExecutable(value);
    require(!path.isEmpty(), "Outil de convergence V3 absent : " + value);
    return path;
}

QJsonObject invoke(const QDir &root, const QString &tool, const QStringList &args, int limit)
{
    QProcess process;
    process.setWorkingDirectory(root.absolutePath());
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert("QT_QPA_PLATFORM", "offscreen");
    env.insert("PYTHONUTF8", "1");
    process.setProcessEnvironment(env);
    const auto hash = fileDigest(tool);
    QElapsedTimer elapsed;
    elapsed.start();
    process.start(tool, args);
    require(process.waitForStarted(5000), "Outil V3 indisponible : " + tool);
    const bool complete = process.state() == QProcess::NotRunning || process.waitForFinished(limit);
    if (!complete) {
        process.kill();
        process.waitForFinished(5000);
    }
    require(fileDigest(tool) == hash, "Outil V3 modifié pendant une mesure : " + tool);
    return {{"tool", tool}, {"tool_sha256", hash}, {"argv", QJsonArray::fromStringList(args)},
            {"exit_code", complete && process.exitStatus() == QProcess::NormalExit ? process.exitCode() : -1},
            {"duration_ms", elapsed.elapsed()}, {"stdout", QString::fromUtf8(process.readAllStandardOutput().right(4096))},
            {"stderr", QString::fromUtf8(process.readAllStandardError().right(4096))}};
}

QString inputPath(const QDir &root, const QString &path)
{
    const auto resolved = fileInside(root, path);
    require(resolved == QDir::cleanPath(QDir::fromNativeSeparators(root.absoluteFilePath(path))) &&
            !hasRedirectedComponent(root, resolved),
            "Entrée V3 redirigée : " + path);
    return resolved;
}

void copyNative(const QDir &root, const QJsonObject &profile, const QDir &target)
{
    const QDir origin(root.filePath(profile.value("source").toString()));
    const auto dependencies = profile.value("dependencies").toObject();
    require(!dependencies.isEmpty() && target.mkpath(".") && target.canonicalPath() == target.absolutePath(),
            "Fermeture native vide ou copie privée inaccessible");
    for (auto it = dependencies.begin(); it != dependencies.end(); ++it) {
        const auto source = inputPath(root, relative(root, origin.filePath(it.key())));
        const auto bytes = read(source);
        require(digest(bytes) == it.value(), "Dépendance native divergente : " + it.key());
        const auto path = target.filePath(it.key());
        require(!QFileInfo::exists(path) && target.mkpath(QFileInfo(it.key()).path()), "Destination XLink déjà utilisée");
        require(write(path, bytes) == it.value() && QFile::setPermissions(path, QFileDevice::ReadOwner | QFileDevice::ReadUser),
                "Échec de la préparation XLink en lecture seule");
    }
}

int integer(const QJsonValue &value, int low, int high, const QString &name)
{
    const auto number = value.toInt(low-1);
    require(value.isDouble() && value.toDouble() == number && number >= low && number <= high,
            "Valeur entière V3 hors borne : " + name);
    return number;
}

void requireSubset(const QJsonObject &inner, const QJsonObject &outer, const QString &label, bool strict)
{
    const auto lower = inner.value("min").toArray(), upper = inner.value("max").toArray();
    const auto baseLower = outer.value("min").toArray(), baseUpper = outer.value("max").toArray();
    require(lower.size() == 3 && upper.size() == 3 && baseLower.size() == 3 && baseUpper.size() == 3,
            "Boîte V3 sans trois axes : " + label);
    bool smaller = false;
    for (int axis = 0; axis < 3; ++axis) {
        require(lower.at(axis).isDouble() && upper.at(axis).isDouble(), "Axe V3 non numérique : " + label);
        const auto a = lower.at(axis).toDouble(), b = upper.at(axis).toDouble();
        const auto first = baseLower.at(axis).toDouble(), last = baseUpper.at(axis).toDouble();
        require(a <= b && a >= first && b <= last, "Zone V3 hors autorité : " + label);
        smaller |= a > first || b < last;
    }
    require(!strict || smaller, "T2 doit modifier strictement la boîte autorisée");
}

QJsonObject verifyProblem(const QDir &root, const QJsonObject &problem, const QJsonObject &domain,
                          const QString &baseProblemPath, const QString &obsSha, const QJsonObject &profile)
{
    const auto phase = problem.value("phase").toString();
    require(problem.value("schema") == "v3.problem_spec/1" && QStringList{"T1", "T2", "T3"}.contains(phase),
            "Problème de convergence V3 incompatible");
    const auto dependencies = profile.value("dependencies").toObject();
    require(problem.value("observation_sha256") == obsSha &&
            problem.value("model_sha256") == dependencies.value(profile.value("entry").toString()),
            "L3 et la référence XLink divergent");
    const auto placement = domain.value("placement").toObject();
    const QJsonObject allowed{{"min", placement.value("translation_min_mm")}, {"max", placement.value("translation_max_mm")}};
    const auto narrowing = problem.value("narrowing").toObject();
    require(narrowing.keys() == QStringList{"translation_mm"}, "Restrictions de support hors contrat de cette campagne");
    const auto used = narrowing.value("translation_mm").toObject();
    requireSubset(used, allowed, "domaine scellé", false);
    if (phase == "T2") {
        const auto baseline = inputPath(root, baseProblemPath);
        require(fileDigest(baseline) == problem.value("base_problem_sha256"), "Référence T1 divergente");
        auto previous = parseUniqueObject(read(baseline), baseline);
        require(previous.value("phase") == "T1", "Référence de perturbation incompatible");
        requireSubset(used, previous.value("narrowing").toObject().value("translation_mm").toObject(), "restriction T2", true);
        auto current = problem;
        for (const auto &field : {"phase", "narrowing", "base_problem_sha256"}) {
            previous.remove(field);
            current.remove(field);
        }
        require(current == previous, "T2 doit conserver modèles, objectifs, graine et budgets de T1");
    } else {
        require(baseProblemPath.isEmpty() && !problem.contains("base_problem_sha256"), "Parent T1 superflu");
    }
    return used;
}

struct Candidate {
    QString id;
    QJsonObject measures;
    QString proof;
    QString sha;
    QJsonObject native;
    QJsonObject values;
};

double value(const Candidate &candidate, const QJsonObject &metric)
{
    const auto measured = candidate.measures.value(metric.value("metric").toString()).toDouble();
    return metric.value("direction") == "MIN" ? measured : -measured;
}

bool dominates(const Candidate &left, const Candidate &right, const QJsonArray &criteria)
{
    bool strictlyBetter = false;
    for (const auto &item : criteria) {
        const auto metric = item.toObject();
        const auto a = value(left, metric), b = value(right, metric);
        if (a > b)
            return false;
        strictlyBetter |= a < b;
    }
    return strictlyBetter;
}

QJsonObject metrics(const QJsonObject &measurement, const QJsonObject &assessment)
{
    const auto routes = measurement.value("routes").toObject();
    require(!routes.isEmpty(), "Longueur native requise pour le classement");
    double length = 0.0;
    for (const auto &route : routes) {
        const auto measured = route.toObject().value("length_mm");
        require(measured.isDouble() && measured.toDouble() > 0, "Longueur native invalide");
        length += measured.toDouble();
    }
    const auto measuredServices = assessment.value("services").toArray();
    double minimumGap = std::numeric_limits<double>::infinity();
    for (const auto &entry : measuredServices) {
        const auto data = entry.toObject();
        const auto distance = data.value("gap_mm");
        require(distance.isDouble() && std::isfinite(distance.toDouble()) && distance.toDouble() >= 0.0,
                "Dégagement natif invalide");
        minimumGap = std::min(minimumGap, distance.toDouble());
    }
    require(std::isfinite(minimumGap), "Dégagement de service requis pour le classement");
    return {{"route_length_mm", length}, {"service_clearance_mm", minimumGap},
            {"support_count", measurement.value("supports").toObject().size()}};
}

QJsonObject applicableServices(const QJsonObject &measurement, const QJsonObject &plan)
{
    QSet<QString> actions;
    for (const auto &row : plan.value("actions").toArray())
        actions.insert(row.toObject().value("id").toString());
    QJsonArray applicable;
    for (const auto &entry : measurement.value("service").toArray()) {
        const auto row = entry.toObject();
        const auto requirement = row.value("required_action");
        if (requirement.isNull() || actions.contains(requirement.toString()))
            applicable.append(row);
    }
    return {{"services", applicable}};
}

QString jsonDigest(const QJsonValue &value)
{
    return digest(QJsonDocument(value.toObject()).toJson(QJsonDocument::Compact));
}

QString chooseFamily(const QStringList &pending, const QJsonArray &diagnoses, const QJsonObject &baseline,
                     const QJsonObject &domain)
{
    if (!pending.contains("DETOUR_POSITIVE") || !pending.contains("DETOUR_NEGATIVE"))
        return pending.first();
    const auto axis = domain.value("route").toObject().value("start_mm").toArray().at(1).toDouble();
    const auto occurrences = baseline.value("occurrences").toObject();
    QSet<QString> considered;
    double offset = 0.0;
    for (const auto &diagnosis : diagnoses) {
        for (const auto &issue : diagnosis.toObject().value("blocking_issues").toArray()) {
            const auto key = issue.toString();
            if (!key.startsWith("route/") || considered.contains(key))
                continue;
            considered.insert(key);
            const auto bounds = occurrences.value(key.mid(6)).toObject().value("bounds_mm").toArray();
            if (bounds.size() == 2)
                offset += (bounds.at(0).toArray().at(1).toDouble() + bounds.at(1).toArray().at(1).toDouble())/2 - axis;
        }
    }
    return offset > 0 ? "DETOUR_NEGATIVE" : pending.first();
}

} // namespace

QJsonObject Campaign::runV3(const QDir &root, const QDir &output, const QString &problemPath,
                            const QString &observationPath, const QString &baseProblemPath,
                            const QString &freecadArg, const QString &pythonArg, const QString &t0Arg)
{
    const auto freecad = executable(freecadArg), python = executable(pythonArg), t0 = executable(t0Arg);
    const auto problemFile = inputPath(root, problemPath), observationFile = inputPath(root, observationPath);
    const auto problemBytes = read(problemFile), observationBytes = read(observationFile);
    const auto bytesHash = digest(problemBytes), obsHash = digest(observationBytes);
    const auto problem = parseUniqueObject(problemBytes, problemFile);
    const auto domainSha = problem.value("domain_sha256").toString();
    const auto domain = loadV3Domain(root, domainSha);
    const auto profileSha = domain.value("profile_sha256").toString();
    const auto profile = loadMutationProfile(root, profileSha);
    const auto narrowed = verifyProblem(root, problem, domain, baseProblemPath, obsHash, profile);
    const auto budget = problem.value("budget").toObject();
    const auto proposalsBudget = integer(budget.value("max_proposals"), 3, 512, "max_proposals");
    const auto nativeBudget = integer(budget.value("max_native"), 1, 16, "max_native");
    require(nativeBudget <= proposalsBudget, "Budget natif supérieur au budget de propositions");
    const auto seed = integer(problem.value("seed"), 0, 2147483647, "seed");
    const auto objectives = problem.value("objectives").toArray();
    require(!objectives.isEmpty(), "Objectifs mesurables requis");
    const QMap<QString, QString> directions{{"route_length_mm", "MIN"}, {"service_clearance_mm", "MAX"}, {"support_count", "MIN"}};
    QSet<QString> metricNames;
    for (const auto &objective : objectives) {
        const auto row = objective.toObject();
        const auto name = row.value("metric").toString();
        require(!metricNames.contains(name) && directions.contains(name) && row.value("direction") == directions.value(name),
                "Objectif V3 inconnu, répété ou inversé");
        metricNames.insert(name);
    }

    QMap<QString, QString> published;
    const auto tracePath = output.filePath("candidate_trace.jsonl");
    QFile trace(tracePath);
    require(trace.open(QIODevice::WriteOnly | QIODevice::NewOnly), "Trace de convergence V3 inaccessible");
    int sequence = 0;
    const auto record = [&](const QString &stage, const QJsonObject &detail = {}) {
        const QJsonObject row{{"stage", stage}, {"sequence", ++sequence}, {"detail", detail}};
        const auto line = QJsonDocument(row).toJson(QJsonDocument::Compact) + '\n';
        require(trace.write(line) == line.size() && trace.flush(), "Écriture de la trace de convergence V3 impossible");
    };
    const auto save = [&](const QString &name, const QJsonObject &object) {
        published.insert(name, write(output.filePath(name), object));
    };
    const auto add = [&](const QString &path) {
        const auto name = relative(output, path);
        published.insert(name, fileDigest(path));
    };

    const auto dependencies = profile.value("dependencies").toObject();
    const auto observed = parseUniqueObject(observationBytes, observationFile);
    const auto workerPath = inputPath(root, measurer), replayPath = inputPath(root, crossReplay);
    const auto profilePath = inputPath(root, v3BaseProfilePath(domain));
    require(fileDigest(profilePath) == profileSha, "Profil de base divergent du domaine");
    const auto workerSha = fileDigest(workerPath), replaySha = fileDigest(replayPath);
    require(observed.value("status") == "MEASURED" && observed.value("schema") == "v3.cross_measurement/1" &&
            observed.value("worker_sha256") == workerSha && observed.value("inputs_sha256") == dependencies &&
            observed.value("source_sha256") == dependencies && observed.value("profile_sha256") == profileSha &&
            observed.value("documents_closed") == true, "Observation de départ hors contrat V3");
    const QString baselineName = "baseline.json";
    const QDir baselineCopy(output.filePath("baseline-copy"));
    record("PRECHECK", {{"domain_sha256", domainSha}, {"problem_sha256", bytesHash},
                         {"budget", budget}, {"seed", seed}, {"narrowing", narrowed}});
    copyNative(root, profile, baselineCopy);
    const auto baselineCommand = invoke(root, freecad, {"-B", workerPath, "--root", baselineCopy.absolutePath(),
        "--profile", profilePath, "--output", output.filePath(baselineName)}, 120000);
    save("baseline-invocation.json", baselineCommand);
    require(baselineCommand.value("exit_code") == 0, "Réouverture de référence V3 non finalisée");
    const auto baseline = load(output.filePath(baselineName));
    require(baseline.value("status") == "MEASURED" && baseline.value("worker_sha256") == workerSha &&
            baseline.value("inputs_sha256") == dependencies && baseline.value("documents_closed") == true,
            "Réouverture de référence V3 incohérente");
    for (const auto &property : {"ports", "service", "occurrences", "routes", "supports", "pairs", "parent_matrices"})
        require(baseline.value(property) == observed.value(property), QString("Observation L3 divergente : ") + property);
    add(output.filePath(baselineName));

    const auto freecadSha = fileDigest(freecad), pythonSha = fileDigest(python), t0Sha = fileDigest(t0);
    QJsonArray evidenceInputs;
    const auto bind = [&](const QString &path, const QString &sha, int id) {
        evidenceInputs.append(QJsonObject{{"input_id", "v3-c-input-" + QString::number(id)}, {"kind", "other"},
            {"reference", QJsonObject{{"path", relative(root, path)}}}, {"checksums", QJsonObject{{"sha256", sha}}}});
    };
    bind(problemFile, bytesHash, 1);
    bind(observationFile, obsHash, 2);
    bind(profilePath, profileSha, 3);
    architecture_decision::Evidence evidence(output.absolutePath(), evidenceInputs, problem,
        {{"binary_sha256", fileDigest(QCoreApplication::applicationFilePath())}, {"domain_sha256", domainSha},
         {"freecad_sha256", freecadSha}, {"t0_sha256", t0Sha}, {"cross_worker_sha256", workerSha},
         {"cross_replay_sha256", replaySha}, {"python_sha256", pythonSha}},
        {"v3_c", "convergence_core", "xlink", "SYNTHETIC_BENCH", "Exploration V3 ouverte", "Campagne V3 finalisée"});

    QVector<Candidate> candidates;
    QJsonArray transitions, coverage, diagnoses;
    QSet<QString> signatures;
    int proposals = 0, builds = 0;
    QString previousFamily;
    bool nativeBudgetReached = false;
    QStringList pendingFamilies{"DIRECT", "DETOUR_POSITIVE", "DETOUR_NEGATIVE"};
    while (!pendingFamilies.isEmpty() && proposals < proposalsBudget) {
        auto restricted = problem;
        auto familyBudget = budget;
        const int proposalsPerFamily = (proposalsBudget-proposals+pendingFamilies.size()-1) / pendingFamilies.size();
        familyBudget.insert("max_proposals", proposalsPerFamily);
        restricted.insert("budget", familyBudget);
        const auto family = chooseFamily(pendingFamilies, diagnoses, baseline, domain);
        const auto generated = generateV3Proposals(domain, baseline, restricted, seed, family);
        pendingFamilies.removeAll(family);
        const auto buildCeiling = builds + (nativeBudget-builds+pendingFamilies.size()) / (pendingFamilies.size()+1);
        if (!previousFamily.isEmpty()) {
            const QJsonObject move{{"from", previousFamily}, {"to", family},
                {"cause", candidates.isEmpty() ? "CONSTRAINTS_ACTIVE" : "PARETO_ALTERNATIVE"}, {"diagnoses", diagnoses}};
            transitions.append(move);
            record("CHANGE_FAMILY", move);
        }
        previousFamily = family;
        diagnoses = {};
        coverage.append(QJsonObject{{"family", family}, {"coverage", generated.value("coverage")}, {"status", generated.value("status")}});
        if (generated.value("proposals").toArray().isEmpty()) {
            const QJsonObject failure{{"family", family}, {"blocking_issues", generated.value("unknowns")},
                                      {"reason", "CONSTRAINT_UNKNOWN"}};
            diagnoses.append(failure);
            record("DIAGNOSE", failure);
        }
        for (const auto &entry : generated.value("proposals").toArray()) {
            if (proposals == proposalsBudget)
                break;
            const auto item = entry.toObject();
            const auto values = item.value("values").toObject();
            const auto screen = item.value("screen").toObject();
            const auto point = (values.isEmpty() ? item.value("sample_translation_mm") : values.value("translation_mm")).toArray();
            const auto signature = values.isEmpty() ? jsonDigest(QJsonObject{{"family", family}, {"point", point}})
                                                    : item.value("signature").toString();
            require(!signature.isEmpty(), "Proposition V3 sans signature géométrique");
            if (signatures.contains(signature))
                continue;
            signatures.insert(signature);
            const auto id = QString("v3-c-%1").arg(++proposals, 3, 10, QChar('0'));
            requireSubset({{"min", point}, {"max", point}}, narrowed, "proposition L3", false);
            record("GENERATE", {{"candidate", id}, {"family", family}, {"translation_mm", point}, {"values", values},
                                {"geometry_signature", signature}, {"value_sha256", jsonDigest(values)}});
            record("SCREEN", {{"candidate", id}, {"family", family}, {"screen", screen}});
            if (screen.value("status") != "ELIGIBLE") {
                const QJsonObject failure{{"candidate", id}, {"reason", screen.value("status")},
                                          {"blocking_issues", screen.value("blocking_issues")}};
                diagnoses.append(failure);
                record("DIAGNOSE", failure);
                continue;
            }
            if (builds >= buildCeiling) {
                nativeBudgetReached |= builds >= nativeBudget;
                const QJsonObject failure{{"candidate", id}, {"reason", builds >= nativeBudget ?
                    "SEARCH_BUDGET_EXHAUSTED" : "NATIVE_BUDGET_RESERVED_FOR_OTHER_FAMILIES"}};
                diagnoses.append(failure);
                record("DIAGNOSE", failure);
                continue;
            }
            const QDir trial(output.filePath("candidates/" + id));
            const QDir sandbox(trial.filePath("input")), transaction(trial.filePath("construction"));
            const auto plan = makeV3Plan(id, domainSha, values);
            copyNative(root, profile, sandbox);
            require(transaction.mkpath("."), "Dossier de transaction V3 inaccessible");
            const auto planBytes = QJsonDocument(plan).toJson(QJsonDocument::Compact);
            const auto proposalSha = write(trial.filePath("proposal.json"), planBytes);
            add(trial.filePath("proposal.json"));
            QElapsedTimer buildTime;
            buildTime.start();
            ++builds;
            record("BUILD", {{"candidate", id}, {"proposal_sha256", proposalSha}, {"native_budget_used", builds}});
            const auto native = ProcessBackend::buildV3(root, sandbox, transaction, planBytes, plan, freecad, t0);
            const auto nativeDuration = buildTime.elapsed();
            if (native.value("construction_result") != "PASS") {
                const QJsonObject failure{{"candidate", id}, {"reason", native.value("reason")},
                                          {"status", native.value("status")}, {"duration_ms", nativeDuration}};
                diagnoses.append(failure);
                record("DIAGNOSE", failure);
                const auto refusal = transaction.filePath("refusal.json");
                if (QFileInfo::exists(refusal))
                    add(refusal);
                else
                    add(transaction.filePath("transaction/campaign.json"));
                continue;
            }
            const auto receipt = transaction.filePath("transaction/campaign.json");
            require(native.value("plan_sha256") == proposalSha, "Reçu de construction V3 hors proposition");
            const auto nativeSha = fileDigest(receipt);
            add(receipt);
            record("REOPEN", {{"candidate", id}, {"native_sha256", native.value("native_sha256")},
                               {"receipt_sha256", nativeSha}, {"duration_ms", nativeDuration}});
            const auto crossInput = trial.filePath("replay.json");
            write(crossInput, QJsonDocument(QJsonArray{QJsonObject{{"plan_id", id}, {"receipt", relative(root, receipt)},
                {"sha256", nativeSha}}}).toJson(QJsonDocument::Indented));
            const auto crossArea = trial.filePath("cross");
            const auto validator = invoke(root, python, {"-B", replayPath, "--replay", crossInput, "--freecad", freecad,
                                                          "--t0", t0, "--output", crossArea}, 200000);
            const auto crossCommand = trial.filePath("cross-invocation.json");
            write(crossCommand, validator);
            add(crossCommand);
            const auto crossResult = QDir(crossArea).filePath(id + "/candidate-result.json");
            QJsonObject checked;
            if (QFileInfo::exists(crossResult)) {
                checked = load(crossResult);
                add(crossResult);
            }
            record("VALIDATE", {{"candidate", id}, {"native", native.value("status")},
                                 {"cross", checked.value("final_verdict")}, {"exit_code", validator.value("exit_code")},
                                 {"duration_ms", validator.value("duration_ms")}});
            if (validator.value("exit_code") != 0 || checked.value("final_verdict") != "PASS") {
                const QJsonObject failure{{"candidate", id}, {"reason", checked.isEmpty() ? "NATIVE_FAILURE" : "NATIVE_CONSTRAINT"},
                                          {"blocking_issues", checked.value("blocking_issues")},
                                          {"independent_disagreements", checked.value("independent_disagreements")}};
                diagnoses.append(failure);
                record("DIAGNOSE", failure);
                continue;
            }
            require(native.value("status") == "PASS" && native.value("source_integrity").toObject().value("status") == "PASS" &&
                    checked.value("schema") == "v3.candidate_result/1" && checked.value("candidate_id") == id &&
                    checked.value("candidate_state") == "CANDIDATE" && checked.value("proposal_sha256") == proposalSha &&
                    checked.value("native_receipt").toObject().value("sha256") == nativeSha &&
                    checked.value("blocking_issues").toArray().isEmpty() && checked.value("independent_disagreements").toArray().isEmpty(),
                    "Contre-validation V3 incohérente");
            const auto measureRecord = checked.value("measurements").toObject();
            const auto path = inputPath(root, measureRecord.value("path").toString());
            require(fileDigest(path) == measureRecord.value("sha256"), "Contre-mesure modifiée");
            add(path);
            const auto measurement = load(path);
            const auto expanded = load(QFileInfo(receipt).absolutePath() + "/expanded-plan.json");
            candidates.append({id, metrics(measurement, applicableServices(measurement, expanded)), relative(output, crossResult),
                               fileDigest(crossResult), native.value("native_sha256").toObject(), values});
        }
        if (proposals >= proposalsBudget)
            break;
    }

    record("RANK", {{"feasible", candidates.size()}, {"objectives", objectives}});
    QJsonArray front, measured;
    QVector<Candidate> pareto;
    for (const auto &candidate : candidates) {
        const QJsonObject row{{"candidate", candidate.id}, {"metrics", candidate.measures}};
        measured.append(row);
        if (std::none_of(candidates.begin(), candidates.end(), [&](const auto &other) { return dominates(other, candidate, objectives); })) {
            front.append(row);
            pareto.append(candidate);
        }
    }
    std::sort(pareto.begin(), pareto.end(), [&](const auto &left, const auto &right) {
        for (const auto &item : objectives) {
            const auto metric = item.toObject();
            const auto a = value(left, metric), b = value(right, metric);
            if (a != b)
                return a < b;
        }
        return left.id < right.id;
    });
    QJsonObject retained;
    if (!pareto.isEmpty()) {
        const auto &best = pareto.first();
        retained = {{"candidate_id", best.id}, {"values", best.values}, {"metrics", best.measures},
                    {"result", best.proof}, {"result_sha256", best.sha}, {"native_sha256", best.native}};
        const QDir native(output.filePath("candidates/" + best.id + "/construction/transaction/cad"));
        for (auto it = best.native.begin(); it != best.native.end(); ++it) {
            const auto path = native.filePath(it.key());
            require(fileDigest(path) == it.value(), "Natif retenu modifié depuis validation");
            add(path);
        }
        record("RETAIN", retained);
    }
    save("family_transitions.json", {{"transitions", transitions}});
    save("pareto.json", {{"front", front}, {"admissible", measured}, {"tie_break", "OBJECTIVE_ORDER_THEN_CANDIDATE_ID"}});
    trace.close();
    add(tracePath);
    const QDir source(root.filePath(profile.value("source").toString()));
    for (auto it = dependencies.begin(); it != dependencies.end(); ++it)
        require(fileDigest(source.filePath(it.key())) == it.value(), "Source V3 modifiée : " + it.key());
    require(fileDigest(workerPath) == workerSha && fileDigest(replayPath) == replaySha && fileDigest(problemFile) == bytesHash &&
            fileDigest(observationFile) == obsHash && fileDigest(freecad) == freecadSha && fileDigest(t0) == t0Sha &&
            fileDigest(python) == pythonSha, "Gel V3 modifié pendant l’exploration");
    const auto stopped = retained.isEmpty() ? nativeBudgetReached || proposals >= proposalsBudget ? "SEARCH_BUDGET_EXHAUSTED" :
        proposals == 0 ? "CONSTRAINT_UNKNOWN" : "NO_FEASIBLE_CANDIDATE_FOUND" : "RANKED_FEASIBLE_CANDIDATES";
    const QJsonObject campaign{{"schema", "v3.convergence_campaign/1"}, {"finalized", true}, {"scope", "SYNTHETIC_BENCH"},
        {"phase", problem.value("phase")}, {"domain_sha256", domainSha}, {"seed", seed}, {"budget", budget},
        {"proposals", proposals}, {"native_attempts", builds}, {"qualified_candidates", candidates.size()}, {"coverage", coverage},
        {"reason", stopped}, {"verdict", retained.isEmpty() ? "V3_C_CONDITIONAL" : "V3_C_PASS"}, {"retained", retained}};
    save("campaign.json", campaign);
    evidence.finalize(campaign, published);
    verifyEvidence(output, "V3_C");
    const auto t0Receipt = invoke(root, t0, {"validate", output.absolutePath(), root.absolutePath()}, 60000);
    write(output.filePath("t0-crosscheck.json"), t0Receipt);
    require(t0Receipt.value("exit_code") == 0, "Validation T0 de campagne V3 refusée");
    return campaign;
}

} // namespace convergence
