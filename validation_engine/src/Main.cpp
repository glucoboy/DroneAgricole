#include "Connectivity.hpp"
#include "Evidence.hpp"
#include "Mechanical.hpp"
#include "Reference.hpp"
#include "XLink.hpp"
#include "Report.hpp"

#include <QCommandLineParser>
#include <QCoreApplication>
#include <QDateTime>
#include <QFileInfo>
#include <QJsonDocument>
#include <QProcess>
#include <QProcessEnvironment>
#include <QRegularExpression>
#include <QSet>
#include <QSysInfo>

#include <cstdio>

namespace electromechanical_validation {
namespace {

const QSet<QString> statuses{"PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN"};
const QRegularExpression identifier("^[A-Za-z][A-Za-z0-9_.:-]*$");
const QRegularExpression fileId("^[a-z][a-z0-9-]*$");

QString timestamp()
{
    return QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
}

QDir createOutput(const QDir &root, const QString &name)
{
    const QFileInfo info(root.absoluteFilePath(name));
    QDir parent(info.absoluteDir().canonicalPath());
    require(!name.isEmpty() && !info.absoluteDir().canonicalPath().isEmpty(), "Parent de sortie absent");
    const auto output = parent.filePath(info.fileName());
    relativePath(root, output);
    require(!QFileInfo::exists(output) && parent.mkdir(info.fileName()), "Dossier de sortie neuf requis : " + output);
    return QDir(output);
}

void verifyChecks(const QString &caseId, const QJsonArray &checks)
{
    require(fileId.match(caseId).hasMatch() && !checks.isEmpty(), "Cas sans identifiant ou contrôle : " + caseId);
    QSet<QString> keys;
    QSet<QByteArray> expected;
    for (const auto &item : checks) {
        auto check = item.toObject();
        const auto key = check.take("key").toString();
        const auto family = check.value("family").toString();
        const auto method = check.value("method").toString();
        require(fileId.match(key).hasMatch() && !keys.contains(key) && !method.isEmpty() &&
                QStringList{"V1", "V2", "V3", "V4", "V5", "V6"}.contains(family),
                "Contrôle invalide ou dupliqué : " + caseId + '/' + key);
        keys.insert(key);
        QSet<QString> subjects;
        for (const auto &entry : check.value("subjects").toArray()) {
            const auto id = entry.toString();
            require(identifier.match(id).hasMatch() && !subjects.contains(id), "Sujet invalide : " + id);
            subjects.insert(id);
        }
        require(!subjects.isEmpty(), "Contrôle sans sujet : " + key);
        const auto requirement = check.value("requirement_id").toString("L4-" + family + '-' + method);
        const auto revision = check.value("requirement_revision").toString("1");
        const auto state = check.value("state_id").toString("S-NOMINAL");
        require(identifier.match(requirement).hasMatch() && !revision.isEmpty() && identifier.match(state).hasMatch(),
                "Exigence, révision ou état invalide : " + key);
        const auto tolerance = check.value("tolerance");
        require(tolerance.isUndefined() || tolerance.isNull() || (tolerance.isDouble() && tolerance.toDouble() >= 0),
                "Tolérance invalide : " + key);
        const auto signature = QJsonDocument(QJsonObject{{"requirement", requirement}, {"revision", revision},
            {"method", method}, {"subjects", check.value("subjects")}, {"state", state},
            {"mandatory", check.value("mandatory").toBool(true)}}).toJson(QJsonDocument::Compact);
        require(!expected.contains(signature), "Couverture L0 dupliquée : " + caseId + '/' + key);
        expected.insert(signature);
    }
}

QJsonObject observeNative(const QDir &root, const QDir &output, const QCommandLineParser &options,
                          const Reference &reference, const QString &caseId, const QString &candidatePath)
{
    if (reference.runtimes().isEmpty() || options.isSet("skip-native")) {
        return {{"native_evidence", QJsonObject{{"state", "UNAVAILABLE"},
                 {"reason", "Interpréteur FreeCAD absent ou rejeu désactivé"}}}};
    }
    const auto python = reference.runtime("python", options.value("python"));
    const auto freecad = reference.runtime("freecad", options.value("freecad-python"));
    const auto work = output.filePath("native/" + caseId);
    QStringList args{"-B", "-m", "electromechanical_engine.qualification.l4_native",
        "--freecad-python", freecad, "--workspace", root.absolutePath(),
        "--reference", reference.path("native"), "--case", caseId, "--output", work};
    if (!candidatePath.isEmpty()) {
        args << "--candidate" << candidatePath;
    }
    QProcess process;
    auto env = QProcessEnvironment::systemEnvironment();
    env.remove("PYTHONHOME");
    env.remove("PYTHONSTARTUP");
    env.insert("PYTHONNOUSERSITE", "1");
    env.insert("PYTHONSAFEPATH", "1");
    env.insert("PYTHONPATH", root.absolutePath());
    env.insert("PYTHONUTF8", "1");
    process.setProcessEnvironment(env);
    process.setWorkingDirectory(root.absolutePath());
    process.setStandardOutputFile(output.filePath("native/" + caseId + ".log"));
    process.setProcessChannelMode(QProcess::MergedChannels);
    process.start(python, args);
    const auto failure = [&](const QString &state, const QString &reason) {
        return QJsonObject{{"native_evidence", QJsonObject{{"state", state}, {"reason", reason}}}};
    };
    if (!process.waitForStarted(5000)) {
        return failure("UNAVAILABLE", process.errorString());
    }
    if (!process.waitForFinished(300000)) {
        process.kill();
        process.waitForFinished(5000);
        return failure("INCOMPLETE", "Délai maximal du processus de mesure atteint");
    }
    const auto receipt = QDir(work).filePath("observation.json");
    if (process.exitStatus() != QProcess::NormalExit || !QFileInfo::exists(receipt)) {
        return failure("INCOMPLETE", "Processus de mesure sans reçu finalisé");
    }
    auto observation = parse(read(workspaceFile(QDir(work), receipt)), receipt);
    auto provenance = observation.value("native_evidence").toObject();
    require(observation.value("case_id") == caseId && observation.value("schema_version") == 1 &&
            provenance.value("adapter_sha256") == reference.hash("native-adapter"),
            "Reçu FreeCAD d’un autre cas ou adaptateur : " + caseId);
    const auto state = provenance.value("state").toString();
    require(QStringList{"MEASURED", "UNAVAILABLE", "INCOMPLETE"}.contains(state),
            "État du reçu FreeCAD absent ou invalide : " + caseId);
    provenance.insert("adapter_exit_code", process.exitCode());
    observation.insert("native_evidence", provenance);
    if (state != "MEASURED") {
        return observation;
    }
    require(process.exitCode() == 0 && provenance.value("repeat_exact") == true &&
            provenance.value("sources_unchanged") == true && provenance.value("copies_unchanged") == true,
            "Mesures natives sans provenance reproductible : " + caseId);
    require(candidatePath.isEmpty() || fileDigest(candidatePath) == provenance.value("native_sha256"),
            "Natif mesuré différent du candidat présenté : " + caseId);
    const auto manifest = provenance.value("source_manifest").toObject();
    const auto before = manifest.value("before").toObject();
    const auto entry = provenance.value("native_entry").toString();
    require(!entry.isEmpty() && before.contains(entry) && before == manifest.value("after") &&
            before.value(entry) == provenance.value("native_sha256"),
            "Manifeste des natifs absent, modifié ou sans empreinte de l’entrée : " + caseId);
    QSet<qint64> pids;
    QJsonObject initial;
    const auto measurements = observation.value("measurements").toObject();
    for (const auto &item : provenance.value("attempts").toArray()) {
        const auto attempt = item.toObject();
        const auto pid = attempt.value("pid").toInteger();
        const auto path = workspaceFile(QDir(work), attempt.value("artifact_path").toString());
        const auto raw = read(path);
        require(pid > 0 && !pids.contains(pid) && digest(raw) == attempt.value("sha256"),
                "Preuve de mesure ou identité de processus invalide : " + caseId);
        auto data = parse(raw, path);
        require(data.take("pid") == attempt.value("pid") && data.take("worker_id") == attempt.value("worker_id") &&
                !data.isEmpty() && (pids.isEmpty() || data == initial),
                "Mesures brutes divergentes : " + caseId);
        for (auto it = data.begin(); it != data.end(); ++it) {
            require(it.value() == measurements.value(it.key()), "Reçu différent de la mesure brute : " + caseId + '/' + it.key());
        }
        initial = data;
        pids.insert(pid);
    }
    require(pids.size() == 2, "Deux processus de réouverture distincts attendus : " + caseId);
    return observation;
}

struct Configuration {
    QJsonObject electrical;
    QJsonObject electricalReference;
    QJsonObject mechanical;
    QJsonObject native;
    QJsonObject acceptance;
    QJsonObject fingerprints;
    QJsonObject combined;
    QJsonObject nativeAliases;

