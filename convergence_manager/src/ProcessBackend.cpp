#include "ProcessBackend.hpp"
#include "AdmissionScope.hpp"
#include "Files.hpp"
#include "ResearchAdapter.hpp"

#include <QCoreApplication>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QProcess>
#include <QSet>
#include <QStandardPaths>
#include <QSysInfo>

namespace convergence {
namespace {

const QString builder = "convergence_manager/native/build_candidate.py";
const QString lockName = "authority/l4-lock.json";

struct Result {
    int code;
    QByteArray output;
};

Result invoke(const QDir &root, const QString &program, const QStringList &args, int timeout,
              const QSet<int> &codes)
{
    QProcess process;
    process.setWorkingDirectory(root.absolutePath());
    process.start(program, args);
    require(process.waitForStarted(5000), "Démarrage impossible : " + program + " (" + process.errorString() + ')');
    if (process.state() != QProcess::NotRunning && !process.waitForFinished(timeout)) {
        process.kill();
        process.waitForFinished(5000);
        require(false, "Délai expiré : " + program);
    }
    const auto code = process.exitCode();
    const auto diagnostic = QString::fromUtf8(process.readAllStandardError().right(8192)).trimmed();
    require(process.exitStatus() == QProcess::NormalExit && codes.contains(code),
            QString("%1 (code %2) : %3").arg(program).arg(code).arg(diagnostic));
    return {code, process.readAllStandardOutput()};
}

QString executable(const QDir &root, const QString &path, bool required = true)
{
    require(!path.isEmpty(), "Chemin d'exécutable absent");
    const QFileInfo info(root.absoluteFilePath(path));
    const auto canonical = info.isFile() ? info.canonicalFilePath() : QStandardPaths::findExecutable(path);
    require(!required || !canonical.isEmpty(), "Exécutable absent : " + path);
    return canonical.isEmpty() ? info.absoluteFilePath() : canonical;
}

QJsonObject checkedJson(const QDir &root, const QString &path, const QJsonValue &sha)
{
    const auto bytes = read(fileInside(root, path));
    require(digest(bytes) == sha, "Empreinte de preuve divergente : " + path);
    return parse(bytes, path);
}

} // namespace

QJsonObject verifyEvidence(const QDir &directory, const QString &lot)
{
    const auto terminal = load(fileInside(directory, "t0_run_manifest.json"));
    const auto ledger = load(fileInside(directory, "artifacts.json"));
    require(terminal.value("schema") == "drone_agricole.run_manifest.v1" &&
            terminal.value("state") == "completed" &&
            ledger.value("schema") == "drone_agricole.artifacts.v1" &&
            terminal.value("run_id").isString() && terminal.value("run_id") == ledger.value("run_id"),
            "Manifeste terminal T0 absent ou incohérent");
    QJsonObject artifacts;
    for (const auto &entry : ledger.value("items").toArray()) {
        const auto item = entry.toObject();
        const auto path = item.value("path").toString();
        const auto sha = item.value("checksum_sha256");
        const auto file = fileInside(directory, path);
        require(relative(directory, file) == path && !artifacts.contains(path) &&
                sha.isString() && fileDigest(file) == sha, "Artefact T0 invalide : " + path);
        artifacts.insert(path, sha);
    }
    const QJsonObject expected{{"request", "run_request.json"}, {"campaign", "campaign.json"},
        {"metrics", "t0_metrics.json"}, {"events", "events.jsonl"}, {"artifacts", "artifacts.json"}};
    require(terminal.value("files") == expected, "Table des chemins T0 divergente");
    for (const auto &name : {"run_request.json", "campaign.json", "t0_metrics.json", "events.jsonl"}) {
        require(artifacts.contains(name), QString("Entrée T0 manquante : ") + name);
    }
    const auto request = checkedJson(directory, "run_request.json", artifacts.value("run_request.json"));
    const auto metrics = checkedJson(directory, "t0_metrics.json", artifacts.value("t0_metrics.json"));
    const auto campaign = checkedJson(directory, "campaign.json", artifacts.value("campaign.json"));
    const auto verdict = campaign.value("verdict").toString();
    require(campaign.value("finalized") == true &&
            request.value("request_id") == terminal.value("request_id") &&
            request.value("simulation_id") == "electromechanical_" + lot.toLower() &&
            metrics.value("run_id") == terminal.value("run_id") &&
            verdict == terminal.value("metadata").toObject().value("verdict") &&
            QStringList{lot + "_PASS", lot + "_FAIL", lot + "_CONDITIONAL"}.contains(verdict),
            "Verdict terminal T0 incohérent");
    return {{"campaign", campaign}, {"artifacts", artifacts}, {"terminal", terminal}};
}

ProcessBackend::ProcessBackend(QDir root, QDir output, QJsonObject config, ToolPaths tools)
    : root_(std::move(root)), output_(std::move(output)), config_(std::move(config)), tools_(std::move(tools))
{
    tools_.l1 = executable(root_, tools_.l1);
    tools_.l3 = executable(root_, tools_.l3);
    tools_.l4 = executable(root_, tools_.l4);
    tools_.python = executable(root_, tools_.python);
    tools_.freecad = executable(root_, tools_.freecad, false);
}

QJsonObject ProcessBackend::freeze(const QString &configPath)
{
    const auto native = config_.value("native").toObject();
    const auto referenceConfig = fileInside(root_, native.value("reference").toString());
    require(output_.mkpath("authority"), "Dossier d'autorité L5 inaccessible");
    const auto lockPath = output_.filePath(lockName);
    if (!QFileInfo::exists(lockPath)) {
        require(!QFileInfo::exists(output_.filePath("manifest.json")), "Gel L4 absent à la reprise");
        QStringList args{"seal", "--root", root_.absolutePath(), "--configuration", referenceConfig,
                         "--lock", lockPath, "--python", tools_.python};
        if (QFileInfo(tools_.freecad).isFile()) {
            args << "--freecad-python" << tools_.freecad;
        }
        const auto sealed = invoke(root_, tools_.l4, args, 30000, {0});
        require(QString::fromLatin1(sealed.output.trimmed()) == fileDigest(lockPath), "Empreinte émise par L4 divergente");
    }
    const auto lockSha = fileDigest(fileInside(output_, lockName));
    const auto lock = load(lockPath);
    const auto bindings = lock.value("files").toObject();
    auto declaredBindings = load(referenceConfig).value("files").toObject();
    const auto nativeRecipe = load(fileInside(root_, declaredBindings.value("native").toString()));
    qsizetype sourceIndex = 0;
    for (const auto &source : nativeRecipe.value("source_files").toArray()) {
        declaredBindings.insert("native-source-" + QString::number(++sourceIndex), source);
    }
    declaredBindings.insert("configuration", referenceConfig);
    require(bindings.keys() == declaredBindings.keys(), "Périmètre du gel L4 différent de la recette déclarée");
    QJsonObject files;
    const auto capture = [&](const QString &name) {
        const auto path = fileInside(root_, name);
        files.insert(relative(root_, path), fileDigest(path));
    };
    for (auto it = declaredBindings.constBegin(); it != declaredBindings.constEnd(); ++it) {
        const auto path = fileInside(root_, it.value().toString());
        const auto name = relative(root_, path);
        capture(path);
        const auto item = bindings.value(it.key()).toObject();
        require(item.value("path") == name && item.value("sha256") == files.value(name),
                "Fichier différent de la recette ou du gel L4 : " + it.key());
    }
    for (const auto &role : {qMakePair(QString("system"), QString("model-system")),
                             qMakePair(QString("requirements"), QString("model-requirements"))}) {
        require(fileInside(root_, native.value(role.first).toString()) ==
                fileInside(root_, bindings.value(role.second).toObject().value("path").toString()),
                "Modèle de construction différent du gel L4 : " + role.first);
    }
    capture(configPath);
    capture(builder);
    capture("electromechanical_engine/validation.py");
    capture(native.value("routes").toString());
    const auto research = config_.value("research").toObject();
    capture(research.value("catalog").toString());
    const auto catalog = load(fileInside(root_, research.value("catalog").toString()));
    for (const auto &entry : catalog.value("sources").toArray()) {
        const auto source = entry.toObject().value("evidence").toObject().value("artifact_path");
        if (source.isString()) {
            capture(source.toString());
        }
    }
    for (const auto &entry : research.value("inputs").toArray()) {
        capture(entry.toString());
    }
    for (const auto &entry : config_.value("exploration").toObject()) {
        capture(entry.toString());
    }
    for (const auto &source : {"interconnection_engine/examples/banc_l2.json",
        "architecture_decision_engine/fixtures/f31_interconnection.json",
        "architecture_decision_engine/fixtures/f31_research.json",
        "architecture_decision_engine/fixtures/f31_straight_observation.json",
        "docs/electromechanical_v2/RESEARCH_REPORT.schema.json"}) {
        capture(source);
    }
    QJsonObject toolHashes;
    for (const auto &pair : {qMakePair(QString("l1"), tools_.l1), qMakePair(QString("l3"), tools_.l3),
            qMakePair(QString("l4"), tools_.l4), qMakePair(QString("python"), tools_.python),
            qMakePair(QString("freecad"), tools_.freecad),
            qMakePair(QString("l5"), QCoreApplication::applicationFilePath())}) {
        const auto path = QFileInfo(pair.second);
        toolHashes.insert(pair.first, QJsonObject{{"path", pair.second},
            {"sha256", path.isFile() ? QJsonValue(fileDigest(pair.second)) : QJsonValue(QJsonValue::Null)}});
    }
    require(toolHashes.value("l4").toObject().value("sha256") == lock.value("validator_sha256"),
            "Binaire L4 différent du gel");
    for (const auto &role : {"python", "freecad"}) {
        const auto tool = toolHashes.value(role).toObject();
        const auto frozen = lock.value("runtimes").toObject().value(role).toObject();
        if (!frozen.isEmpty()) {
            require(tool == frozen, QString("Interpréteur différent du gel L4 : ") + role);
        }
    }
    const auto system = load(fileInside(root_, native.value("system").toString()));
    const auto routes = load(fileInside(root_, native.value("routes").toString()));
    QJsonArray modelLinks;
    for (const auto &entry : system.value("links").toArray()) {
        modelLinks.append(entry.toObject().value("id"));
    }
    const auto coverage = config_.value("required_links").toArray();
    const auto scope = config_.value("base").toObject();
    require(modelLinks.size() == coverage.size() && modelLinks.size() == scope.size(),
            "Couverture déclarée différente du modèle gelé");
    for (const auto &id : modelLinks) {
        require(coverage.contains(id) && scope.contains("route:" + id.toString()),
                "Liaison du modèle absente du périmètre L5");
    }
    manifest_ = {{"schema_version", 1}, {"configuration", relative(root_, fileInside(root_, configPath))},
        {"reference_sha256", lockSha}, {"reference_lock", relative(root_, lockPath)}, {"files", files},
        {"tools", toolHashes}, {"routes", routes}, {"topology", system.value("links")},
        {"parameters", config_.value("budgets")}, {"qt", qVersion()},
        {"os", QSysInfo::prettyProductName()}, {"architecture", QSysInfo::currentCpuArchitecture()}};
    verify();
    return manifest_;
}

void ProcessBackend::verify() const
{
    require(fileDigest(fileInside(output_, lockName)) == manifest_.value("reference_sha256"),
            "Gel L4 modifié depuis l'inventaire");
    const auto files = manifest_.value("files").toObject();
    for (auto it = files.begin(); it != files.end(); ++it) {
        require(fileDigest(fileInside(root_, it.key())) == it.value(), "Entrée modifiée : " + it.key());
    }
    const auto tools = manifest_.value("tools").toObject();
    for (auto it = tools.begin(); it != tools.end(); ++it) {
        const auto tool = it.value().toObject();
        const auto path = tool.value("path").toString();
        const auto sha = tool.value("sha256");
        require(sha.isNull() ? !QFileInfo(path).isFile() : fileDigest(path) == sha, "Outil modifié : " + it.key());
    }
}

QJsonObject ProcessBackend::inventory()
{
    verify();
    return {{"reference_sha256", manifest_.value("reference_sha256")}, {"links", config_.value("required_links")},
            {"model_topology", manifest_.value("topology")}};
}

QJsonObject ProcessBackend::research(const QString &issue, const QDir &operation)
{
    const auto result = architecture_decision::researchIssue(tools_.l1, root_.absolutePath(),
        operation.filePath("cache"), config_.value("research").toObject().value("catalog").toString(), issue);
    auto report = result.value("report").toObject();
    report.insert("l1_stdout_sha256", result.value("sha256"));
    return report;
}

QJsonObject ProcessBackend::explore(const QDir &operation)
{
    const auto exploration = config_.value("exploration").toObject();
    const QDir out(operation.filePath("l3"));
    const auto process = invoke(root_, tools_.l3, {"--root", root_.absolutePath(), "--l1", tools_.l1,
        "--output", out.absolutePath(), "--benches", exploration.value("benches").toString(),
        "--requirements", exploration.value("requirements").toString(),
        "--acceptance", exploration.value("acceptance").toString()}, 90000, {0, 2, 3});
    const auto evidence = verifyEvidence(out, "L3");
    const auto campaign = evidence.value("campaign").toObject();
    require(process.code == 0 && campaign.value("verdict") == "L3_PASS", "La recette de criblage L3 a échoué");
    const auto software = evidence.value("terminal").toObject().value("software").toObject();
    const auto tools = manifest_.value("tools").toObject();
    require(software.value("l1_executable_sha256") == tools.value("l1").toObject().value("sha256") &&
            software.value("l3_executable_sha256") == tools.value("l3").toObject().value("sha256"),
            "Versions du criblage L3 différentes du gel de campagne");
    const auto artifacts = evidence.value("artifacts").toObject();
    QJsonArray alternatives, conflicts;
    for (const auto &value : campaign.value("benches").toObject()) {
        const auto bench = value.toObject();
        const auto baseline = bench.value("baseline").toObject();
        const auto path = baseline.value("path").toString();
        require(artifacts.value(path) == baseline.value("sha256"), "Rapport de référence L3 hors manifeste");
        for (const auto &conflict : checkedJson(out, path, artifacts.value(path)).value("conflict_graph").toArray()) {
            conflicts.append(conflict);
        }
        for (const auto &entry : bench.value("candidates").toArray()) {
            const auto item = entry.toObject();
            const auto candidatePath = item.value("path").toString();
            require(item.value("sha256") == artifacts.value(candidatePath), "Variante L3 hors manifeste");
            alternatives.append(checkedJson(out, candidatePath, artifacts.value(candidatePath)));
        }
    }
    return {{"alternatives", alternatives}, {"conflicts", conflicts},
        {"evidence", relative(output_, out.filePath("t0_run_manifest.json"))},
        {"evidence_sha256", fileDigest(out.filePath("t0_run_manifest.json"))}};
}

QJsonObject ProcessBackend::buildV3(const QDir &root, const QDir &sandbox, const QJsonObject &request)
{
    const auto admission = evaluateAdmissionScope(root, sandbox, request);
    const auto decision = admission.value("decision");
    const auto scope = admission.value("execution_scope");
    const auto domain = request.value("domain");
    const auto operation = request.value("operation");
    const auto output = request.value("output");
    QJsonObject report{{"schema", "v3.l5_admission_receipt/1"}, {"admission", admission},
        {"dispatch_status", "BLOCKED"}, {"candidate_transactions", 0}, {"construction_result", "NOT_RUN"}};

    if (decision != "ALLOW" || admission.value("allowed_operations") != QJsonArray{operation}) {
        return report;
    }
    if (operation == "ANALYZE_IMPACT") {
        if (scope == "READ_ONLY_IMPACT" && domain == "CARTOGRAPHER_PRIVATE_CAD" && output == "IMPACT_REPORT") {
            report.insert("dispatch_status", "READ_ONLY");
        }
        return report;
    }
    const QStringList benchOperations{"REPOSITION_DEVICE", "REROUTE_HARNESS", "RELOCATE_SUPPORT", "CREATE_SUPPORT"};
    if (scope != "BENCH_TEST_ONLY" || domain != "SYNTHETIC_BENCH" || output != "PRIVATE_CANDIDATE" ||
            !benchOperations.contains(operation.toString())) {
        return report;
    }

    // This is the dispatch boundary for future V3 operators. The legacy builder
    // below generates a static model and has no authority over XLink copies.
    report.insert("dispatch_status", "NOT_IMPLEMENTED");
    return report;
}

QJsonObject ProcessBackend::build(const QJsonObject &assignments, const QDir &operation)
{
    require(QFileInfo(tools_.freecad).isFile(), "FreeCAD indisponible : " + tools_.freecad);
    const auto native = config_.value("native").toObject();
    const auto catalog = manifest_.value("routes").toObject();
    QJsonObject routes;
    for (auto it = assignments.begin(); it != assignments.end(); ++it) {
        const auto route = catalog.value(it.value().toString()).toObject();
        const auto link = route.value("link").toString();
        require(!route.isEmpty() && it.key() == "route:" + link, "Affectation non constructible : " + it.key());
        routes.insert(link, route);
    }
    const QJsonObject plan{{"system", load(fileInside(root_, native.value("system").toString()))},
        {"requirements", load(fileInside(root_, native.value("requirements").toString()))},
        {"candidate", QJsonObject{{"routes", routes}}}};
    const auto planPath = operation.filePath("plan.json");
    const auto planSha = write(planPath, plan);
    const QDir fresh(operation.filePath("native"));
    invoke(root_, tools_.python, {"-B", root_.filePath(builder), "--freecad-python", tools_.freecad,
        "--plan", planPath, "--output", fresh.absolutePath(), "--timeout", "30"}, 105000, {0});
    const auto nativePath = fileInside(fresh, "candidate.FCStd");
    const auto receiptPath = fileInside(fresh, "build_receipt.json");
    auto receipt = load(receiptPath);
    const auto sha = fileDigest(nativePath);
    require(receipt.value("reopened") == true && receipt.value("save_performed") == true &&
            receipt.value("native_sha256") == sha && receipt.value("plan_sha256") == planSha &&
            receipt.value("native_inputs_sha256").toObject() == QJsonObject{{"candidate.FCStd", sha}},
            "Reçu de sauvegarde et de réouverture invalide");
    receipt.insert("path", relative(output_, nativePath));
    receipt.insert("sha256", sha);
    receipt.insert("receipt", relative(output_, receiptPath));
    receipt.insert("receipt_sha256", fileDigest(receiptPath));
    return receipt;
}

QJsonObject ProcessBackend::validate(const QJsonObject &built, const QDir &operation)
{
    const auto candidatePath = fileInside(output_, built.value("path").toString());
    const auto caseId = identifier(config_.value("native").toObject().value("case"));
    const auto portfolio = QFileInfo(operation.absolutePath()).dir().dirName();
    const auto seal = manifest_.value("reference_sha256");
    const QDir out(operation.filePath("l4"));
    const auto process = invoke(root_, tools_.l4, {"validate", "--root", root_.absolutePath(),
        "--lock", output_.filePath(lockName), "--lock-sha256", seal.toString(), "--case", caseId,
        "--candidate", candidatePath, "--candidate-id", portfolio, "--output", out.absolutePath(),
        "--python", tools_.python, "--freecad-python", tools_.freecad}, 300000, {0, 2, 3});
    return readValidation(built, out, caseId, portfolio, process.code);
}

QJsonObject ProcessBackend::readValidation(const QJsonObject &built, const QDir &out, const QString &caseId,
                                            const QString &portfolio, int code) const
{
    const auto seal = manifest_.value("reference_sha256");
    const auto evidence = verifyEvidence(out, "L4");
    const auto campaign = evidence.value("campaign").toObject();
    const auto artifacts = evidence.value("artifacts").toObject();
    const auto cases = campaign.value("cases").toObject();
    const auto summary = cases.value(caseId).toObject();
    const auto reportPath = "cases/" + caseId + ".json";
    const auto observationPath = "cases/" + caseId + "-native-observation.json";
    const auto report = checkedJson(out, reportPath, artifacts.value(reportPath));
    const auto observation = checkedJson(out, observationPath, artifacts.value(observationPath));
    const auto fingerprints = report.value("fingerprints").toObject();
    const auto native = observation.value("native_evidence").toObject();
    const auto measured = observation.value("measurements").toObject();
    const auto nativeSha = built.value("sha256");
    require(cases.size() == 1 && summary.value("report") == reportPath &&
            summary.value("sha256") == artifacts.value(reportPath) && report.value("finalized") == true &&
            report.value("validation_report").toObject().value("candidate_id") == portfolio &&
            report.value("case_id") == caseId && report.value("candidate_sha256") == nativeSha &&
            fingerprints == campaign.value("fingerprints").toObject() && fingerprints.value("reference_sha256") == seal &&
            fingerprints.value("validator_sha256") == manifest_.value("tools").toObject().value("l4").toObject().value("sha256"),
            "L4 a rapporté une autre candidate, référence ou version");
    const auto status = report.value("verdict").toString();
    if (code == 0 || code == 2) {
        require(status == (code == 0 ? "PASS" : "FAIL") && report.value("native_sha256") == nativeSha &&
                native.value("native_sha256") == nativeSha && native.value("repeat_exact") == true &&
                native.value("sources_unchanged") == true && native.value("copies_unchanged") == true &&
                measured.value("cables").toObject().value("sha256_modules") ==
                    built.value("cables").toObject().value("sha256_modules"),
                "Mesures indépendantes incomplètes ou version de Cables divergente");
    }
    QJsonObject metrics;
    const auto values = measured.value("architecture_metrics").toObject();
    for (auto it = values.begin(); it != values.end(); ++it) {
        metrics.insert(it.key(), it.value().toObject().value("value"));
    }
    QJsonArray coverage;
    const auto measuredRoutes = measured.value("route_metrics").toObject();
    for (const auto &link : measuredRoutes.keys()) {
        coverage.append(link);
    }
    return {{"status", status}, {"coverage", coverage}, {"metrics", metrics}, {"native_sha256", report.value("native_sha256")},
        {"reference_sha256", seal}, {"findings", report.value("findings")}, {"reason", native.value("reason")},
        {"report", relative(output_, out.filePath(reportPath))}, {"report_sha256", artifacts.value(reportPath)},
        {"evidence", relative(output_, out.filePath("t0_run_manifest.json"))},
        {"evidence_sha256", fileDigest(out.filePath("t0_run_manifest.json"))}};
}

void ProcessBackend::verifyConsolidation(const QJsonObject &outcome) const
{
    const auto consolidated = outcome.value("consolidated").toObject();
    if (consolidated.isEmpty()) {
        require(outcome.value("verdict") == "L5_FAIL", "Une consolidation indépendante est requise avant publication");
        return;
    }

    const auto portfolio = identifier(consolidated.value("id"));
    const auto prefix = "consolidations/" + portfolio + '/';
    const auto built = consolidated.value("build").toObject();
    const auto candidate = consolidated.value("path").toString();
    const auto candidatePath = fileInside(output_, candidate);
    require(relative(output_, candidatePath) == candidate && candidate.startsWith(prefix) &&
            candidate == built.value("path") && consolidated.value("sha256") == built.value("sha256") &&
            fileDigest(candidatePath) == built.value("sha256"),
            "Natif consolidé absent ou divergent avant publication");

    const auto stored = consolidated.value("validation").toObject();
    const auto terminal = stored.value("evidence").toString();
    const auto terminalPath = fileInside(output_, terminal);
    require(relative(output_, terminalPath) == terminal && terminal.startsWith(prefix) &&
            QFileInfo(terminalPath).fileName() == "t0_run_manifest.json",
            "Preuve L4 hors du dossier de consolidation");
    const QDir validation(QFileInfo(terminalPath).absolutePath());
    const auto caseId = identifier(config_.value("native").toObject().value("case"));
    const auto measured = readValidation(built, validation, caseId, portfolio, 0);
    const auto coverage = measured.value("coverage").toArray();
    require(consolidated.value("status") == "PASS" && measured == stored &&
            consolidated.value("coverage") == coverage &&
            consolidated.value("metrics") == measured.value("metrics") &&
            consolidated.value("reference_sha256") == manifest_.value("reference_sha256"),
            "La consolidation publiée diffère de la rétrovalidation indépendante");
    for (const auto &link : config_.value("required_links").toArray()) {
        require(coverage.contains(link), "Liaison gelée absente de la rétrovalidation : " + link.toString());
    }
}

} // namespace convergence
