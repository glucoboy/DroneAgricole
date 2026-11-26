#include "A6Transaction.hpp"
#include "Admission.hpp"
#include "AuthorityReview.hpp"
#include "Campaign.hpp"
#include "Files.hpp"
#include "ProcessBackend.hpp"
#include "Evidence.hpp"

#include <QCommandLineParser>
#include <QCoreApplication>
#include <QFileInfo>
#include <QJsonArray>
#include <QLockFile>
#include <QTemporaryDir>
#include <cstdio>
#include <filesystem>

namespace {

using namespace convergence;

bool containsDirectory(const QDir &ancestor, QDir child)
{
    do {
        if (std::filesystem::equivalent(ancestor.filesystemAbsolutePath(), child.filesystemAbsolutePath())) {
            return true;
        }
    } while (!child.isRoot() && child.cdUp());
    return false;
}

QDir outputDirectory(const QDir &root, const QString &name, const QString &sandbox = {})
{
    require(!name.isEmpty(), "Dossier de sortie requis");
    const auto requested = QDir::cleanPath(root.absoluteFilePath(name));
    require(sandbox.isEmpty() || !hasRedirectedComponent(root, requested), "Chemin de sortie V3 redirigé");
    const QFileInfo info(requested);
    const auto canonicalParent = QDir(info.absolutePath()).canonicalPath();
    require(!canonicalParent.isEmpty(), "Le dossier parent doit exister");
    const QDir parent(canonicalParent);
    const auto absolute = parent.filePath(info.fileName());
    const auto subpath = relative(root, absolute);
    require(subpath.startsWith(".runtime/") || subpath.startsWith("results/"),
            "Choisir un dossier de campagne isolé sous .runtime/ ou results/");
    if (!sandbox.isEmpty()) {
        const QDir reference(sandbox);
        require(!containsDirectory(reference, parent) &&
                (!info.isDir() || !containsDirectory(QDir(absolute), reference)),
                "La sortie L5 et le sandbox XLink doivent être disjoints");
    }
    require(!info.isSymLink() && !info.isJunction() && (info.isDir() || parent.mkdir(info.fileName())) &&
            QDir(absolute).canonicalPath() == absolute, "Sortie de campagne inaccessible ou redirigée");
    return QDir(absolute);
}

void publishEvidence(const QDir &output, const QJsonObject &manifest)
{
    const auto terminal = output.filePath("t0_run_manifest.json");
    if (QFileInfo::exists(terminal)) {
        verifyEvidence(output, "L5");
        return;
    }

    // Evidence writes its terminal manifest last. Preparing a complete copy first
    // lets a resumed campaign replace any interrupted publication safely.
    QTemporaryDir staging(output.filePath(".t0-XXXXXX"));
    require(staging.isValid(), "Préparation de la preuve T0 impossible");
    const QDir stage(staging.path());
    QMap<QString, QString> published;
    const auto add = [&](const QString &name, const QJsonValue &expected = QJsonValue()) {
        if (name.isEmpty() || published.contains(name)) {
            return;
        }
        const auto source = fileInside(output, name);
        require(relative(output, source) == name && stage.mkpath(QFileInfo(name).path()), "Artefact hors campagne");
        const auto bytes = read(source);
        const auto hash = digest(bytes);
        require(expected.isNull() || expected.isUndefined() || expected == hash, "Preuve modifiée : " + name);
        published.insert(name, write(stage.filePath(name), bytes));
    };
    for (const auto &name : {"manifest.json", "checkpoint.json", "selection.json", "campaign.json"}) {
        add(name);
    }
    add("authority/l4-lock.json", manifest.value("reference_sha256"));
    const auto checkpoint = load(output.filePath("checkpoint.json"));
    const auto addReceipt = [&](const QJsonObject &result, const QString &field) {
        add(result.value(field).toString(), result.value(field + "_sha256"));
    };
    const auto addValidation = [&](const QJsonObject &result, const QString &lot) {
        const auto terminalName = result.value("evidence").toString();
        if (terminalName.isEmpty()) {
            return;
        }
        addReceipt(result, "evidence");
        const auto folder = QFileInfo(terminalName).path();
        const QDir child(output.filePath(folder));
        const auto nested = verifyEvidence(child, lot).value("artifacts").toObject();
        add(folder + "/artifacts.json");
        for (auto it = nested.begin(); it != nested.end(); ++it) {
            add(folder + '/' + it.key(), it.value());
        }
    };
    for (const auto &entry : checkpoint.value("attempts").toArray()) {
        addReceipt(entry.toObject(), "receipt");
    }
    for (const auto &entry : checkpoint.value("portfolios").toArray()) {
        const auto portfolio = entry.toObject();
        addReceipt(portfolio.value("build").toObject(), "receipt");
        const auto validation = portfolio.value("validation").toObject();
        addReceipt(validation, "report");
        addValidation(validation, "L4");
    }
    for (const auto &rows : checkpoint.value("operations").toObject()) {
        for (const auto &entry : rows.toArray()) {
            const auto row = entry.toObject();
            if (row.value("state") == "COMPLETED") {
                add(row.value("path").toString() + "/operation.json", row.value("sha256"));
            }
        }
    }
    const auto last = checkpoint.value("last_consolidated").toObject();
    add(last.value("path").toString(), last.value("sha256"));
    addValidation(checkpoint.value("exploration").toObject(), "L3");

    QJsonArray inputs;
    int sequence = 0;
    const auto files = manifest.value("files").toObject();
    for (auto it = files.begin(); it != files.end(); ++it) {
        inputs.append(QJsonObject{{"input_id", "frozen-" + QString::number(++sequence)}, {"kind", "other"},
            {"reference", QJsonObject{{"path", it.key()}}}, {"checksums", QJsonObject{{"sha256", it.value()}}}});
    }
    inputs.append(QJsonObject{{"input_id", "l4-lock"}, {"kind", "other"},
        {"reference", QJsonObject{{"path", manifest.value("reference_lock")}}},
        {"checksums", QJsonObject{{"sha256", manifest.value("reference_sha256")}}}});
    const QJsonObject software{{"qt_version", manifest.value("qt")}, {"os", manifest.value("os")},
        {"architecture", manifest.value("architecture")}, {"tools", manifest.value("tools")}};
    architecture_decision::Evidence evidence(stage.absolutePath(), inputs, manifest.value("parameters").toObject(),
        software, {"l5", "convergence_core", "synthetic", "SYNTHETIC_BENCH",
                   "Campagne de convergence ouverte", "Verdict et preuves de convergence publiés"});
    evidence.finalize(load(output.filePath("campaign.json")), published);
    verifyEvidence(stage, "L5");
    for (const auto &name : {"run_request.json", "t0_metrics.json", "events.jsonl", "artifacts.json", "t0_run_manifest.json"}) {
        write(output.filePath(name), read(stage.filePath(name)));
    }
    verifyEvidence(output, "L5");
}

int run(const QCommandLineParser &options)
{
    const auto rootPath = QDir(options.value("root")).canonicalPath();
    require(!rootPath.isEmpty(), "Racine de travail absente");
    const QDir root(rootPath);
    const auto configPath = fileInside(root, options.value("config"));
    const auto config = load(configPath);
    require(!config.value("schema").toString().startsWith("v3."),
            "Un contrat V3 requiert la commande v3-admission");
    require(config.value("version") == 1, "Version de campagne invalide");
    bool validSteps = false;
    const auto steps = options.value("steps").toInt(&validSteps);
    require(validSteps && steps >= -1, "Nombre d'étapes invalide");
    const auto output = outputDirectory(root, options.value("output"));
    QLockFile lock(output.filePath(".publication.lock"));
    lock.setStaleLockTime(0);
    require(lock.tryLock(), "Campagne ou publication déjà en cours");
    if (!QFileInfo::exists(output.filePath("manifest.json"))) {
        const auto entries = output.entryList(QDir::AllEntries | QDir::Hidden | QDir::NoDotAndDotDot);
        for (const auto &entry : entries) {
            require(entry == ".publication.lock" || entry == "authority",
                    "Dossier de sortie déjà occupé : " + entry);
        }
    }
    ProcessBackend backend(root, output, config, {options.value("l1"), options.value("l3"),
        options.value("l4"), options.value("python"), options.value("freecad-python")});
    const auto manifest = backend.freeze(configPath);
    const auto code = Campaign(output, config, manifest, backend).run(steps);
    if (code == 4) {
        return code;
    }
    backend.verify();
    backend.verifyConsolidation(load(output.filePath("campaign.json")));
    publishEvidence(output, manifest);
    const auto result = load(output.filePath("campaign.json"));
    std::printf("%s %s\n", result.value("verdict").toString().toLatin1().constData(),
                result.value("decision").toString().toLatin1().constData());
    return code;
}

QString directA6Path(const QDir &root, const QString &name)
{
    const auto path = QDir::fromNativeSeparators(name);
    require(!path.isEmpty() && QDir::cleanPath(path) == path, "A6_PATH_NOT_CANONICAL");
    const auto absolute = root.absoluteFilePath(path);
    if (absolute != root.absolutePath()) {
#ifdef Q_OS_WIN
        require(absolute.size() > 3 && absolute.mid(1, 2) == ":/", "A6_PATH_VOLUME_DENIED");
        const QDir volume(absolute.first(3));
#else
        const QDir volume(QStringLiteral("/"));
#endif
        require(!hasRedirectedComponent(volume, absolute), "A6_PATH_REDIRECTED");
    }
    return absolute;
}

bool overlaps(const QString &left, const QString &right)
{
#ifdef Q_OS_WIN
    constexpr auto caseSensitivity = Qt::CaseInsensitive;
#else
    constexpr auto caseSensitivity = Qt::CaseSensitive;
#endif
    return left.compare(right, caseSensitivity) == 0 || left.startsWith(right + '/', caseSensitivity) ||
           right.startsWith(left + '/', caseSensitivity);
}

int runA6(const QCommandLineParser &options, bool mutation, const QDir &root, const QDir &sandbox,
          const QByteArray &bytes, const QJsonObject &request)
{
    require(mutation, "A6_REQUIRES_V3_BUILD");
    require(!options.isSet("freecad-python") && !options.isSet("t0-validator"), "A6_TOOL_OVERRIDE_DENIED");
    require(directA6Path(QDir::current(), options.value("root")) == root.absolutePath(), "A6_ROOT_REDIRECTED");
    const auto input = directA6Path(root, options.value("request"));
    require(fileInside(root, input) == input &&
            std::filesystem::hard_link_count(QFileInfo(input).filesystemFilePath()) == 1, "A6_REQUEST_PATH_DENIED");
    require(directA6Path(root, options.value("sandbox")) == sandbox.absolutePath() &&
            relative(root, sandbox.absolutePath()).startsWith(".runtime/"), "A6_SANDBOX_NOT_PRIVATE");
    const auto requestedOutput = directA6Path(root, options.value("output"));
    const auto raw = request.value("submission").toObject().value("raw_root").toString();
    const auto trust = options.value("a5-trust");
    require(relative(root, requestedOutput).startsWith(".runtime/") &&
            !overlaps(requestedOutput, input) && !overlaps(requestedOutput, sandbox.absolutePath()) &&
            (raw.isEmpty() || !overlaps(requestedOutput, directA6Path(root, raw))) &&
            (trust.isEmpty() || !overlaps(requestedOutput, QFileInfo(directA6Path(QDir::current(), trust)).absolutePath())),
            "A6_OUTPUT_NOT_PRIVATE_OR_OVERLAPPING");
    const auto output = outputDirectory(root, requestedOutput, sandbox.absolutePath());
    QLockFile lock(output.filePath(".publication.lock"));
    require(!hasRedirectedComponent(output, output.filePath(".publication.lock")) && lock.tryLock(),
            "A6_OUTPUT_BUSY");
    require(output.entryList(QDir::AllEntries | QDir::System | QDir::Hidden | QDir::NoDotAndDotDot) ==
            QStringList{".publication.lock"}, "A6_OUTPUT_NOT_EMPTY");
    return runAuthorizedTransaction(root, sandbox, output, input, bytes, request, trust, options.value("a5-trust-sha256"));
}

int runV3(const QCommandLineParser &options, bool mutation)
{
    for (const auto &legacy : {"mode", "receipt", "plan", "source-release", "config", "steps",
                              "l1", "l3", "l4", "python"}) {
        require(!options.isSet(legacy), "Option incompatible avec V3 : " + QString(legacy));
    }
    require(options.isSet("request") && options.isSet("sandbox"), "Demande et sandbox XLink requis");
    const auto rootPath = QDir(options.value("root")).canonicalPath();
    require(!rootPath.isEmpty(), "Racine de travail absente");
    const QDir root(rootPath);
    const auto requestedSandbox = QDir::cleanPath(root.absoluteFilePath(options.value("sandbox")));
    require(!hasRedirectedComponent(root, requestedSandbox), "Chemin de sandbox XLink redirigé");
    const auto sandboxPath = QDir(requestedSandbox).canonicalPath();
    require(!sandboxPath.isEmpty(), "Sandbox XLink absent");
    relative(root, sandboxPath);
    const auto requestPath = fileInside(root, options.value("request"));
    require(!hasRedirectedComponent(root, root.absoluteFilePath(options.value("request"))), "Demande V3 redirigée");
    const auto bytes = read(requestPath);
    const auto request = parseUniqueObject(bytes, requestPath);
    if (request.value("schema") == a6AdmissionSchema)
        return runA6(options, mutation, root, QDir(sandboxPath), bytes, request);
    require(mutation == options.isSet("freecad-python") && mutation == options.isSet("t0-validator"),
            "v3-build requiert FreeCAD Python et le validateur T0 indépendant");
    const auto output = outputDirectory(root, options.value("output"), sandboxPath);
    QLockFile lock(output.filePath(".publication.lock"));
    lock.setStaleLockTime(0);
    require(lock.tryLock(), "Admission V3 déjà en cours");
    if (request.value("schema") == a5AdmissionSchema) {
        require(output.entryList(QDir::AllEntries | QDir::System | QDir::Hidden | QDir::NoDotAndDotDot) ==
                QStringList{".publication.lock"}, "Un dossier de sortie neuf est requis pour chaque admission A.5");
        const auto report = verifyAuthorityReview(root, QDir(sandboxPath), request, digest(bytes),
            options.value("a5-trust"), options.value("a5-trust-sha256"), mutation);
        write(output.filePath("admission.json"), report);
        return report.value("admission").toObject().value("decision") == "ALLOW" ? 0 : 2;
    }
    require(!options.isSet("a5-trust") && !options.isSet("a5-trust-sha256"), "Contrat d'admission A.5 requis");
    if (mutation) {
        const auto result = ProcessBackend::buildV3(root, QDir(sandboxPath), output, bytes, request,
            options.value("freecad-python"), options.value("t0-validator"));
        const auto status = result.value("status").toString();
        std::printf("%s\n", status.toLatin1().constData());
        return status == "PASS" ? 0 : status == "FAIL" ? 2 : status == "INCONCLUSIVE" ? 4 : 3;
    }
    const auto entries = output.entryList(QDir::AllEntries | QDir::System | QDir::Hidden | QDir::NoDotAndDotDot);
    require(entries == QStringList{".publication.lock"}, "Un dossier de sortie neuf est requis pour chaque admission V3");

    auto report = ProcessBackend::buildV3(root, QDir(sandboxPath), request);
    report.insert("request_sha256", digest(bytes));
    write(output.filePath("admission.json"), report);
    const auto decision = report.value("admission").toObject().value("decision").toString();
    const auto status = report.value("dispatch_status").toString();
    std::printf("%s %s\n", decision.toLatin1().constData(), status.toLatin1().constData());
    if (status == "READ_ONLY") {
        return 0;
    }
    return status == "NOT_IMPLEMENTED" ? 3 : 2;
}

int convergeV3(const QCommandLineParser &options)
{
    require(options.isSet("request") && options.isSet("observation") && options.isSet("freecad-python") &&
            options.isSet("t0-validator") && !options.isSet("sandbox"), "Entrées de convergence V3 incomplètes");
    for (const auto &legacy : {"mode", "receipt", "plan", "source-release", "config", "steps", "l1", "l3", "l4"})
        require(!options.isSet(legacy), QString("Option hors mode v3-converge : ") + legacy);
    const auto rootPath = QDir(options.value("root")).canonicalPath();
    require(!rootPath.isEmpty(), "Racine de travail absente");
    const QDir root(rootPath);
    const auto output = outputDirectory(root, options.value("output"));
    require(!hasRedirectedComponent(root, root.absoluteFilePath(options.value("output"))), "Sortie de convergence redirigée");
    QLockFile lock(output.filePath(".publication.lock"));
    lock.setStaleLockTime(0);
    require(lock.tryLock(), "Convergence V3 déjà en cours");
    require(output.entryList(QDir::AllEntries | QDir::Hidden | QDir::System | QDir::NoDotAndDotDot) ==
            QStringList{".publication.lock"}, "Un dossier de convergence V3 neuf est requis");
    const auto result = Campaign::runV3(root, output, options.value("request"), options.value("observation"),
                                       options.value("base-problem"), options.value("freecad-python"),
                                       options.value("python"), options.value("t0-validator"));
    const auto verdict = result.value("verdict").toString();
    std::printf("%s\n", verdict.toLatin1().constData());
    return verdict == "V3_C_PASS" ? 0 : 4;
}

} // namespace