    QJsonObject electricalCase(const QString &caseId) const
    {
        return electrical.value(combined.value(caseId).toString(caseId)).toObject();
    }

    QJsonArray checks(const QString &caseId) const
    {
        auto result = mechanical.value(nativeAliases.value(caseId).toString(caseId)).toArray();
        for (const auto &item : electricalCase(caseId).value("checks").toArray()) {
            result.append(item);
        }
        return result;
    }
};

Configuration configuration(const Reference &reference)
{
    const auto config = reference.document("configuration");
    QJsonArray research;
    for (const auto &id : config.value("research").toArray()) {
        research.append(reference.document(id.toString()));
    }
    const auto electrical = reference.document("connectivity");
    auto electricalReference = electrical;
    electricalReference.insert("l2", reference.document("l2"));
    electricalReference.insert("l3", reference.document("l3"));
    electricalReference.insert("research", research);
    electricalReference.insert("reconciliation", reference.document("l2-reconciliation"));
    QJsonObject requirementFiles{{"connectivity", reference.hash("connectivity")},
        {"mechanical", reference.hash("mechanical")}, {"native", reference.hash("native")},
        {"l2", reference.hash("l2")}, {"l3", reference.hash("l3")}};
    for (const auto *key : {"model-system", "model-requirements"}) {
        if (const auto hash = reference.hash(key); !hash.isEmpty()) {
            requirementFiles.insert(key, hash);
        }
    }
    const QJsonObject fingerprints{{"reference_sha256", reference.lockHash()},
        {"requirements_sha256", digest(QJsonDocument(requirementFiles).toJson(QJsonDocument::Compact))},
        {"requirement_files", requirementFiles}, {"acceptance_sha256", reference.hash("acceptance")},
        {"validator_version", VALIDATOR_VERSION}, {"validator_sha256", fileDigest(QCoreApplication::applicationFilePath())}};
    return {electrical.value("cases").toObject(), electricalReference, reference.document("mechanical"),
            reference.document("native").value("cases").toObject(), reference.document("acceptance"), fingerprints,
            config.value("combined_cases").toObject(), config.value("native_check_aliases").toObject()};
}

QJsonObject activeSources(const QDir &root, const Reference &reference)
{
    for (const auto &entry : reference.document("l0-baseline").value("native_closures").toArray()) {
        const auto closure = entry.toObject();
        if (closure.value("role") != "REFERENCE_ACTIVE") {
            continue;
        }
        const auto base = closure.value("root").toString();
        const auto files = closure.value("files_sha256").toObject();
        require(!files.isEmpty() && files.size() == closure.value("file_count").toInt(), "Fermeture active L0 incomplète");
        QJsonObject hashes;
        for (auto it = files.begin(); it != files.end(); ++it) {
            const auto path = base + '/' + it.key();
            const auto hash = fileDigest(workspaceFile(root, path));
            require(hash == it.value(), "Empreinte de la fermeture L0 active divergente : " + path);
            hashes.insert(path, hash);
        }
        return hashes;
    }
    throw std::runtime_error("Fermeture CAO active absente du référentiel L0");
}

struct Acceptance {
    bool failed = false;
    bool open = false;
    QJsonArray checks;
};

Acceptance grade(const QJsonObject &policy, const QJsonObject &reports)
{
    const auto expectedCases = policy.value("cases").toObject();
    require(policy.value("schema_version") == 1 && expectedCases.keys() == reports.keys(),
            "Les cas de réception diffèrent de la campagne gelée");
    Acceptance result;
    for (auto it = reports.begin(); it != reports.end(); ++it) {
        const auto expected = expectedCases.value(it.key()).toObject();
        const auto required = expected.value("findings").toObject();
        const auto report = it.value().toObject();
        QSet<QString> checked;
        bool caseUnavailable = false;
        for (const auto &entry : report.value("findings").toArray()) {
            const auto finding = entry.toObject();
            const auto key = finding.value("key").toString();
            require(required.contains(key), "Contrôle sans attente de réception : " + it.key() + '/' + key);
            const auto want = required.value(key).toString();
            const auto actual = finding.value("status").toString();
            require(statuses.contains(want), "Attente de réception inconnue : " + it.key() + '/' + key);
            const auto unavailable = actual == "NOT_RUN" && want != "NOT_RUN";
            const auto matches = actual == want;
            result.failed |= !matches && !unavailable;
            result.open |= unavailable;
            caseUnavailable |= unavailable;
            checked.insert(key);
            result.checks.append(QJsonObject{{"case_id", it.key()}, {"finding_id", finding.value("finding_id")},
                {"expected", want}, {"actual", actual},
                {"status", matches ? "PASS" : unavailable ? "NOT_RUN" : "FAIL"}});
        }
        require(!checked.isEmpty() && checked.size() == required.size(), "Critères de réception non émis : " + it.key());
        if (expected.contains("verdict")) {
            const auto want = expected.value("verdict").toString();
            const auto actual = report.value("verdict").toString();
            require(statuses.contains(want), "Verdict de réception inconnu : " + it.key());
            const auto unavailable = caseUnavailable && want != actual && actual != "FAIL";
            result.failed |= want != actual && !unavailable;
            result.open |= unavailable;
            result.checks.append(QJsonObject{{"case_id", it.key()}, {"report_verdict", true},
                {"expected", want}, {"actual", actual},
                {"status", want == actual ? "PASS" : unavailable ? "NOT_RUN" : "FAIL"}});
        }
    }
    return result;
}

QString markdown(const QJsonObject &reports, const QString &verdict)
{
    QString out = "# Rétrovalidation électromécanique L4\n\n**" + verdict + "**\n\n"
        "| Cas | Périmètre | Verdict | PASS | FAIL | INCONCLUSIVE | NOT_RUN |\n"
        "|---|---|---|---:|---:|---:|---:|\n";
    for (auto it = reports.begin(); it != reports.end(); ++it) {
        const auto report = it.value().toObject();
        const auto counts = report.value("counts").toObject();
        out += QString("| %1 | %2 | %3 | %4 | %5 | %6 | %7 |\n")
            .arg(it.key(), report.value("scope").toString(), report.value("verdict").toString())
            .arg(counts.value("PASS").toInt()).arg(counts.value("FAIL").toInt())
            .arg(counts.value("INCONCLUSIVE").toInt()).arg(counts.value("NOT_RUN").toInt());
    }
    out += "\nLe résultat s’applique aux critères et états documentés. Fatigue, CEM et sécurité du vol restent à valider.\n";
    return out;
}

int evaluate(const QDir &root, const QCommandLineParser &options, bool campaignMode)
{
    const Reference reference(root, options.value("lock"), options.value("lock-sha256"));
    const auto settings = configuration(reference);
    require(!reference.runtimes().isEmpty() || !options.isSet("freecad-python"),
            "Interpréteurs à déclarer lors du gel avec seal --freecad-python");
    const auto selected = options.value("case");
    auto allCases = settings.electrical.keys();
    allCases.append(settings.mechanical.keys());
    require(campaignMode ? !options.isSet("case") : allCases.contains(selected) || settings.nativeAliases.contains(selected),
            "Cas de validation absent ou inconnu");
    require(!campaignMode || (!options.isSet("candidate") && !options.isSet("candidate-id") && !options.isSet("electrical")),
            "Les bancs de réception utilisent les entrées de campagne");
    auto cases = campaignMode ? allCases : QStringList{selected};
    cases.sort();
    require(QSet<QString>(cases.begin(), cases.end()).size() == cases.size(), "Cas dupliqué entre familles");
    const auto output = createOutput(root, options.value("output"));
    require(output.mkdir("cases") && output.mkdir("native"), "Initialisation du dossier de campagne impossible");
    QJsonArray inputs = reference.inputs();
    QMap<QString, QString> candidatePaths, candidateHashes, inputHashes;
    QMap<QString, QJsonObject> candidates;
    for (const auto &caseId : cases) {
        const auto electrical = settings.electricalCase(caseId);
        const auto native = settings.native.contains(caseId);
        verifyChecks(caseId, settings.checks(caseId));
        const auto capture = [&](const QString &name, const QString &kind) {
            const auto canonical = workspaceFile(root, name);
            const auto hash = fileDigest(canonical);
            inputHashes.insert(canonical, hash);
            inputs.append(inputReference(kind + '-' + caseId, relativePath(root, canonical), hash));
            return canonical;
        };
        if (native && options.isSet("candidate")) {
            require(settings.native.value(caseId).toObject().value("mode") == "candidate",
                    "Ce périmètre gelé ne prend pas de natif externe : " + caseId);
            const auto path = capture(options.value("candidate"), "native-candidate");
            candidatePaths.insert(caseId, path);
            candidateHashes.insert(caseId, inputHashes.value(path));
        }
        auto path = options.value("electrical");
        if (path.isEmpty() && !native) {
            path = options.value("candidate");
        }
        if (path.isEmpty() && !electrical.isEmpty() && options.isSet("candidates")) {
            path = QDir(options.value("candidates")).filePath(caseId + ".json");
        }
        if (path.isEmpty()) {
            require(electrical.isEmpty() || !campaignMode, "Entrées électriques de campagne absentes");
            continue;
        }
        require(!electrical.isEmpty(), "Cas sans contrôle électrique : " + caseId);
        const auto canonical = capture(path, "electrical-candidate");
        const auto bytes = read(canonical);
        require(digest(bytes) == inputHashes.value(canonical), "Candidat électrique modifié lors de la lecture");
        candidates.insert(caseId, parse(bytes, canonical));
        if (!native) {
            candidateHashes.insert(caseId, inputHashes.value(canonical));
        }
    }
    const auto candidateId = options.value("candidate-id");
    require(candidateId.isEmpty() || identifier.match(candidateId).hasMatch(), "Identifiant de candidat invalide");
    const auto software = QJsonObject{{"qt_version", qVersion()}, {"os", QSysInfo::prettyProductName()},
        {"architecture", QSysInfo::currentCpuArchitecture()}, {"validator_version", VALIDATOR_VERSION},
        {"validator_sha256", settings.fingerprints.value("validator_sha256")}};
    auto parameters = settings.fingerprints;
    parameters.insert("case", campaignMode ? "campaign" : selected);
    parameters.insert("length_unit", "mm");
    parameters.insert("volume_unit", "mm3");
    const auto originals = campaignMode && !options.isSet("skip-native") ? activeSources(root, reference) : QJsonObject{};
    architecture_decision::Evidence t0(output.absolutePath(), inputs, parameters, software,
        {"l4", "validation_core", campaignMode ? "revalidation" : "candidate", "ELECTROMECHANICAL_VALIDATION",
         "Rétrovalidation indépendante lancée", "Résultats L4 publiés"});
    QMap<QString, QString> artifacts;
    const auto publish = [&](const QString &path, const QJsonObject &object) {
        const auto hash = writeNew(output.filePath(path), QJsonDocument(object).toJson());
        artifacts.insert(path, hash);
        return hash;
    };
    QJsonObject reports, originalSources;
    QJsonArray matrix;
    for (const auto &caseId : cases) {
        const auto electrical = settings.electricalCase(caseId);
        const auto native = settings.native.contains(caseId);
        const auto nativeCase = settings.native.value(caseId).toObject();
        require(!native || !nativeCase.isEmpty(), "Cas FreeCAD absent du référentiel : " + caseId);
        const auto scope = native ? (nativeCase.value("mode") == "historical" || nativeCase.value("mode") == "candidate" ? "CAD" : "BENCH")
                                  : electrical.value("scope").toString(caseId.contains("historical") ? "DOCUMENT" : "BENCH");
        require(QStringList{"CAD", "BENCH", "DOCUMENT"}.contains(scope), "Périmètre de contrôle inconnu");
        const auto observation = native ? observeNative(root, output, options, reference, caseId, candidatePaths.value(caseId))
                                        : QJsonObject{};
        const auto provenance = observation.value("native_evidence").toObject();
        const auto measurements = observation.value("measurements").toObject();
        const auto state = provenance.value("state").toString();
        const auto executed = !native || state == "MEASURED";
        const auto date = timestamp();
        const auto nativeEvidenceId = "native-evidence-" + caseId;
        const auto electricalEvidenceId = "electrical-evidence-" + caseId;
        QJsonArray evidence;
        if (native) {
            originalSources.insert(caseId, QJsonObject{{"state", state},
                {"sources_unchanged", provenance.value("sources_unchanged")}, {"files", provenance.value("source_manifest")}});
            const auto path = "cases/" + caseId + "-native-observation.json";
            evidence.append(makeEvidence(nativeEvidenceId, path, publish(path, observation), scope,
                "Relecture FreeCAD indépendante", date));
        }
        if (!electrical.isEmpty()) {
            const auto path = "cases/" + caseId + "-electrical-observation.json";
            const QJsonObject electricalObservation{{"candidate_observation", candidates.value(caseId)}, {"frozen_input_hashes", QJsonObject{
                {"l1_geometry", reference.hash("l1-f12-geometry")}, {"l1_revision", reference.hash("l1-f12-revision")},
                {"l2", reference.hash("l2")}, {"l3", reference.hash("l3")},
                {"reconciliation", reference.hash("l2-reconciliation")}}}};
            evidence.append(makeEvidence(electricalEvidenceId, path, publish(path, electricalObservation), scope,
                "Réconciliation L1, L2 et L3", date));
        }
        if (native && executed) {
            const auto caseDir = "native/" + caseId + '/';
            for (const auto &item : provenance.value("attempts").toArray()) {
                const auto attempt = item.toObject();
                artifacts.insert(caseDir + attempt.value("artifact_path").toString(), attempt.value("sha256").toString());
            }
            for (const auto &item : measurements.value("views").toObject()) {
                const auto view = item.toObject();
                const auto path = view.value("artifact_path").toString();
                const auto file = workspaceFile(QDir(output.filePath(caseDir)), path);
                const auto hash = view.value("sha256").toString();
                require(fileDigest(file) == hash, "Projection native modifiée : " + caseId + '/' + path);
                artifacts.insert(caseDir + path, hash);
            }
        }
        QJsonArray findings;
        for (const auto &entry : settings.checks(caseId)) {
            const auto check = entry.toObject();
            const auto isElectrical = check.value("family") == "V1";
            const auto result = isElectrical ? assessConnectivity(check, settings.electricalReference, candidates.value(caseId)) :
                executed ? assessMechanical(check, measurements) : Assessment{"NOT_RUN", QJsonValue::Null, "1",
                    provenance.value("reason").toString("Rejeu natif sans observation reproductible")};
            require(statuses.contains(result.status) && !result.reason.isEmpty(), "Constat invalide : " + caseId);
            findings.append(makeFinding(caseId, check, result, isElectrical ? electricalEvidenceId : nativeEvidenceId, date, scope));
        }
        QJsonArray tools{QJsonObject{{"name", "validation_core"}, {"version", VALIDATOR_VERSION}},
                         QJsonObject{{"name", "Qt"}, {"version", qVersion()}}};
        const auto nativeEnvironment = provenance.value("environment").toObject();
        for (auto it = nativeEnvironment.begin(); it != nativeEnvironment.end(); ++it) {
            if (it.value().isString() && !it.value().toString().isEmpty()) {
                tools.append(QJsonObject{{"name", it.key()}, {"version", it.value()}});
            }
        }
        const QJsonObject environment{{"platform", QSysInfo::prettyProductName()},
            {"architecture", QSysInfo::currentCpuArchitecture()}, {"tools", tools}};
        auto report = makeReport(caseId, candidateId.isEmpty() ? caseId : candidateId, scope, settings.fingerprints,
                                 environment, findings, evidence, native && executed ? nativeEvidenceId : QString{});
        report.insert("scope_description", nativeCase.value("scope").toString(
            scope == "DOCUMENT" ? "Constats documentaires archivés sur interfaces ciblées" :
                                  "Réconciliation numérique sur le graphe déclaré du banc"));
        report.insert("native_state", native ? QJsonValue(state) : QJsonValue::Null);
        report.insert("candidate_sha256", candidateHashes.contains(caseId) ? QJsonValue(candidateHashes.value(caseId)) : QJsonValue::Null);
        report.insert("native_sha256", provenance.value("native_sha256").isUndefined() ? QJsonValue::Null : provenance.value("native_sha256"));
        for (const auto &item : report.value("traceability").toArray()) {
            matrix.append(item);
        }
        publish("cases/" + caseId + ".json", report);
        reports.insert(caseId, report);
    }
    const auto acceptance = campaignMode ? grade(settings.acceptance, reports) : Acceptance{};
    const auto caseVerdict = campaignMode ? QString{} : reports.value(selected).toObject().value("verdict").toString();
    const auto limits = campaignMode ? settings.acceptance.value("open_scope").toArray() : QJsonArray{};
    const auto failed = campaignMode ? acceptance.failed : caseVerdict == "FAIL";
    const auto conditional = campaignMode ? acceptance.open || !limits.isEmpty() : caseVerdict != "PASS";
    const QString verdict = failed ? "L4_FAIL" : conditional ? "L4_CONDITIONAL" : "L4_PASS";
    reference.verify();
    if (!options.isSet("skip-native") && !reference.runtimes().isEmpty()) {
        reference.runtime("python", options.value("python"));
        reference.runtime("freecad", options.value("freecad-python"));
    }
    for (auto it = inputHashes.begin(); it != inputHashes.end(); ++it) {
        require(fileDigest(it.key()) == it.value(), "Candidat modifié pendant la validation : " + it.key());
    }
    const auto originalAfter = originals.isEmpty() ? QJsonObject{} : activeSources(root, reference);
    require(originals == originalAfter, "Fermeture active modifiée pendant la campagne");
    publish("original_sources.json", {{"schema_version", 1}, {"cases", originalSources},
        {"active_closure", QJsonObject{{"before", originals}, {"after", originalAfter},
            {"state", originals.isEmpty() ? "NOT_RUN" : "UNCHANGED"}}}});
    publish("traceability.json", {{"schema_version", 1}, {"matrix", matrix}});
    artifacts.insert("SUMMARY.md", writeNew(output.filePath("SUMMARY.md"), markdown(reports, verdict).toUtf8()));
    QJsonObject summaries;
    for (auto it = reports.begin(); it != reports.end(); ++it) {
        const auto report = it.value().toObject();
        const auto path = "cases/" + it.key() + ".json";
        summaries.insert(it.key(), QJsonObject{{"verdict", report.value("verdict")}, {"counts", report.value("counts")},
            {"coverage", report.value("coverage")}, {"report", path}, {"sha256", artifacts.value(path)}});
    }
    const QJsonObject campaign{{"schema_version", 1}, {"verdict", verdict}, {"finalized", true},
        {"fingerprints", settings.fingerprints}, {"cases", summaries}, {"acceptance", acceptance.checks},
        {"open_scope", limits}, {"traceability", "traceability.json"}, {"original_sources", "original_sources.json"}};
    publish("campaign.json", campaign);
    t0.finalize(campaign, artifacts);
    std::puts(verdict.toLatin1().constData());
    return failed ? 2 : conditional ? 3 : 0;
}

} // namespace
} // namespace electromechanical_validation

