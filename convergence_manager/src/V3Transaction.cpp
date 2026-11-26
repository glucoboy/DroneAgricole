#include "V3Transaction.hpp"

#include "AdmissionScope.hpp"
#include "Evidence.hpp"
#include "Files.hpp"
#include "Graph.hpp"
#include "ProcessBackend.hpp"
#include "V3Domain.hpp"

#include <QCoreApplication>
#include <QDateTime>
#include <QFileInfo>
#include <QJsonArray>
#include <QProcess>
#include <QSet>
#include <QTemporaryDir>
#include <filesystem>

namespace convergence {
namespace {

const QString planSchema = "v3.mutation_plan/1";
const QString worker = "convergence_manager/native/v3_mutate.py";
const QString verifier = "convergence_manager/native/v3_verify.py";
const QSet<QString> implemented{"REPOSITION_DEVICE", "REROUTE_HARNESS", "RELOCATE_SUPPORT", "CREATE_SUPPORT"};

QString exactFile(const QDir &root, const QString &name)
{
    require(QDir::isRelativePath(name) && QDir::cleanPath(name) == name &&
            !name.contains('\\') && !name.contains(':'), "Chemin V3 non canonique : " + name);
    const auto absolute = root.filePath(name);
    const auto canonical = fileInside(root, name);
    require(canonical == absolute && !hasRedirectedComponent(root, absolute) &&
            std::filesystem::hard_link_count(QFileInfo(absolute).filesystemFilePath()) == 1,
            "Fichier V3 partagé ou redirigé : " + name);
    return canonical;
}

QJsonObject hashes(const QDir &root, const QJsonObject &paths)
{
    QJsonObject measured;
    for (auto it = paths.begin(); it != paths.end(); ++it)
        measured.insert(it.key(), fileDigest(exactFile(root, it.key())));
    return measured;
}

void copyClosure(const QDir &from, const QDir &to, const QJsonObject &expected)
{
    require(to.mkpath(".") && to.canonicalPath() == to.absolutePath(), "Copie XLink inaccessible");
    for (auto it = expected.begin(); it != expected.end(); ++it) {
        const auto bytes = read(exactFile(from, it.key()));
        require(digest(bytes) == it.value(), "Fichier de départ divergent : " + it.key());
        require(to.mkpath(QFileInfo(it.key()).path()), "Dossier XLink inaccessible");
        const auto destination = to.filePath(it.key());
        require(!QFileInfo::exists(destination) && !hasRedirectedComponent(to, destination),
                "Destination XLink existante ou redirigée : " + it.key());
        write(destination, bytes);
    }
    require(hashes(to, expected) == expected, "Copie XLink divergente");
}

QString appendJournal(const QDir &stage, QJsonObject &journal, const QString &event,
                      const QJsonObject &detail = {})
{
    auto events = journal.value("events").toArray();
    events.append(QJsonObject{{"event", event}, {"when_utc", QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},
                              {"detail", detail}});
    journal.insert("events", events);
    return write(stage.filePath("journal.json"), journal);
}

QJsonObject call(const QDir &root, const QDir &stage, QJsonObject &journal, const QString &name,
                 const QString &program, const QStringList &arguments, int timeout)
{
    QJsonObject record{{"program", program}, {"program_sha256", fileDigest(program)},
                       {"argv", QJsonArray::fromStringList(arguments)}, {"stage", name}};
    appendJournal(stage, journal, "PROCESS_START", record);
    QProcess process;
    process.setWorkingDirectory(root.absolutePath());
    auto environment = QProcessEnvironment::systemEnvironment();
    environment.insert("QT_QPA_PLATFORM", "offscreen");
    environment.insert("PYTHONUTF8", "1");
    process.setProcessEnvironment(environment);
    process.start(program, arguments);
    const bool started = process.waitForStarted(5000);
    const bool timedOut = started && process.state() != QProcess::NotRunning && !process.waitForFinished(timeout);
    if (timedOut) {
        process.kill();
        process.waitForFinished(5000);
    }
    const auto diagnostics = process.readAllStandardError().right(8192);
    record.insert("exit_code", started ? process.exitCode() : -1);
    record.insert("status", !started ? "START_FAILED" : timedOut ? "TIMEOUT" :
                  process.exitStatus() != QProcess::NormalExit ? "CRASH" : "EXITED");
    record.insert("stdout", QString::fromUtf8(process.readAllStandardOutput().right(8192)));
    record.insert("stderr", QString::fromUtf8(diagnostics));
    appendJournal(stage, journal, "PROCESS_END", record);
    require(record.value("status") == "EXITED", name + " : " + record.value("status").toString());
    return record;
}

QJsonArray stringKeys(const QJsonObject &object)
{
    return QJsonArray::fromStringList(object.keys());
}

bool consistentNativeChecks(const QJsonObject &job, const QJsonObject &observation)
{
    static const QSet<QString> states{"PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN", "UNSUPPORTED", "NOT_APPLICABLE"};
    QMap<QString, QString> checks;
    for (const auto &value : observation.value("checks").toArray()) {
        const auto check = value.toObject();
        const auto id = check.value("id").toString();
        const auto status = check.value("status").toString();
        if (id.isEmpty() || checks.contains(id) || !states.contains(status))
            return false;
        checks.insert(id, status);
    }
    QSet<QString> required{"REOPEN_XLINK", "L2_TOPOLOGY", "L4_GEOMETRY", "L4_SERVICE", "L4_DYNAMIC_BEND_RADIUS"};
    for (const auto &check : job.value("mandatory_checks").toArray())
        required.insert(check.toString());
    required.remove("VERIFY_IMMUTABLE_SOURCES");
    required.remove("VALIDATE_T0");
    if (checks.contains("NATIVE_MEASUREMENT"))
        required.insert("NATIVE_MEASUREMENT");

    bool failed = false;
    bool incomplete = false;
    for (const auto &id : required) {
        if (!checks.contains(id))
            return false;
        const auto status = checks.value(id);
        failed |= status == "FAIL";
        incomplete |= status != "PASS";
    }
    const QString computed = failed ? "FAIL" : incomplete ? "INCONCLUSIVE" : "PASS";
    return observation.value("status") == computed;
}

QJsonObject inspect(const QDir &repo, const QDir &published, const QDir &working, const QDir &stage,
                    QJsonObject &journal, const QString &python, const QString &phase, QJsonObject job)
{
    job.insert("stage", phase);
    const auto jobPath = published.filePath(phase + "-job.json");
    const auto jobSha = write(jobPath, job);
    const auto report = published.filePath(phase + "-validation.json");
    const auto command = call(repo, stage, journal, phase, python,
        {"-B", exactFile(repo, verifier), "--root", working.absolutePath(), "--job", jobPath, "--output", report}, 120000);
    require(command.value("exit_code") == 0, "Réouverture indépendante non finalisée : " + phase);
    const auto observation = load(exactFile(published, phase + "-validation.json"));
    const auto dependencies = job.value("dependencies").toObject();
    require(observation.value("schema") == "v3.native_validation/1" && observation.value("finalized") == true &&
            observation.value("documents_closed") == true && observation.value("pid").toInt() > 0 &&
            observation.value("stage") == phase && observation.value("job_sha256") == jobSha &&
            observation.value("plan_id") == job.value("plan_id") && observation.value("reopened") == true &&
            observation.value("inputs_sha256") == dependencies && observation.value("open_documents") == stringKeys(dependencies) &&
            !observation.value("worker_id").toString().isEmpty() &&
            consistentNativeChecks(job, observation) &&
            hashes(working, dependencies) == dependencies, "Réouverture indépendante incohérente : " + phase);
    return observation;
}

QJsonArray recover(const QDir &output, const QString &planSha)
{
    QJsonArray abandoned;
    const auto entries = output.entryInfoList(QDir::AllEntries | QDir::System | QDir::Hidden | QDir::NoDotAndDotDot);
    for (const auto &entry : entries) {
        const auto name = entry.fileName();
        if (name == ".publication.lock")
            continue;
        require(name.startsWith(".attempt-") && entry.isDir() &&
                !hasRedirectedComponent(output, entry.absoluteFilePath()), "Sortie V3 déjà utilisée : " + name);
        const QDir attempt(entry.absoluteFilePath());
        const auto prior = load(exactFile(attempt, "journal.json"));
        require(prior.value("schema") == "v3.b1.journal/1" && prior.value("plan_sha256") == planSha,
                "Interruption d'une autre transaction V3");
        // An interrupted child may still have the isolated scratch directory open.
        // Abandon the attempt and run in a different directory.
        abandoned.append(QJsonObject{{"attempt", name}, {"journal_sha256", fileDigest(attempt.filePath("journal.json"))}});
    }
    return abandoned;
}

QJsonObject refusal(const QDir &output, QJsonObject report, const QString &status, const QString &reason)
{
    report.insert("status", status);
    report.insert("reason", reason);
    report.insert("finalized", true);
    write(output.filePath("refusal.json"), report);
    return report;
}

QStringList validatePlan(const QJsonObject &plan, const QJsonObject &profile)
{
    static const QStringList fields{"actions", "context_sha256", "domain", "plan_id", "profile_sha256", "schema"};
    require(plan.keys() == fields, "Champs du plan V3 non autorisés ou absents");
    const auto planId = identifier(plan.value("plan_id"));
    const auto actions = plan.value("actions").toArray();
    require(!actions.isEmpty() && actions.size() <= 8, "Nombre d'actions hors bornes");
    QMap<QString, QJsonObject> reviewed;
    for (const auto &value : profile.value("actions").toArray()) {
        const auto action = value.toObject();
        const auto id = identifier(action.value("id"));
        require(!reviewed.contains(id), "Identité d'action ambiguë dans le profil");
        reviewed.insert(id, action);
    }
    QStringList sequence;
    QSet<QString> writes;
    for (const auto &value : actions) {
        const auto action = value.toObject();
        const auto id = identifier(action.value("id"));
        const auto subject = action.value("occurrence").toString();
        require(reviewed.contains(id) && action == reviewed.value(id), "Action hors du domaine A.1 : " + id);
        require(!writes.contains(subject) && action.value("parameters").isObject() &&
                action.value("expected_before").isObject() && action.value("expected_after").isObject() &&
                !action.value("domain_limits").toObject().isEmpty() && !action.value("affected").toArray().isEmpty(),
                "Action non typée ou sujet écrit plusieurs fois : " + id);
        writes.insert(subject);
        sequence.append(id);
    }
    const auto allowed = profile.value("compositions").toArray();
    require(allowed.contains(QJsonArray::fromStringList(sequence)), "Composition ordonnée hors du domaine A.1");
    const auto binding = plan.value("profile_sha256").toString() + '\n' + planId + '\n' + sequence.join('\n');
    require(plan.value("context_sha256") == digest(binding.toUtf8()), "Signature du contexte incohérente");
    return sequence;
}

QJsonArray calculateImpact(const QDir &root, const QJsonObject &profile, const QJsonArray &actions)
{
    const auto path = exactFile(root, profile.value("graph").toString());
    const auto bytes = read(path);
    require(digest(bytes) == profile.value("graph_sha256"), "Graphe V3-A altéré");
    const auto graph = parseUniqueObject(bytes, path);
    const auto authorities = graph.value("sources").toObject();
    for (auto it = authorities.begin(); it != authorities.end(); ++it) {
        const auto reference = it.value().toObject();
        require(fileDigest(exactFile(root, reference.value("path").toString())) == reference.value("sha256"),
                "Source du graphe V3-A altérée : " + it.key());
    }
    QJsonArray impacts;
    for (const auto &value : actions) {
        const auto action = value.toObject();
        const auto impact = electromechanical::graph::impact(graph, action.value("graph_operation").toString(),
                                                           action.value("graph_target").toString());
        const auto affected = action.value("affected").toArray();
        const auto nodes = impact.value("nodes").toArray();
        require(affected.contains(action.value("occurrence")) && !impact.value("checks").toArray().isEmpty(),
                "Fermeture d'impact sans contrôles ou sujet direct");
        for (const auto &subject : affected)
            require(nodes.contains(subject), "Impact non fermé pour : " + subject.toString());
        impacts.append(QJsonObject{{"action_id", action.value("id")}, {"closure", impact}});
    }
    return impacts;
}

QJsonObject execute(const QDir &root, const QDir &sandbox, const QDir &output, const QByteArray &planBytes,
                    const QJsonObject &plan, const QJsonObject &profile, const QString &freecad, const QString &t0,
                    QJsonObject report, const QJsonArray &abandoned)
{
    const auto source = QDir(root.filePath(profile.value("source").toString()));
    const auto dependencies = profile.value("dependencies").toObject();
    const auto entry = profile.value("entry").toString();
    const auto planId = plan.value("plan_id").toString();
    const auto actions = plan.value("actions").toArray();
    QTemporaryDir scratch(output.filePath(".attempt-XXXXXX"));
    require(scratch.isValid(), "Transaction XLink inaccessible");
    const QDir stage(scratch.path());
    QJsonObject journal{{"schema", "v3.b1.journal/1"}, {"plan_id", planId}, {"plan_sha256", report.value("plan_sha256")}};
    appendJournal(stage, journal, "PREPARED", {{"abandoned_attempts", abandoned}});
    const QDir published(stage.filePath("publication"));
    const QDir mutation(stage.filePath("mutation"));
    const QDir transfer(published.filePath("cad"));
    require(published.mkpath("."), "Préparation de la publication impossible");
    QJsonObject job{{"plan_id", planId}, {"entry", entry}, {"dependencies", dependencies},
                    {"model", profile.value("model")}, {"actions", actions}};
    const bool spatial = report.value("plan_schema") == v3SpatialPlanSchema;
    const bool multiharness = spatial || report.value("plan_schema") == v3MultiHarnessPlanSchema;
    if (multiharness) {
        job.insert("support_option", plan.value("support_option"));
        report.insert("support_option", plan.value("support_option"));
    }
    QSet<QString> mandatory;
    for (const auto &value : report.value("admissions").toArray()) {
        for (const auto &check : value.toObject().value("mandatory_checks").toArray())
            mandatory.insert(check.toString());
    }
    if (spatial) {
        job.insert("spatial_contract", plan.value("spatial_contract"));
        if (plan.contains("external_obstacle"))
            job.insert("external_obstacle", plan.value("external_obstacle"));
        mandatory.insert("L4_SPATIAL_CONTRACT");
    }
    auto checks = mandatory.values();
    checks.sort();
    job.insert("mandatory_checks", QJsonArray::fromStringList(checks));
    const auto workerPath = exactFile(root, worker);
    const auto verifierPath = exactFile(root, verifier);
    const QJsonObject tools{{"l5_sha256", fileDigest(QCoreApplication::applicationFilePath())},
        {"builder_sha256", fileDigest(workerPath)}, {"verifier_sha256", fileDigest(verifierPath)},
        {"freecad_python_sha256", fileDigest(freecad)}, {"t0_validator_sha256", fileDigest(t0)}};
    report.insert("tools", tools);
    report.insert("abandoned_attempts", abandoned);
    QJsonArray inputs;
    qsizetype serial = 0;
    for (auto it = dependencies.begin(); it != dependencies.end(); ++it) {
        inputs.append(QJsonObject{{"input_id", "native-" + QString::number(++serial)}, {"kind", "other"},
            {"reference", QJsonObject{{"path", relative(root, exactFile(source, it.key()))}}},
            {"checksums", QJsonObject{{"sha256", it.value()}}}});
    }
    QMap<QString, QString> artifacts;
    artifacts.insert("mutation-plan.json", write(published.filePath("mutation-plan.json"), planBytes));
    QJsonObject evidenceParameters{{"plan_id", planId}, {"plan_sha256", report.value("plan_sha256")},
                                   {"profile_sha256", plan.value("profile_sha256")}};
    if (isV3ParametricPlan(report.value("plan_schema"))) {
        const auto domainSha = plan.value("domain_sha256").toString();
        const auto domainPath = v3DomainPath(domainSha);
        const auto expandedSha = write(published.filePath("expanded-plan.json"), plan);
        artifacts.insert("expanded-plan.json", expandedSha);
        report.insert("expanded_plan_sha256", expandedSha);
        evidenceParameters.insert("authority_sha256", domainSha);
        evidenceParameters.insert("domain_sha256", domainSha);
        evidenceParameters.insert("expanded_plan_sha256", expandedSha);
        inputs.append(QJsonObject{{"input_id", "authority-domain"}, {"kind", "other"},
            {"reference", QJsonObject{{"path", domainPath}}},
            {"checksums", QJsonObject{{"sha256", domainSha}}}});
    }
    architecture_decision::Evidence evidence(published.absolutePath(), inputs, evidenceParameters,
        tools, {"v3_b1", "convergence_core", "xlink", "SYNTHETIC_BENCH", "Transaction native V3 B.1 préparée",
                "Transaction native V3 B.1 finalisée"});
    QString status = "INCONCLUSIVE";
    QJsonObject resultingFiles;
    try {
        require(hashes(source, dependencies) == dependencies && hashes(sandbox, dependencies) == dependencies,
                "Source XLink altérée après l'admission");
        copyClosure(sandbox, mutation, dependencies);
        const auto baseline = inspect(root, published, mutation, stage, journal, freecad, "baseline", job);
        bool reopened = false;
        for (const auto &row : baseline.value("checks").toArray()) {
            const auto check = row.toObject();
            reopened |= check.value("id") == "REOPEN_XLINK" && check.value("status") == "PASS";
        }
        require(reopened, "Réouverture native de référence incomplète");
        const auto jobPath = published.filePath("build-job.json");
        const auto jobSha = write(jobPath, job);
        report.insert("candidate_transactions", 1);
        const auto built = call(root, stage, journal, "build", freecad,
            {"-B", workerPath, "--root", mutation.absolutePath(), "--job", jobPath,
             "--output", published.filePath("build.json")}, 120000);
        const auto build = load(exactFile(published, "build.json"));
        require(build.value("schema") == "v3.b1.native_build/1" && build.value("finalized") == true &&
                build.value("plan_id") == planId && build.value("job_sha256") == jobSha &&
                build.value("documents_closed") == true && build.value("builder_sha256") == tools.value("builder_sha256") &&
                !build.value("worker_id").toString().isEmpty() && build.value("before_sha256") == dependencies,
                "Reçu du constructeur incohérent");
        if (built.value("exit_code") == 2 && build.value("status") == "FAIL" && build.value("save_performed") == false) {
            status = "FAIL";
            report.insert("reason", "CONSTRUCTOR_REJECTED");
            report.insert("construction_result", "FAIL");
        } else {
            require(built.value("exit_code") == 0 && build.value("status") == "PASS" &&
                    build.value("save_performed") == true, "Constructeur non finalisé");
            const auto after = hashes(mutation, dependencies);
            auto unchanged = after;
            unchanged.insert(entry, dependencies.value(entry));
            require(after.value(entry) != dependencies.value(entry) && build.value("after_sha256") == after &&
                    unchanged == dependencies, "Installation du natif divergente");
            report.insert("construction_result", "PASS");
            copyClosure(mutation, transfer, after);
            job.insert("dependencies", after);
            job.insert("baseline", baseline);
            const auto candidate = inspect(root, published, transfer, stage, journal, freecad, "candidate", job);
            require(baseline.value("worker_id") != candidate.value("worker_id") &&
                    build.value("worker_id") != candidate.value("worker_id") &&
                    candidate.value("pid") != build.value("pid"), "Validation sans processus indépendant");
            status = candidate.value("status").toString();
            report.insert("reason", "INDEPENDENT_NATIVE_VALIDATION");
            report.insert("validation_status", status);
            if (!multiharness || status == "PASS")
                resultingFiles = after;
        }
    } catch (const std::exception &error) {
        report.insert("reason", QString::fromUtf8(error.what()));
        appendJournal(stage, journal, "EXECUTION_ABORTED", {{"reason", report.value("reason")}});
    }
    QJsonObject sourceAfter, inputAfter;
    try {
        sourceAfter = hashes(source, dependencies);
        inputAfter = hashes(sandbox, dependencies);
    } catch (const std::exception &error) {
        appendJournal(stage, journal, "SOURCE_CHECK_FAILED", {{"reason", QString::fromUtf8(error.what())}});
    }
    const bool sourcesIntact = sourceAfter == dependencies && inputAfter == dependencies;
    report.insert("source_integrity", QJsonObject{{"status", sourcesIntact ? "PASS" : "FAIL"},
        {"before_sha256", dependencies}, {"source_after_sha256", sourceAfter}, {"sandbox_after_sha256", inputAfter}});
    if (!sourcesIntact) {
        status = "FAIL";
        resultingFiles = {};
        report.insert("reason", "SOURCE_INTEGRITY_FAILURE");
    }
    if (resultingFiles.isEmpty() && transfer.exists()) {
        require(transfer.canonicalPath() == transfer.absolutePath() &&
                !hasRedirectedComponent(published, transfer.absolutePath()), "Copie de transfert redirigée");
        require(QDir(transfer).removeRecursively(), "Abandon de la copie de transfert impossible");
    }
    const auto native = resultingFiles.isEmpty() ? "ROLLED_BACK" : status == "PASS" ? "CANDIDATE" : "MEASURED_REJECTED";
    report.insert("candidate_state", native);
    report.insert("native_sha256", resultingFiles);
    report.insert("status", status);
    report.insert("finalized", true);
    report.insert("verdict", status == "PASS" ? "V3_B1_PASS" : status == "FAIL" ? "V3_B1_FAIL" : "V3_B1_CONDITIONAL");
    appendJournal(stage, journal, native);
    artifacts.insert("journal.json", write(published.filePath("journal.json"), journal));
    for (const auto &name : {"baseline-job.json", "baseline-validation.json", "build-job.json", "build.json",
                             "candidate-job.json", "candidate-validation.json"}) {
        if (QFileInfo::exists(published.filePath(name)))
            artifacts.insert(name, fileDigest(exactFile(published, name)));
    }
    for (auto it = resultingFiles.begin(); it != resultingFiles.end(); ++it)
        artifacts.insert("cad/" + it.key(), it.value().toString());
    artifacts.insert("campaign.json", write(published.filePath("campaign.json"), report));
    try {
        evidence.finalize(report, artifacts);
        verifyEvidence(published, "V3_B1");
        const auto crosscheck = call(root, stage, journal, "t0", t0,
            {"validate", published.absolutePath(), root.absolutePath()}, 30000);
        require(crosscheck.value("exit_code") == 0, "Validateur T0 indépendant en échec");
        write(published.filePath("t0-crosscheck.json"), crosscheck);
        require(hashes(source, dependencies) == dependencies && hashes(sandbox, dependencies) == dependencies,
                "Sources altérées à la publication");
        require(QDir().rename(published.absolutePath(), output.filePath("transaction")), "Publication atomique impossible");
    } catch (const std::exception &error) {
        report.insert("candidate_state", "ROLLED_BACK");
        report.remove("native_sha256");
        report.remove("verdict");
        const auto reason = QString::fromUtf8(error.what());
        appendJournal(stage, journal, "PUBLICATION_ROLLED_BACK", {{"reason", reason}});
        write(output.filePath("rollback.json"), journal);
        return refusal(output, report, "INCONCLUSIVE", reason);
    }
    return report;
}

} // namespace

QJsonObject runV3Mutation(const QDir &root, const QDir &sandbox, const QDir &output,
                          const QByteArray &planBytes, const QJsonObject &plan, const QString &freecadPython,
                          const QString &t0Validator)
{
    const auto planSha = digest(planBytes);
    require(!output.exists("transaction"), "Une transaction est déjà finalisée dans ce dossier");
    const auto abandoned = recover(output, planSha);
    QJsonObject report{{"schema", "v3.b1.transaction/1"}, {"plan_id", plan.value("plan_id")},
        {"plan_sha256", planSha}, {"construction_result", "NOT_RUN"}, {"validation_status", "NOT_RUN"},
        {"candidate_transactions", 0}, {"execution_scope", "NONE"}};
    const bool parametric = isV3ParametricPlan(plan.value("schema"));
    if (!parametric && plan.value("schema") != planSchema)
        return refusal(output, report, "UNSUPPORTED", "CONTRACT_VERSION_UNSUPPORTED");
    if (plan.value("domain") != "SYNTHETIC_BENCH")
        return refusal(output, report, "FAIL", "MUTATION_DOMAIN_DENIED");
    QJsonObject executablePlan = plan;
    QJsonObject profile;
    try {
        QJsonArray parametricDecisions;
        QStringList sequence;
        if (parametric) {
            const auto admitted = admitV3Plan(root, sandbox, plan);
            profile = admitted.profile;
            executablePlan = admitted.expandedPlan;
            parametricDecisions = admitted.decisions;
            for (const auto &value : executablePlan.value("actions").toArray())
                sequence.append(identifier(value.toObject().value("id")));
            report.insert("plan_schema", plan.value("schema"));
            report.insert("authority_sha256", executablePlan.value("authority_sha256"));
            report.insert("domain_sha256", executablePlan.value("domain_sha256"));
        } else {
            for (const auto &value : plan.value("actions").toArray()) {
                if (!implemented.contains(value.toObject().value("operation").toString()))
                    return refusal(output, report, "UNSUPPORTED", "OPERATION_UNSUPPORTED");
            }
            profile = loadMutationProfile(root, plan.value("profile_sha256").toString());
            sequence = validatePlan(plan, profile);
        }
        const auto constraints = profile.value("constraints").toObject();
        const auto constraintKeys = constraints.keys();
        require(QSet<QString>(constraintKeys.begin(), constraintKeys.end()) == QSet<QString>{
            "BMS_USB_STRUCTURE_ISOLATION", "NC", "TX_RX", "PROTECTIONS", "PINOUT", "INDEPENDENT_FRAMES",
            "GEOMETRY", "SUPPORT_ANCHOR", "SERVICE", "IMMUTABLE_SOURCES", "DYNAMIC_BEND_RADIUS"},
            "Registre des contraintes A.1 incomplet");
        report.insert("operations", QJsonArray::fromStringList(sequence));
        report.insert("context_sha256", executablePlan.value("context_sha256"));
        QJsonArray admissions;
        const auto actions = executablePlan.value("actions").toArray();
        const auto profileSha = executablePlan.value("profile_sha256").toString();
        for (qsizetype index = 0; index < actions.size(); ++index) {
            const auto action = actions.at(index).toObject();
            const auto admission = parametric ? parametricDecisions.at(index).toObject()
                : evaluateAdmissionScope(root, sandbox, mutationAdmissionRequest(profile, profileSha, action));
            admissions.append(admission);
            report.insert("admissions", admissions);
            require(admission.value("decision") == "ALLOW" && admission.value("execution_scope") == "BENCH_TEST_ONLY" &&
                    admission.value("allowed_operations") == QJsonArray{action.value("operation")},
                    "Admission A.1 : " + admission.value("reason").toString());
        }
        report.insert("execution_scope", "BENCH_TEST_ONLY");
        report.insert("impact", calculateImpact(root, profile, actions));
    } catch (const V3UnsupportedPose &error) {
        return refusal(output, report, "UNSUPPORTED", QString::fromUtf8(error.what()));
    } catch (const std::exception &error) {
        return refusal(output, report, "FAIL", QString::fromUtf8(error.what()));
    }
    return execute(root, sandbox, output, planBytes, executablePlan, profile, freecadPython, t0Validator, report, abandoned);
}

} // namespace convergence
