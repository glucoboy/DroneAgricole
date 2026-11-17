#include "XLink.hpp"

#include "Evidence.hpp"
#include "Reference.hpp"
#include "XLinkElectrical.hpp"

#include <QCommandLineParser>
#include <QCoreApplication>
#include <QFileInfo>
#include <QJsonDocument>
#include <QLockFile>
#include <QProcess>
#include <QSaveFile>
#include <QSysInfo>
#include <QUuid>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>

namespace electromechanical_validation {
namespace {

QByteArray json(const QJsonObject &object)
{
    return QJsonDocument(object).toJson(QJsonDocument::Compact);
}

QJsonObject load(const QString &path)
{
    return parse(read(path), path);
}

QJsonObject object(const QJsonObject &value, const QString &key)
{
    require(value.value(key).isObject(), "Objet attendu : " + key);
    return value.value(key).toObject();
}

int budget(const QCommandLineParser &options, const QString &name)
{
    bool ok = false;
    const auto value = options.value(name).toInt(&ok);
    require(ok && value > 0, "Budget positif requis : " + name);
    return value;
}

struct Worker {
    QDir workspace;
    QDir run;
    QString program;

    QJsonObject operator()(const QString &name, const QJsonObject &request, int timeout) const
    {
        const auto input = run.filePath(name + ".request.json");
        const auto output = run.filePath(name + ".result.json");
        const auto log = run.filePath(name + ".log");
        writeNew(input, json(request));
        QProcess process;
        process.setWorkingDirectory(workspace.absolutePath());
        auto environment = QProcessEnvironment::systemEnvironment();
        environment.insert("QT_QPA_PLATFORM", "offscreen");
        environment.insert("PYTHONUTF8", "1");
        process.setProcessEnvironment(environment);
        process.setProcessChannelMode(QProcess::MergedChannels);
        process.setStandardOutputFile(log);
        process.start(program, {"-B", "-m", "electromechanical_engine.xlink_native", input, output});
        const auto started = process.waitForStarted(std::min(timeout, 5000));
        const auto done = started && process.waitForFinished(timeout);
        if (started && !done) {
            process.kill();
            process.waitForFinished(5000);
        }
        if (!done || !QFileInfo::exists(output)) {
            return {{"finalized", false}, {"timed_out", started && !done}, {"log", name + ".log"},
                    {"reason", !started ? process.errorString() : done ? "Processus terminé sans preuve"
                                                                    : "Budget du processus dépassé"}};
        }
        auto result = load(output);
        result.insert("log", name + ".log");
        require((process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0)
                    == (result.value("finalized") == true), "Sortie native incohérente : " + name);
        return result;
    }
};

struct Bounds {
    QString id;
    std::array<double, 3> low;
    std::array<double, 3> high;
    bool route;
};

Bounds bounds(const QString &id, const QJsonObject &item)
{
    const auto box = item.value("bounds_mm").toArray();
    require(box.size() == 2, "Boîte englobante absente : " + id);
    const auto lo = box.at(0).toArray();
    const auto hi = box.at(1).toArray();
    require(lo.size() == 3 && hi.size() == 3, "Boîte englobante invalide : " + id);
    Bounds result{id, {}, {}, item.value("route").isObject()};
    for (int axis = 0; axis < 3; ++axis) {
        require(lo.at(axis).isDouble() && hi.at(axis).isDouble(), "Cote de boîte invalide : " + id);
        result.low[axis] = lo.at(axis).toDouble();
        result.high[axis] = hi.at(axis).toDouble();
        require(result.low[axis] <= result.high[axis], "Boîte englobante inversée : " + id);
    }
    return result;
}

QString pairKey(const QString &a, const QString &b)
{
    return a < b ? a + QChar::Null + b : b + QChar::Null + a;
}

double gap(const Bounds &a, const Bounds &b)
{
    double squared = 0.0;
    for (int axis = 0; axis < 3; ++axis) {
        const auto separation = std::max({0.0, a.low[axis] - b.high[axis], b.low[axis] - a.high[axis]});
        squared += separation * separation;
    }
    return std::sqrt(squared);
}

struct Plan {
    QJsonArray tasks;
    QJsonArray unavailable;
    QJsonObject exclusions;
    qsizetype solids = 0;
    qsizetype routes = 0;
    qint64 expectedPairs = 0;
    qint64 possiblePairs = 0;
};

void addTask(Plan &plan, QJsonObject task)
{
    task.insert("id", digest(json(task)));
    plan.tasks.append(task);
}

Plan planFor(const QJsonObject &inventory, const QJsonObject &criteria)
{
    Plan plan;
    QList<Bounds> items, routes;
    const auto occurrences = object(inventory, "occurrences");
    auto routeCriteria = criteria.value("route_criteria").toObject();
    for (auto it = occurrences.begin(); it != occurrences.end(); ++it) {
        const auto occurrence = it.value().toObject();
        if (!occurrence.value("visible").toBool()) {
            plan.exclusions.insert(it.key(), "Occurrence masquée dans la représentation native");
        } else if (occurrence.value("status") != "PASS") {
            plan.unavailable.append(QJsonObject{{"id", it.key()}, {"reason", occurrence.value("reason")}});
        } else if (occurrence.value("terminal_shape") == true) {
            const auto box = bounds(it.key(), occurrence);
            items.append(box);
            if (box.route) {
                routes.append(box);
                QJsonObject task{{"kind", "route"}, {"a", it.key()}};
                if (routeCriteria.contains(it.key())) {
                    task.insert("criteria", object(routeCriteria, it.key()));
                    routeCriteria.remove(it.key());
                }
                addTask(plan, task);
            }
            addTask(plan, {{"kind", "solid"}, {"a", it.key()}});
        } else {
            plan.exclusions.insert(it.key(), occurrence.value("geometry_scope"));
        }
    }
    require(routeCriteria.isEmpty(), "Critère d’axe associé à une occurrence non mesurable");
    plan.solids = items.size();
    plan.routes = routes.size();
    plan.expectedPairs = qint64(plan.routes) * (plan.solids - plan.routes)
                         + qint64(plan.routes) * (plan.routes - 1) / 2;
    QMap<QString, QJsonObject> contacts;
    for (const auto &entry : criteria.value("contacts").toArray()) {
        const auto relation = entry.toObject();
        const auto kind = relation.value("kind").toString();
        const auto a = relation.value("inner_id").toString();
        const auto b = relation.value("outer_id").toString();
        const auto ia = occurrences.value(a).toObject();
        const auto ib = occurrences.value(b).toObject();
        require((kind == "functional_contact" || (kind == "cable_in_conduit_envelope" &&
                    relation.value("outer_representation") == "occupancy_envelope")) &&
                a != b && ia.value("terminal_shape") == true && ib.value("terminal_shape") == true &&
                ia.value("visible") == true && ib.value("visible") == true &&
                (ia.value("route").isObject() || ib.value("route").isObject()) &&
                !relation.value("justification").toString().trimmed().isEmpty(),
                "Contact autorisé invalide : " + a + ' ' + b);
        const auto key = pairKey(a, b);
        require(!contacts.contains(key), "Contact autorisé en double");
        auto authorized = relation;
        authorized.insert("pair", QJsonArray{a, b});
        contacts.insert(key, authorized);
    }
    const auto cutoff = criteria.value("clearance_mm").toDouble()
                        + criteria.value("distance_tolerance_mm").toDouble();
    std::sort(items.begin(), items.end(), [](const Bounds &a, const Bounds &b) {
        return a.low[0] == b.low[0] ? a.id < b.id : a.low[0] < b.low[0];
    });
    for (const auto &route : routes) {
        for (const auto &item : items) {
            if (item.low[0] > route.high[0] + cutoff) {
                break;
            }
            if (item.id == route.id || (item.route && item.id < route.id) || gap(route, item) > cutoff) {
                continue;
            }
            if (contacts.contains(pairKey(route.id, item.id))) {
                continue; // Evaluated explicitly even if outside the spatial filter.
            }
            addTask(plan, {{"kind", "pair"}, {"a", route.id}, {"b", item.id}});
            ++plan.possiblePairs;
        }
    }
    for (const auto &relation : contacts) {
        addTask(plan, {{"kind", "pair"}, {"a", relation.value("inner_id")}, {"b", relation.value("outer_id")},
                       {"relation", relation}});
        ++plan.possiblePairs;
    }
    return plan;
}

QJsonObject checkpoint(const QDir &directory, const QJsonObject &task, const QString &key)
{
    const auto file = directory.filePath(task.value("id").toString() + ".json");
    if (!QFileInfo::exists(file)) {
        return {};
    }
    const auto row = load(file);
    require(row.value("cache_key") == key && row.value("task").toObject() == task &&
            row.value("observation").isObject(), "Point de reprise incohérent : " + file);
    return row;
}

QJsonObject evaluateTasks(const Plan &plan, const QDir &cache, const QString &key, bool preliminary)
{
    QJsonObject counts{{"PASS", 0}, {"FAIL", 0}, {"INCONCLUSIVE", 0}, {"NOT_RUN", 0}};
    QJsonArray rows;
    int pairsAttempted = 0;
    int pairsExamined = 0;
    for (const auto &entry : plan.tasks) {
        const auto task = entry.toObject();
        auto result = checkpoint(cache, task, key);
        auto status = QString("NOT_RUN");
        if (!result.isEmpty()) {
            const auto observation = result.value("observation").toObject();
            const auto value = observation.value("status").toString();
            require(QStringList{"pass", "fail", "unknown"}.contains(value), "Statut de mesure natif invalide");
            status = value == "fail" ? "FAIL" : value == "pass" ? "PASS" : "INCONCLUSIVE";
            if (task.value("kind") == "pair") {
                ++pairsAttempted;
                if (observation.value("intersection_mm3").isDouble() && observation.value("clearance_mm").isDouble()) {
                    ++pairsExamined;
                } else {
                    status = "INCONCLUSIVE";
                }
                if (preliminary && status == "PASS") {
                    status = "INCONCLUSIVE";
                }
            }
        }
        counts.insert(status, counts.value(status).toInt() + 1);
        rows.append(QJsonObject{{"task", task}, {"status", status},
                                {"native_evidence", result.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(result)}});
    }
    return {{"status", plan.routes == 0 ? "NOT_RUN" : counts.value("FAIL").toInt() > 0 ? "FAIL" :
                      counts.value("NOT_RUN").toInt() > 0 || counts.value("INCONCLUSIVE").toInt() > 0 ||
                      !plan.unavailable.isEmpty() || preliminary ? "INCONCLUSIVE" : "PASS"},
            {"counts", counts}, {"checks", rows}, {"unavailable_occurrences", plan.unavailable},
            {"solid_occurrences", plan.solids}, {"route_occurrences", plan.routes},
            {"expected_pairs", plan.expectedPairs}, {"possible_brep_pairs", plan.possiblePairs},
            {"pairs_screened_out", plan.expectedPairs - plan.possiblePairs}, {"pairs_examined", pairsExamined},
            {"pairs_attempted", pairsAttempted}, {"pairs_unmeasurable", pairsAttempted - pairsExamined},
            {"pairs_not_run", plan.possiblePairs - pairsAttempted},
            {"filter", "Balayage X et distance euclidienne entre AABB ; seuil garde + tolérance ; contacts par identifiant exact"},
            {"scope", "Paires de solides visibles dont au moins un câble ; état nominal de la copie"},
            {"exclusions", plan.exclusions}};
}

} // namespace

int validateXLink(const QDir &workspace, const QCommandLineParser &options)
{
    const auto configPath = workspaceFile(workspace, options.value("configuration"));
    const auto configBytes = read(configPath);
    const auto configuration = parse(configBytes, configPath);
    const auto scope = configuration.value("scope").toString();
    const auto source = QDir(workspace.absoluteFilePath(configuration.value("source").toString())).canonicalPath();
    relativePath(workspace, source);
    require(!source.isEmpty() && !scope.isEmpty() && configuration.value("native_count").toInt() > 0 &&
                !configuration.value("entry").toString().isEmpty(), "Configuration XLink invalide");
    const auto criteria = object(configuration, "criteria");
    require(criteria.value("screening_only").isBool() && criteria.value("contacts").isArray() &&
            (!criteria.contains("route_criteria") || criteria.value("route_criteria").isObject()) &&
            (!configuration.contains("open_checks") || configuration.value("open_checks").isArray()),
            "Contrat des critères XLink incomplet");
    for (const auto *metric : {"clearance_mm", "distance_tolerance_mm", "volume_tolerance_mm3"}) {
        require(criteria.value(metric).isDouble() && criteria.value(metric).toDouble() >= 0,
                QString("Critère géométrique invalide : ") + metric);
    }
    const int timeout = budget(options, "native-timeout-ms");
    const int batchTimeout = budget(options, "batch-timeout-ms");
    const int maxTasks = budget(options, "max-native-tasks");
    const auto freecad = QFileInfo(options.value("freecad-python")).canonicalFilePath();
    require(!freecad.isEmpty(), "Python FreeCAD requis");
    const auto outputPath = QDir::cleanPath(workspace.absoluteFilePath(options.value("output")));
    const auto relativeOutput = relativePath(workspace, outputPath);
    require(relativeOutput.startsWith(".runtime/") && workspace.mkpath(relativeOutput), "Dossier .runtime requis");
    const QDir output(QDir(outputPath).canonicalPath());
    require(relativePath(workspace, output.absolutePath()).startsWith(".runtime/"), "Dossier réel hors .runtime");
    QLockFile mutex(output.filePath("campaign.lock"));
    require(mutex.tryLock(0), "Validation déjà en cours dans ce dossier");
    const auto attempt = "run-" + QUuid::createUuid().toString(QUuid::WithoutBraces);
    require(output.mkdir(attempt), "Dossier de tentative non créé");
    const QDir run(output.filePath(attempt));
    const Worker worker{workspace, run, freecad};
    const auto copy = output.filePath("copy");
    const QJsonObject copyRequest{{"copy", copy}};
    const auto graphPath = options.value("electrical").isEmpty() ? QString{} : workspaceFile(workspace, options.value("electrical"));
    const auto graphBytes = graphPath.isEmpty() ? QByteArray{} : read(graphPath);
    const auto graph = graphBytes.isEmpty() ? QJsonObject{} : parse(graphBytes, graphPath);
    const auto registerPath = configuration.value("equipment_register").toString();
    const auto mappingPath = configuration.value("equipment_mapping").toString();
    require(registerPath.isEmpty() || mappingPath.isEmpty(), "Une seule source pour le mapping des occurrences");
    QJsonObject pins{{"configuration", digest(configBytes)}, {"validator", fileDigest(QCoreApplication::applicationFilePath())},
                     {"freecad_python", fileDigest(freecad)}};
    QMap<QString, QString> inputs;
    inputs.insert(configPath, digest(configBytes));
    if (!graphPath.isEmpty()) {
        inputs.insert(graphPath, digest(graphBytes));
        pins.insert("electrical", digest(graphBytes));
        const auto provenance = object(graph, "source_sha256");
        for (auto it = provenance.begin(); it != provenance.end(); ++it) {
            inputs.insert(workspaceFile(workspace, it.key()), it.value().toString());
        }
    }
    for (const auto *file : {"electromechanical_engine/xlink_native.py", "electromechanical_engine/freecad.py",
                             "electromechanical_engine/freecad_worker.py",
                             ".agents/skills/electromechanical-integration/scripts/workspace_guard.py",
                             ".agents/skills/electromechanical-integration/scripts/freecad_geometry.py",
                             "hardware/mecanique/cartographe/verification/cable_workbench_prototype.py"}) {
        const auto path = workspaceFile(workspace, file);
        const auto sha = fileDigest(path);
        inputs.insert(path, sha);
        pins.insert(file, sha);
    }
    if (!registerPath.isEmpty()) {
        require(!graph.isEmpty(), "Rapport électrique L2 requis avec le registre des équipements");
        const auto path = workspaceFile(workspace, registerPath);
        const auto sha = fileDigest(path);
        require(inputs.value(path) == sha, "Registre des équipements absent ou divergent du gel L2");
        pins.insert("equipment_register", sha);
    }
    for (const auto &binding : {qMakePair(QString("criteria"), criteria.value("source").toString()),
                                qMakePair(QString("equipment_mapping"), mappingPath)}) {
        if (!binding.second.isEmpty()) {
            const auto path = workspaceFile(workspace, binding.second);
            const auto sha = fileDigest(path);
            inputs.insert(path, sha);
            pins.insert(binding.first, sha);
        }
    }
    require(graph.isEmpty() || !registerPath.isEmpty() || !mappingPath.isEmpty(),
            "Une projection d’occurrences est requise avec le graphe L2");
    for (auto it = inputs.begin(); it != inputs.end(); ++it) {
        require(fileDigest(it.key()) == it.value(), "Entrée modifiée : " + it.key());
    }

    QJsonObject phases, report{{"schema", "drone-agricole.v21.xlink.coverage.v1"}, {"scope", scope},
                               {"criteria", criteria}, {"pins", pins}, {"attempt", attempt}};
    QJsonObject receipt, saved, inventory, electrical, geometry;
    const auto copyRecord = output.filePath("saved.json");
    const auto checkReceipt = [&](const QJsonObject &row) {
        const auto files = object(row, "inputs_sha256");
        qsizetype natives = 0;
        for (auto it = files.begin(); it != files.end(); ++it) {
            natives += it.key().endsWith(".FCStd", Qt::CaseInsensitive);
        }
        return natives == configuration.value("native_count").toInt() &&
               row.value("entry") == configuration.value("entry") &&
               QDir::fromNativeSeparators(row.value("source_root").toString()) == source &&
               QDir::fromNativeSeparators(row.value("copy_root").toString()) == copy;
    };
    if (QFileInfo::exists(copyRecord)) {
        saved = load(copyRecord);
        require(saved.value("copy_configuration") == pins.value("configuration"), "La configuration de copie a changé");
        receipt = load(QDir(copy).filePath("experiment.json"));
        require(checkReceipt(receipt), "Reçu de copie divergent à la reprise");
        phases.insert("reuse_saved", true);
    } else {
        auto stageRequest = copyRequest;
        stageRequest.insert("action", "stage");
        stageRequest.insert("source", source);
        stageRequest.insert("entry", configuration.value("entry"));
        stageRequest.insert("extras", configuration.value("extras").toArray());
        receipt = worker("stage", stageRequest, timeout);
        phases.insert("stage", receipt);
        if (receipt.value("finalized") == true) {
            auto saveRequest = copyRequest;
            saveRequest.insert("action", "save");
            if (checkReceipt(receipt)) {
                saved = worker("save", saveRequest, timeout);
                saved.insert("copy_configuration", pins.value("configuration"));
                phases.insert("save", saved);
                if (saved.value("finalized") == true) {
                    writeNew(copyRecord, json(saved));
                }
            } else {
                phases.insert("save", QJsonObject{{"finalized", false}, {"reason", "Nombre de fichiers hors référentiel"}});
            }
        }
    }
    const auto originals = receipt.value("inputs_sha256").toObject();
    const auto nativeHashes = saved.value("after_sha256").toObject();
    const auto rootFile = configuration.value("entry").toString();
    QJsonObject nativeRequest{{"copy", copy}, {"native_sha256", nativeHashes}};
    bool available = false;
    if (saved.value("finalized") == true) {
        nativeRequest.insert("action", "inventory");
        inventory = worker("inventory", nativeRequest, timeout);
        phases.insert("inventory", QJsonObject{{"finalized", inventory.value("finalized")},
                                               {"reason", inventory.value("reason")}, {"log", "inventory.log"}});
        available = inventory.value("finalized") == true && inventory.value("inventory_complete") == true;
    }
    QJsonObject cacheIdentity{{"pins", pins}, {"root_sha256", nativeHashes.value(rootFile)}, {"closure_sha256", nativeHashes}};
    if (available) {
        cacheIdentity.insert("environment", inventory.value("environment"));
    }
    const auto cacheKey = digest(json(cacheIdentity));
    QJsonArray t0Inputs;
    for (auto it = inputs.begin(); it != inputs.end(); ++it) {
        t0Inputs.append(inputReference("input-" + QString::number(t0Inputs.size() + 1),
                                      relativePath(workspace, it.key()), it.value()));
    }
    if (!originals.isEmpty()) {
        t0Inputs.append(inputReference("root", relativePath(workspace, QDir(source).filePath(rootFile)),
                                      originals.value(rootFile).toString()));
    }
    architecture_decision::Evidence t0(run.absolutePath(), t0Inputs,
        {{"scope", scope}, {"criteria", criteria}, {"cache_key", cacheKey},
         {"native_timeout_ms", timeout}, {"batch_timeout_ms", batchTimeout}, {"max_native_tasks", maxTasks}},
        {{"os", QSysInfo::prettyProductName()}, {"architecture", QSysInfo::currentCpuArchitecture()},
         {"qt_version", qVersion()}, {"validator_sha256", pins.value("validator")}},
        {"v21_xlink", "validation_core", scope, "ELECTROMECHANICAL_VALIDATION",
         "Validation XLink lancée", "Couverture XLink publiée", "V21_XLINK_BLOCKED"});

    if (available) {
        require(inventory.value("worker_id") != saved.value("worker_id") &&
                inventory.value("after_sha256").toObject() == nativeHashes,
                "Réouverture indépendante incohérente");
        if (!graph.isEmpty()) {
            QJsonObject projection;
            if (mappingPath.isEmpty()) {
                projection = worker("projection", {{"action", "projection"},
                    {"register", workspace.absoluteFilePath(registerPath)}}, timeout);
                require(projection.value("finalized") == true &&
                        projection.value("register_sha256") == pins.value("equipment_register"), "Projection CSV incohérente");
            } else {
                projection = load(workspaceFile(workspace, mappingPath));
            }
            projection.insert("native_root", relativePath(workspace, source));
            electrical = joinXLinkElectrical(graph, projection, inventory, originals);
        }
        const auto plan = planFor(inventory, criteria);
        const auto checkpointPath = "cache/" + cacheKey;
        require(output.mkpath(checkpointPath), "Dossier de reprise non créé");
        const QDir checkpoints(output.filePath(checkpointPath));
        QMap<QString, int> earlier;
        for (const auto &previous : output.entryList({"run-*"}, QDir::Dirs)) {
            const auto file = QDir(output.filePath(previous)).filePath("scheduled.json");
            if (!QFileInfo::exists(file)) {
                continue;
            }
            const auto schedule = load(file);
            if (schedule.value("cache_key") == cacheKey) {
                for (const auto &entry : schedule.value("ids").toArray()) {
                    ++earlier[entry.toString()];
                }
            }
        }
        QList<QJsonObject> pending;
        qsizetype resumed = 0;
        for (const auto &entry : plan.tasks) {
            const auto task = entry.toObject();
            if (checkpoint(checkpoints, task, cacheKey).isEmpty()) {
                pending.append(task);
            } else {
                ++resumed;
            }
        }
        std::stable_sort(pending.begin(), pending.end(), [&earlier](const QJsonObject &a, const QJsonObject &b) {
            const auto va = earlier.value(a.value("id").toString());
            const auto vb = earlier.value(b.value("id").toString());
            if (va != vb) {
                return va < vb;
            }
            return (a.value("kind") == "route") > (b.value("kind") == "route");
        });
        QJsonArray batch, ids;
        for (qsizetype i = 0; i < std::min<qsizetype>(pending.size(), maxTasks); ++i) {
            batch.append(pending[i]);
            ids.append(pending[i].value("id"));
        }
        if (!batch.isEmpty()) {
            auto request = nativeRequest;
            request.insert("action", "measure");
            request.insert("tasks", batch);
            request.insert("criteria", criteria);
            request.insert("environment", inventory.value("environment"));
            request.insert("checkpoints", checkpoints.absolutePath());
            request.insert("cache_key", cacheKey);
            const auto result = worker("batch", request, batchTimeout);
            const auto logFile = run.filePath("batch.log");
            const auto batchLog = QFileInfo::exists(logFile) ? read(logFile) : QByteArray{};
            // Batches publish each completed measurement before the next one starts.
            // Only the first unresolved task may have consumed the remaining time.
            QJsonArray attempted;
            for (const auto &entry : batch) {
                const auto task = entry.toObject();
                const auto id = task.value("id");
                if (batchLog.contains(id.toString().toLatin1() + ": ")) {
                    attempted.append(id);
                }
                if (checkpoint(checkpoints, task, cacheKey).isEmpty()) {
                    break;
                }
            }
            writeNew(run.filePath("scheduled.json"), json({{"cache_key", cacheKey}, {"ids", attempted}, {"scheduled", ids}}));
            phases.insert("batch", QJsonObject{{"finalized", result.value("finalized")}, {"timed_out", result.value("timed_out")},
                {"reason", result.value("reason")}, {"log", "batch.log"}, {"log_sha256", digest(batchLog)},
                {"started", attempted.size()}, {"scheduled", batch.size()}});
        }
        geometry = evaluateTasks(plan, checkpoints, cacheKey, criteria.value("screening_only").toBool(true));
        geometry.insert("resumed_tasks", resumed);
    }

    QJsonObject integrity;
    if (!originals.isEmpty()) {
        integrity = worker("verify", {{"action", "verify"}, {"copy", copy}}, timeout);
        require(integrity.value("finalized") == true && integrity.value("sources_unchanged") == true &&
                (nativeHashes.isEmpty() || integrity.value("after_sha256").toObject() == nativeHashes),
                "Échec de la vérification finale des sources ou de la copie");
    }
    for (auto it = inputs.begin(); it != inputs.end(); ++it) {
        require(fileDigest(it.key()) == it.value(), "Entrée modifiée durant la mesure : " + it.key());
    }
    const auto reopened = available && saved.value("save_performed") == true && inventory.value("recompute_ok") == true;
    report.insert("closure", QJsonObject{{"root", rootFile}, {"source_root", configuration.value("source")},
        {"source_sha256", originals}, {"saved_sha256", nativeHashes}, {"expected_native_count", configuration.value("native_count")},
        {"cache_key", cacheKey}, {"saved_worker", saved.value("worker_id")}, {"reopened_worker", inventory.value("worker_id")},
        {"saved_pid", saved.value("pid")}, {"reopened_pid", inventory.value("pid")}, {"reopened", reopened},
        {"status", reopened ? "PASS" : available ? "INCONCLUSIVE" : "NOT_RUN"}, {"integrity", integrity}});
    report.insert("phases", phases);
    report.insert("electrical", electrical.isEmpty() ? QJsonObject{{"status", "NOT_RUN"}} : electrical);
    report.insert("geometry", geometry.isEmpty() ? QJsonObject{{"status", "NOT_RUN"}} : geometry);
    const auto open = configuration.value("open_checks").toArray();
    report.insert("open_checks", open);
    const auto complete = reopened && electrical.value("status") == "PASS" && geometry.value("status") == "PASS" && open.isEmpty();
    const auto verdict = !available ? "V21_XLINK_BLOCKED" : complete ? "V21_XLINK_PASS" : "V21_XLINK_CONDITIONAL";
    report.insert("verdict", verdict);
    report.insert("finalized", true);
    QMap<QString, QString> artifacts;
    artifacts.insert("campaign.json", writeNew(run.filePath("campaign.json"), json(report)));
    for (const auto *file : {"stage.result.json", "save.result.json", "inventory.result.json",
                             "projection.result.json", "batch.request.json", "scheduled.json", "verify.result.json"}) {
        if (QFileInfo::exists(run.filePath(file))) {
            artifacts.insert(file, fileDigest(run.filePath(file)));
        }
    }
    t0.finalize(report, artifacts);
    std::printf("%s %s\n", verdict, qPrintable(relativePath(workspace, run.absolutePath())));
    return !available ? 2 : complete ? 0 : 3;
}

} // namespace electromechanical_validation