int main(int argc, char **argv)
{
    using namespace electromechanical_validation;
    QCoreApplication app(argc, argv);
    QCommandLineParser options;
    options.setApplicationDescription("Validateur électromécanique indépendant L4");
    options.addHelpOption();
    options.addPositionalArgument("command", "seal, campaign, validate ou xlink");
    options.addOptions({{"root", "Racine du dépôt", "path", "."},
        {"configuration", "Configuration à figer avec seal", "path", "validation_engine/fixtures/reference.json"},
        {"lock", "Fichier de gel séparé du candidat", "path"},
        {"lock-sha256", "Empreinte du gel reçue du référentiel de campagne", "sha256"},
        {"output", "Dossier neuf pour le résultat", "path"},
        {"python", "Interpréteur de l’adaptateur FreeCAD", "path"},
        {"freecad-python", "Interpréteur embarqué FreeCAD", "path"},
        {"skip-native", "Consigner les contrôles natifs comme non exécutés"},
        {"case", "Cas du référentiel à évaluer", "id"},
        {"candidate", "Fichier candidat du cas sélectionné", "path"},
        {"electrical", "Dossier électrique JSON du candidat mixte", "path"},
        {"candidate-id", "Identifiant de la variante évaluée", "id"},
        {"candidates", "Dossier des entrées électriques de réception", "path"},
        {"native-timeout-ms", "Délai d’ouverture/sauvegarde XLink", "ms", "60000"},
        {"batch-timeout-ms", "Délai par lot de mesures XLink", "ms", "90000"},
        {"max-native-tasks", "Nombre maximal de nouvelles tâches XLink par exécution", "count", "500"},
        {"native-batch-size", "Nombre maximal de tâches par lot XLink", "count", "500"},
        {"max-native-retries", "Nombre maximal de reprises isolées par tâche XLink", "count", "0"},
        {"measurement-timeout-ms", "Budget total des lots de mesure XLink", "ms", "900000"},
        {"checkpoint", "Point de reprise XLink produit par le validateur", "file"},
        {"checkpoint-sha256", "Empreinte du point de reprise fournie par l’autorité de campagne", "sha256"}});
    options.process(app);
    try {
        const auto rootPath = QDir(options.value("root")).canonicalPath();
        require(!rootPath.isEmpty(), "Racine du dépôt introuvable");
        const QDir root(rootPath);
        const auto arguments = options.positionalArguments();
        if (arguments == QStringList{"xlink"}) {
            require(options.isSet("configuration") && options.isSet("output"), "Configuration et dossier XLink requis");
            return validateXLink(root, options);
        }
        require(arguments.size() == 1 && options.isSet("lock"), "Commande unique et chemin de gel attendus");
        const auto command = arguments.first();
        if (command == "seal") {
            const auto hash = Reference::seal(root, options.value("configuration"), options.value("lock"),
                options.isSet("python") ? options.value("python") : QString("python"), options.value("freecad-python"));
            std::puts(hash.toLatin1().constData());
            return 0;
        }
        require(command == "campaign" || command == "validate", "Commande inconnue : " + command);
        return evaluate(root, options, command == "campaign");
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
