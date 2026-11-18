#include "Admission.hpp"
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

namespace {

using namespace convergence;

QDir outputDirectory(const QDir &root, const QString &name)
{
    require(!name.isEmpty(), "Dossier de sortie requis");
    const QFileInfo info(QDir::cleanPath(root.absoluteFilePath(name)));
    const auto canonicalParent = QDir(info.absolutePath()).canonicalPath();
    require(!canonicalParent.isEmpty(), "Le dossier parent doit exister");
    const QDir parent(canonicalParent);
    const auto absolute = parent.filePath(info.fileName());
    const auto subpath = relative(root, absolute);
    require(subpath.startsWith(".runtime/") || subpath.startsWith("results/"),
            "Choisir un dossier de campagne isolé sous .runtime/ ou results/");
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

} // namespace

int main(int argc, char **argv)
{
    const QCoreApplication app(argc, argv);
    QCommandLineParser options;
    options.setApplicationDescription("Campagne électromécanique L5 bornée et reprenable");
    options.addHelpOption();
    options.addPositionalArgument("command", "run (par défaut) ou preflight");
    options.addOptions({
        {"mode", "Porte preflight : historical, explore ou final", "mode"},
        {"source-release", "Gel des outils : v2.1, ou v2 pour le rejeu historique", "release", "v2.1"},
        {"plan", "Plan de variante preflight", "path", "convergence_manager/fixtures/v21_h01_exploration.json"},
        {"receipt", "Reçu indépendant de réception V2.1", "path"},
        {"root", "Racine du dépôt", "path", "."},
        {"config", "Configuration de campagne", "path", "convergence_manager/fixtures/campaign.json"},
        {"output", "Dossier de campagne neuf ou à reprendre", "path"},
        {"l1", "Exécutable de recherche L1", "path"},
        {"l3", "Exécutable d'exploration L3", "path"},
        {"l4", "Exécutable de validation indépendante L4", "path"},
        {"python", "Interpréteur de l'adaptateur FreeCAD", "path", "python"},
        {"freecad-python", "Interpréteur embarqué de FreeCAD", "path"},
        {"steps", "Nombre maximal de transitions avant pause, -1 pour terminer", "count", "-1"}
    });
    options.process(app);
    try {
        const auto command = options.positionalArguments();
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