int main(int argc, char **argv)
{
    const QCoreApplication app(argc, argv);
    QCommandLineParser options;
    options.setApplicationDescription("Campagne électromécanique L5 bornée et reprenable");
    options.addHelpOption();
    options.addPositionalArgument("command", "run (par défaut), preflight, v3-admission, v3-build ou v3-converge");
    options.addOptions({
        {"mode", "Porte preflight : historical, explore ou final", "mode"},
        {"source-release", "Gel des outils : v2.1, ou v2 pour le rejeu historique", "release", "v2.1"},
        {"plan", "Plan de variante preflight", "path", "convergence_manager/fixtures/v21_h01_exploration.json"},
        {"receipt", "Reçu indépendant de réception V2.1", "path"},
        {"root", "Racine du dépôt", "path", "."},
        {"config", "Configuration de campagne", "path", "convergence_manager/fixtures/campaign.json"},
        {"request", "Demande d'admission ou plan de mutation V3", "path"},
        {"observation", "Observation de référence FreeCAD pour v3-converge", "path"},
        {"base-problem", "Problème T1 scellé pour un rejeu T2", "path"},
        {"sandbox", "Copie de référence XLink pour la demande V3", "path"},
        {"output", "Dossier de campagne neuf ou à reprendre", "path"},
        {"l1", "Exécutable de recherche L1", "path"},
        {"l3", "Exécutable d'exploration L3", "path"},
        {"l4", "Exécutable de validation indépendante L4", "path"},
        {"python", "Interpréteur de l'adaptateur FreeCAD", "path", "python"},
        {"freecad-python", "Interpréteur embarqué de FreeCAD", "path"},
        {"t0-validator", "Validateur indépendant de preuve T0 pour v3-build", "path"},
        {"a5-trust", "Configuration de confiance A.5 indépendante des relevés", "path"},
        {"a5-trust-sha256", "Empreinte de confiance A.5 réservée au banc TEST_ONLY", "sha256"},
        {"steps", "Nombre maximal de transitions avant pause, -1 pour terminer", "count", "-1"}
    });
    options.process(app);
    try {
        const auto command = options.positionalArguments();
        require((!options.isSet("a5-trust") && !options.isSet("a5-trust-sha256")) ||
                command == QStringList{"v3-admission"} || command == QStringList{"v3-build"},
                "Les options de confiance requièrent v3-admission ou v3-build");
        if (command == QStringList{"v3-converge"}) {
            return convergeV3(options);
        }
        require(!options.isSet("observation") && !options.isSet("base-problem"),
                "Les observations de référence requièrent v3-converge");
        if (command == QStringList{"v3-admission"} || command == QStringList{"v3-build"}) {
            return runV3(options, command.front() == "v3-build");
        }
        require(!options.isSet("request") && !options.isSet("sandbox") && !options.isSet("t0-validator"),
                "Les options de demande V3 requièrent v3-admission ou v3-build");
        if (command.isEmpty() || command == QStringList{"run"}) {
            require(!options.isSet("mode") && !options.isSet("receipt") && !options.isSet("plan") &&
                    !options.isSet("source-release"),
                    "Les options de porte requièrent la commande preflight");
            return run(options);
        }
        require(command == QStringList{"preflight"}, "Commande inconnue");
        const auto mode = options.value("mode");
        require(QStringList{"historical", "explore", "final"}.contains(mode) &&
                (mode == "final" || !options.isSet("receipt")) && (mode == "explore" || !options.isSet("plan")),
                "Options preflight incompatibles");
        bool validSteps = false;
        const auto steps = options.value("steps").toInt(&validSteps);
        require(validSteps && steps >= -1 && (mode == "explore" || steps == -1), "Nombre d'étapes invalide");
        const auto rootPath = QDir(options.value("root")).canonicalPath();
        require(!rootPath.isEmpty(), "Racine de travail absente");
        const QDir root(rootPath);
        const auto output = outputDirectory(root, options.value("output"));
        QLockFile lock(output.filePath(".publication.lock"));
        lock.setStaleLockTime(0);
        require(lock.tryLock(), "Publication déjà en cours");
        const auto checkpoint = output.filePath("preflight.json");
        const auto entries = output.entryList(QDir::AllEntries | QDir::System | QDir::Hidden | QDir::NoDotAndDotDot);
        for (const auto &entry : entries) {
            const QFileInfo info(output.filePath(entry));
            require(entry == ".publication.lock" ||
                    (entry == "preflight.json" && info.isFile() && !info.isSymLink()), "Sortie déjà occupée : " + entry);
        }
        const auto report = preflight(root, output, mode, options.value("plan"), options.value("receipt"), steps,
                                      options.value("source-release"));
        const auto previous = QFileInfo::exists(checkpoint) ? load(checkpoint) : QJsonObject{};
        if (previous != report) {
            require(previous.isEmpty() || mode == "explore", "Sortie déjà utilisée par un autre préflight");
            write(checkpoint, report);
        }
        const auto verdict = report.value("verdict").toString();
        std::printf("%s\n", verdict.toLatin1().constData());
        if (report.value("campaign_state") == "PAUSED") {
            return 4;
        }
        return verdict == "EXPLORATION_ALLOWED" ? 0 : 2;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
