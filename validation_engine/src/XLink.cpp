#include "XLink.hpp"

#include "Evidence.hpp"
#include "Reference.hpp"
#include "XLinkElectrical.hpp"

#include <QCommandLineParser>
#include <QCoreApplication>
#include <QElapsedTimer>
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
#include <limits>

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

int budget(const QCommandLineParser &options, const QString &name, int minimum = 1)
{
    bool ok = false;
    const auto value = options.value(name).toInt(&ok);
    require(ok && value >= minimum, "Budget invalide : " + name);
    return value;
}

struct Worker {
    QDir workspace;
    QDir run;
    QString program;
    QMap<QString, QString> digests;

    QJsonObject operator()(const QString &name, const QJsonObject &request, int timeout)
    {
        const auto requestName = name + ".request.json";
        const auto resultName = name + ".result.json";
        const auto input = run.filePath(requestName);
        const auto output = run.filePath(resultName);
        const auto log = run.filePath(name + ".log");
        const auto requestSha = writeNew(input, json(request));
        QProcess process;
        process.setWorkingDirectory(workspace.absolutePath());
        auto environment = QProcessEnvironment::systemEnvironment();
        const auto channel = QByteArray("DRONE_XLINK:") + QUuid::createUuid().toByteArray(QUuid::WithoutBraces) + ':';
        environment.insert("DRONE_XLINK_RESULT_CHANNEL", QString::fromLatin1(channel));
        environment.insert("DRONE_XLINK_REQUEST_SHA256", requestSha);
        environment.insert("QT_QPA_PLATFORM", "offscreen");
        environment.insert("PYTHONUTF8", "1");
        process.setProcessEnvironment(environment);
        process.setProcessChannelMode(QProcess::MergedChannels);
        process.start(program, {"-B", "-m", "electromechanical_engine.xlink_native", input, output});
        QElapsedTimer deadline;
        deadline.start();
        const auto started = process.waitForStarted(std::min(timeout, 5000));
        const auto done = started && process.waitForFinished(int(std::max<qint64>(0, timeout - deadline.elapsed())));
        if (!done && process.state() != QProcess::NotRunning) {
            process.kill();
            process.waitForFinished(5000);
        }
        auto messages = process.readAllStandardOutput();
        const auto start = messages.indexOf(channel);
        const auto end = start < 0 ? -1 : messages.indexOf('\n', start);
        const auto framed = done && process.exitStatus() == QProcess::NormalExit && end >= 0;
        QByteArray body;
        if (start >= 0) {
            if (framed) {
                body = messages.mid(start + channel.size(), end - start - channel.size());
            }
            messages.remove(start, end < 0 ? messages.size() - start : end - start + 1);
        }
        writeNew(log, messages);
        if (!framed) {
            return {{"finalized", false}, {"timed_out", started && !done}, {"log", name + ".log"},
                    {"reason", !started ? process.errorString() : done ? "Processus terminé sans résultat sur son canal"
                                                                    : "Budget du processus dépassé"}};
        }
        auto result = parse(body, name + " (canal du processus)");
        result.insert("log", name + ".log");
        if (result.value("request_sha256") != requestSha || !QFileInfo::exists(input) || fileDigest(input) != requestSha) {
            return {{"finalized", false}, {"log", name + ".log"}, {"reason", "Empreinte de la requête native divergente"}};
        }
        require((process.exitCode() == 0) == (result.value("finalized") == true), "Sortie native incohérente : " + name);
        digests.insert(resultName, writeNew(output, json(result)));
        digests.insert(requestName, requestSha);
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
        require(std::isfinite(result.low[axis]) && std::isfinite(result.high[axis]) &&
                result.low[axis] <= result.high[axis], "Boîte englobante inversée ou non finie : " + id);
    }
    return result;
}

QString pairKey(const QString &a, const QString &b)
{
    return a < b ? a + QChar::Null + b : b + QChar::Null + a;
}

double lowerGap(const Bounds &a, const Bounds &b)
{
    std::array<double, 3> separations{};
    double scale = 1.0;
    for (int axis = 0; axis < 3; ++axis) {
        separations[axis] = std::max({0.0, a.low[axis] - b.high[axis], b.low[axis] - a.high[axis]});
        scale = std::max({scale, std::abs(a.low[axis]), std::abs(a.high[axis]),
                        std::abs(b.low[axis]), std::abs(b.high[axis])});
    }
    const auto distance = std::hypot(separations[0], separations[1], separations[2]);
    // Round towards inclusion at coordinate-scale floating-point uncertainty.
    const auto roundoff = (32 * std::numeric_limits<double>::epsilon()) * scale;
    return std::isfinite(distance) ? std::max(0.0, distance - roundoff) : 0.0;
}

struct Plan {
    QJsonArray tasks;
    QJsonArray unavailable;
    QJsonObject exclusions;
    QJsonArray excludedPairs;
    double cutoff = 0.0;
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
    plan.cutoff = criteria.value("clearance_mm").toDouble() + criteria.value("distance_tolerance_mm").toDouble();
    require(std::isfinite(plan.cutoff), "Seuil AABB non fini");
    std::sort(items.begin(), items.end(), [](const Bounds &a, const Bounds &b) {
        return a.low[0] == b.low[0] ? a.id < b.id : a.low[0] < b.low[0];
    });
    for (const auto &route : routes) {
        for (const auto &item : items) {
            if (item.id == route.id || (item.route && item.id < route.id)) {
                continue;
            }
            if (contacts.contains(pairKey(route.id, item.id))) {
                continue; // Evaluated explicitly even if outside the spatial filter.
            }
            const auto lower = lowerGap(route, item);
            if (lower > plan.cutoff) {
                plan.excludedPairs.append(QJsonArray{route.id, item.id, lower});
                continue;
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
    require(plan.possiblePairs + plan.excludedPairs.size() == plan.expectedPairs,
            "Partition des paires XLink incomplète");
    return plan;
}

bool nonnegative(const QJsonValue &value)
{
    return value.isDouble() && std::isfinite(value.toDouble()) && value.toDouble() >= 0;
}

bool consistentPair(const QJsonObject &task, const QJsonObject &observation, const QJsonObject &criteria)
{
    const auto volume = observation.value("intersection_mm3");
    const auto clearance = observation.value("clearance_mm");
    if (!nonnegative(volume) || !nonnegative(clearance) || observation.value("intersection_volume_mm3") != volume ||
        observation.value("a") != task.value("a") || observation.value("b") != task.value("b") ||
        !observation.value("authorized_relation").isBool()) {
        return false;
    }
    const auto volumeTolerance = criteria.value("volume_tolerance_mm3").toDouble();
    const auto distanceTolerance = criteria.value("distance_tolerance_mm").toDouble();
    const auto authorized = observation.value("authorized_relation").toBool();
    if (authorized) {
        const auto kind = task.value("relation").toObject().value("kind");
        const auto outside = observation.value("outside_envelope_volume_mm3");
        if (!((kind == "functional_contact" && volume.toDouble() <= volumeTolerance &&
               clearance.toDouble() <= distanceTolerance) ||
              (kind == "cable_in_conduit_envelope" && nonnegative(outside) && outside.toDouble() <= volumeTolerance))) {
            return false;
        }
    }
    const auto fails = !authorized && (volume.toDouble() > volumeTolerance ||
                         clearance.toDouble() < criteria.value("clearance_mm").toDouble() - distanceTolerance);
    return observation.value("status") == (fails ? "fail" : "pass");
}

bool consistentObservation(const QJsonObject &task, const QJsonObject &observation, const QJsonObject &criteria)
{
    const auto status = observation.value("status");
    const auto failures = observation.value("failures").toArray();
    const auto unknowns = observation.value("unknowns").toArray();
    if (status == "unknown") {
        return !unknowns.isEmpty() || !observation.value("reason").toString().isEmpty();
    }
    if (!(status == "pass" || status == "fail") || (status == "pass" && (!failures.isEmpty() || !unknowns.isEmpty()))) {
        return false;
    }
    const auto kind = task.value("kind");
    if (kind == "pair") {
        return consistentPair(task, observation, criteria);
    }
    if (kind == "route") {
        return status == "fail" ? !failures.isEmpty() : observation.value("length_mm").toDouble() > 0 &&
            observation.value("shape_sha256").toString().size() == 64 && observation.value("endpoints_mm").toArray().size() == 2;
    }
    return kind == "solid" && nonnegative(observation.value("volume_mm3")) &&
        nonnegative(observation.value("solid_count")) && (status == "fail" ||
        (observation.value("volume_mm3").toDouble() > 0 && observation.value("solid_count").toInt() > 0));
}

QJsonObject currentObservations(const QJsonObject &batchResult, const QJsonArray &batch,
                                const QJsonObject &request, const QJsonObject &inventory)
{
    if (batchResult.value("finalized") != true) {
        return {};
    }
    const auto observations = batchResult.value("observations").toArray();
    require(batchResult.value("observations").isArray() && observations.size() == batch.size() &&
            batchResult.value("worker_id").isString() && batchResult.value("worker_id") != inventory.value("worker_id") &&
            batchResult.value("measurement_identity_sha256") == inventory.value("measurement_identity_sha256") &&
            batchResult.value("before_sha256") == request.value("native_sha256") &&
            batchResult.value("after_sha256") == request.value("native_sha256") &&
            batchResult.value("environment") == request.value("environment"), "Lot natif incomplet ou identité incohérente");

    QJsonObject rows;
    const auto criteria = object(request, "criteria");
    for (qsizetype i = 0; i < batch.size(); ++i) {
        const auto task = batch.at(i).toObject();
        const auto id = task.value("id").toString();
        const auto row = observations.at(i).toObject();
        const auto observation = object(row, "observation");
        require(!rows.contains(id) && row.value("task") == task && row.value("cache_key") == request.value("cache_key") &&
                row.value("worker_pid").toInt() > 0 && row.value("worker_pid") == batchResult.value("pid") &&
                consistentObservation(task, observation, criteria),
                "Observation native contradictoire ou hors du lot : " + id);
        rows.insert(id, row);
    }
    return rows;
}

void publishDiagnostics(const QDir &directory, const QJsonObject &observations)
{
    for (auto it = observations.constBegin(); it != observations.constEnd(); ++it) {
        const auto path = directory.filePath(it.key() + ".json");
        QSaveFile output(path);
        const auto bytes = json(it.value().toObject());
        require(!QFileInfo(path).isSymLink() && output.open(QIODevice::WriteOnly) &&
                output.write(bytes) == bytes.size() && output.commit(), "Export diagnostique impossible : " + path);
    }
}

constexpr auto checkpointSchema = "drone-agricole.v21.xlink.checkpoint.v1";

QJsonObject restoreObservations(const QJsonObject &checkpoint, const QString &key, const Plan &plan,
                                const QJsonObject &criteria)
{
    if (checkpoint.isEmpty()) {
        return {};
    }
    require(checkpoint.value("schema") == checkpointSchema && checkpoint.value("measurement_key") == key,
            "Point de reprise hors identité de mesure XLink");
    const auto observations = object(checkpoint, "observations");
    qsizetype found = 0;
    for (const auto &entry : plan.tasks) {
        const auto task = entry.toObject();
        const auto id = task.value("id").toString();
        if (!observations.contains(id)) {
            continue;
        }
        const auto row = object(observations, id);
        require(row.value("task") == task && row.value("cache_key") == key && row.value("worker_pid").toInt() > 0 &&
                consistentObservation(task, object(row, "observation"), criteria), "Point de reprise incohérent : " + id);
        ++found;
    }
    require(found == observations.size(), "Point de reprise hors plan XLink");
    return observations;
}

struct MeasurementBudget {
    int tasks;
    int batchSize;
    int retries;
    int processTimeoutMs;
    int measurementTimeoutMs;
};

struct Measurement {
    QJsonObject observations;
    QJsonObject pendingReasons;
    QJsonArray batches;
    QJsonArray attempted;
    QJsonArray scheduled;
    QMap<QString, QString> artifacts;
};

struct Lot {
    QJsonArray tasks;
    int retries;
};

void scheduleRetry(QList<Lot> &queue, const QJsonArray &tasks, int remaining)
{
    if (remaining > 0 && !tasks.isEmpty()) {
        queue.append({tasks, remaining - 1});
    }
}

void subdivide(QList<Lot> &queue, const Lot &lot, qsizetype started)
{
    const auto size = lot.tasks.size();
    if (size == 1) {
        scheduleRetry(queue, lot.tasks, lot.retries);
        return;
    }
    QJsonArray left, isolated, right;
    const auto cut = started > 0 ? started - 1 : size / 2;
    for (qsizetype i = 0; i < size; ++i) {
        auto &group = i < cut ? left : started > 0 && i == cut ? isolated : right;
        group.append(lot.tasks.at(i));
    }
    scheduleRetry(queue, left, lot.retries);
    scheduleRetry(queue, right, lot.retries);
    scheduleRetry(queue, isolated, lot.retries);
}

Measurement measureCampaign(Worker &worker, QJsonObject request, const QJsonObject &inventory,
                            const QList<QJsonObject> &pending, QJsonObject history, const MeasurementBudget &budget)
{
    Measurement measured{std::move(history), {}, {}, {}, {}, {}};
    QList<Lot> queue;
    int selected = 0;
    for (const auto &task : pending) {
        const auto id = task.value("id").toString();
        const auto prior = measured.observations.value(id).toObject();
        if (!prior.isEmpty() && (task.value("kind") != "pair" ||
            object(prior, "observation").value("status") != "unknown")) {
            continue;
        }
        if (selected >= budget.tasks) {
            if (prior.isEmpty()) {
                measured.pendingReasons.insert(id, "BUDGET_TASKS");
            }
            continue;
        }
        if (queue.isEmpty() || queue.back().tasks.size() == budget.batchSize) {
            queue.append({{}, budget.retries});
        }
        queue.back().tasks.append(task);
        measured.scheduled.append(id);
        if (prior.isEmpty()) {
            measured.pendingReasons.insert(id, "BUDGET_TIME");
        }
        ++selected;
    }

    QElapsedTimer deadline;
    deadline.start();
    while (!queue.isEmpty() && deadline.elapsed() < budget.measurementTimeoutMs) {
        const auto lot = queue.takeFirst();
        const auto name = measured.batches.isEmpty() ? QString("batch") : "batch-" + QString::number(measured.batches.size() + 1);
        request.insert("tasks", lot.tasks);
        const auto result = worker(name, request, int(std::min<qint64>(budget.processTimeoutMs,
                    std::max<qint64>(1, budget.measurementTimeoutMs - deadline.elapsed()))));
        const auto fresh = currentObservations(result, lot.tasks, request, inventory);
        const auto logName = name + ".log";
        const auto log = read(worker.run.filePath(logName));
        const bool finalized = result.value("finalized") == true;
        const bool timeout = result.value("timed_out") == true;
        const auto unobserved = timeout ? "NATIVE_TIMEOUT" : "NATIVE_CRASH_OR_INVALID";
        qsizetype started = 0;
        for (const auto &entry : lot.tasks) {
            const auto task = entry.toObject();
            const auto id = task.value("id").toString();
            if (log.contains(id.toLatin1() + ": ")) {
                measured.attempted.append(id);
                ++started;
            }
            if (fresh.contains(id)) {
                const auto row = object(fresh, id);
                measured.observations.insert(id, row);
                measured.pendingReasons.remove(id);
                if (task.value("kind") == "pair" && object(row, "observation").value("status") == "unknown") {
                    scheduleRetry(queue, QJsonArray{task}, lot.retries);
                }
            } else if (!measured.observations.contains(id)) {
                measured.pendingReasons.insert(id, unobserved);
            }
        }
        if (!finalized) {
            subdivide(queue, lot, started);
        } else {
            for (const auto &suffix : {".result.json", ".request.json"}) {
                const auto path = name + suffix;
                measured.artifacts.insert(path, worker.digests.value(path));
            }
        }
        measured.batches.append(QJsonObject{{"finalized", finalized}, {"timed_out", timeout},
            {"reason", result.value("reason")}, {"log", logName}, {"log_sha256", digest(log)},
            {"started", started}, {"scheduled", lot.tasks.size()}, {"fresh_observations", fresh.size()},
            {"worker_id", result.value("worker_id")}, {"retries_remaining", lot.retries}});
    }
    return measured;
}

QJsonObject evaluateTasks(const Plan &plan, const Measurement &measurement, bool preliminary)
{
    QJsonObject counts{{"PASS", 0}, {"FAIL", 0}, {"INCONCLUSIVE", 0}, {"NOT_RUN", 0}};
    QJsonArray rows;
    int pairsAttempted = 0;
    int pairsExamined = 0;
    int intersections = 0;
    int clearanceFailures = 0;
    int authorizedContacts = 0;
    QJsonObject pairPendingReasons;
    for (const auto &entry : plan.tasks) {
        const auto task = entry.toObject();
        const auto id = task.value("id").toString();
        const auto result = measurement.observations.value(id).toObject();
        auto status = QString("NOT_RUN");
        QJsonValue reason;
        if (!result.isEmpty()) {
            const auto observation = result.value("observation").toObject();
            const auto value = observation.value("status").toString();
            status = value == "fail" ? "FAIL" : value == "pass" ? "PASS" : "INCONCLUSIVE";
            if (task.value("kind") == "pair") {
                ++pairsAttempted;
                if (value != "unknown" && nonnegative(observation.value("intersection_mm3")) &&
                    nonnegative(observation.value("clearance_mm"))) {
                    ++pairsExamined;
                    const auto failures = observation.value("failures").toArray();
                    intersections += failures.contains("forbidden_interference");
                    clearanceFailures += failures.contains("insufficient_clearance");
                    authorizedContacts += observation.value("authorized_relation") == true;
                } else {
                    status = "INCONCLUSIVE";
                    reason = "OCC_INDETERMINATE";
                }
                if (preliminary && status == "PASS") {
                    status = "INCONCLUSIVE";
                }
            }
        } else {
            reason = measurement.pendingReasons.value(id);
            if (task.value("kind") == "pair") {
                const auto key = reason.toString();
                pairPendingReasons.insert(key, pairPendingReasons.value(key).toInt() + 1);
            }
        }
        counts.insert(status, counts.value(status).toInt() + 1);
        rows.append(QJsonObject{{"task", task}, {"status", status}, {"reason", reason},
                                {"native_evidence", result.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(result)}});
    }
    return {{"status", plan.routes == 0 ? "NOT_RUN" : counts.value("FAIL").toInt() > 0 ? "FAIL" :
                      counts.value("NOT_RUN").toInt() > 0 || counts.value("INCONCLUSIVE").toInt() > 0 ||
                      !plan.unavailable.isEmpty() || preliminary ? "INCONCLUSIVE" : "PASS"},
            {"counts", counts}, {"checks", rows}, {"unavailable_occurrences", plan.unavailable},
            {"solid_occurrences", plan.solids}, {"route_occurrences", plan.routes},
            {"expected_pairs", plan.expectedPairs}, {"possible_brep_pairs", plan.possiblePairs},
            {"pairs_screened_out", plan.excludedPairs.size()}, {"pairs_examined", pairsExamined},
            {"pairs_attempted", pairsAttempted}, {"pairs_unmeasurable", pairsAttempted - pairsExamined},
            {"pairs_not_run", plan.possiblePairs - pairsAttempted},
            {"pairs_forbidden_intersections", intersections}, {"pairs_below_clearance", clearanceFailures},
            {"pairs_authorized_contacts", authorizedContacts}, {"pairs_not_run_by_reason", pairPendingReasons},
            {"filter", "Borne inférieure prudente entre AABB mondiales ; seuil garde + tolérance ; contacts par occurrence exacte"},
            {"scope", "Paires de solides visibles dont au moins un câble ; état nominal de la copie"},
            {"exclusions", plan.exclusions}};
}

void verifySaveClosure(const QJsonObject &saved, const QJsonObject &receipt, const QString &entry)
{
    const auto originals = object(receipt, "inputs_sha256");
    const auto after = object(saved, "after_sha256");
    require(saved.value("before_sha256") == originals && after.keys() == originals.keys() &&
            after.contains(entry), "Fermeture de sauvegarde divergente du reçu de copie");
    for (auto it = originals.constBegin(); it != originals.constEnd(); ++it) {
        require(it.key() == entry || it.value() == after.value(it.key()),
                "Dépendance privée modifiée en dehors de la sauvegarde de racine : " + it.key());
    }
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
    const MeasurementBudget measurementBudget{maxTasks, budget(options, "native-batch-size"),
        budget(options, "max-native-retries", 0), batchTimeout, budget(options, "measurement-timeout-ms")};
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
    Worker worker{workspace, run, freecad, {}};
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
    const auto checkpointArg = options.value("checkpoint");
    const auto checkpointPin = options.value("checkpoint-sha256");
    require(checkpointArg.isEmpty() == checkpointPin.isEmpty(), "Point de reprise et empreinte indépendante requis ensemble");
    QJsonObject checkpoint;
    if (!checkpointArg.isEmpty()) {
        const auto path = workspaceFile(workspace, checkpointArg);
        const auto relative = relativePath(output, path);
        const auto bytes = read(path);
        require(relative.startsWith("run-") && relative.endsWith("/checkpoint.json") &&
                relative.count('/') == 1 && digest(bytes) == checkpointPin, "Point de reprise ou empreinte divergente");
        checkpoint = parse(bytes, path);
        require(!checkpoint.isEmpty(), "Point de reprise vide");
        inputs.insert(path, checkpointPin);
    }
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
    QMap<QString, QString> artifacts;
    QString checkpointDigest;
    const auto copyRecord = output.filePath("saved.json");
    const auto rootFile = configuration.value("entry").toString();
    const auto checkReceipt = [&](const QJsonObject &row, const QString &copyPath) {
        const auto files = object(row, "inputs_sha256");
        qsizetype natives = 0;
        for (auto it = files.begin(); it != files.end(); ++it) {
            natives += it.key().endsWith(".FCStd", Qt::CaseInsensitive);
        }
        return natives == configuration.value("native_count").toInt() &&
               row.value("entry") == rootFile &&
               QDir::fromNativeSeparators(row.value("source_root").toString()) == source &&
               QDir::fromNativeSeparators(row.value("copy_root").toString()) == copyPath;
    };
    const auto stageCopy = [&](const QString &name, const QString &copyPath) {
        return worker(name, {{"action", "stage"}, {"copy", copyPath}, {"source", source},
                             {"entry", rootFile}, {"extras", configuration.value("extras").toArray()}}, timeout);
    };
    if (QFileInfo::exists(copyRecord)) {
        saved = load(copyRecord);
        require(saved.value("copy_configuration") == pins.value("configuration"), "La configuration de copie a changé");
        receipt = load(QDir(copy).filePath("experiment.json"));
        require(checkReceipt(receipt, copy), "Reçu de copie divergent à la reprise");
        verifySaveClosure(saved, receipt, rootFile);
        if (checkpointPin.isEmpty()) {
            const auto auditCopy = run.filePath("reference-copy");
            const auto auditReceipt = stageCopy("audit-stage", auditCopy);
            require(auditReceipt.value("finalized") == true && checkReceipt(auditReceipt, auditCopy) &&
                    auditReceipt.value("inputs_sha256") == receipt.value("inputs_sha256"),
                    "Fermeture reprise divergente des sources recopiées");
            const auto auditSaved = worker("audit-save", {{"action", "save"}, {"copy", auditCopy}}, timeout);
            require(auditSaved.value("finalized") == true, "Sauvegarde de la copie de contrôle échouée");
            verifySaveClosure(auditSaved, auditReceipt, rootFile);
            const auto audit = worker("audit-root", {{"action", "audit_saved_root"}, {"copy", copy},
                {"reference_copy", auditCopy}, {"native_sha256", saved.value("after_sha256")},
                {"reference_native_sha256", auditSaved.value("after_sha256")}}, timeout);
            require(audit.value("finalized") == true && audit.value("equivalent") == true,
                    "Racine privée divergente d’une sauvegarde indépendante des sources");
            phases.insert("reopened_copy_authority", audit);
        }
        phases.insert("reuse_saved", true);
    } else {
        receipt = stageCopy("stage", copy);
        phases.insert("stage", receipt);
        if (receipt.value("finalized") == true) {
            auto saveRequest = copyRequest;
            saveRequest.insert("action", "save");
            if (checkReceipt(receipt, copy)) {
                saved = worker("save", saveRequest, timeout);
                saved.insert("copy_configuration", pins.value("configuration"));
                phases.insert("save", saved);
                if (saved.value("finalized") == true) {
                    verifySaveClosure(saved, receipt, rootFile);
                    writeNew(copyRecord, json(saved));
                }
            } else {
                phases.insert("save", QJsonObject{{"finalized", false}, {"reason", "Nombre de fichiers hors référentiel"}});
            }
        }
    }
    const auto originals = receipt.value("inputs_sha256").toObject();
    const auto nativeHashes = saved.value("after_sha256").toObject();
    QJsonObject nativeRequest{{"copy", copy}, {"native_sha256", nativeHashes}};
    bool available = false;
    if (saved.value("finalized") == true) {
        nativeRequest.insert("action", "inventory");
        inventory = worker("inventory", nativeRequest, timeout);
        phases.insert("inventory", QJsonObject{{"finalized", inventory.value("finalized")},
                                               {"reason", inventory.value("reason")}, {"log", "inventory.log"}});
        available = inventory.value("finalized") == true && inventory.value("inventory_complete") == true;
    }
    const QJsonObject context{{"request_kind", "nominal_xlink_validation"}, {"criteria_contract", "xlink.coverage.v1"},
                              {"observations_protocol", "fresh-worker.v1"}, {"scope", scope},
                              {"os", QSysInfo::prettyProductName()}, {"architecture", QSysInfo::currentCpuArchitecture()},
                              {"qt", qVersion()}};
    const auto measurementIdentity = inventory.value("measurement_identity_sha256");
    QJsonObject cacheIdentity{{"pins", pins}, {"root_sha256", nativeHashes.value(rootFile)}, {"closure_sha256", nativeHashes},
                              {"original_closure_sha256", originals},
                              {"save_record_sha256", digest(json(saved))},
                              {"context", context}, {"criteria", criteria}};
    if (available) {
        require(measurementIdentity.toString().size() == 64, "Empreinte des occurrences natives absente");
        cacheIdentity.insert("environment", inventory.value("environment"));
        cacheIdentity.insert("measurement_identity_sha256", measurementIdentity);
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
         {"native_timeout_ms", timeout}, {"batch_timeout_ms", batchTimeout}, {"max_native_tasks", maxTasks},
         {"native_batch_size", measurementBudget.batchSize}, {"max_native_retries", measurementBudget.retries},
         {"measurement_timeout_ms", measurementBudget.measurementTimeoutMs}, {"checkpoint_sha256", checkpointPin}},
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
        const auto restored = restoreObservations(checkpoint, cacheKey, plan, criteria);
        const auto checkpointPath = "cache/" + cacheKey;
        require(output.mkpath(checkpointPath), "Dossier diagnostique non créé");
        const QDir checkpoints(output.filePath(checkpointPath));
        require(checkpoints.canonicalPath() == output.filePath(checkpointPath), "Dossier diagnostique redirigé");
        const auto ignored = checkpoints.entryList({"*.json"}, QDir::Files).size();
        phases.insert("cache", QJsonObject{{"policy", checkpointPin.isEmpty() ? "REMEASURE" : "PINNED_CHECKPOINT"},
            {"diagnostic_files_ignored", ignored}, {"checkpoint_sha256", checkpointPin},
            {"reason", "Les observations diagnostiques ne sont jamais relues. La reprise requiert une empreinte de campagne externe au point de reprise."}});
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
        for (const auto &entry : plan.tasks) {
            pending.append(entry.toObject());
        }
        std::stable_sort(pending.begin(), pending.end(), [&earlier](const QJsonObject &a, const QJsonObject &b) {
            const auto va = earlier.value(a.value("id").toString());
            const auto vb = earlier.value(b.value("id").toString());
            if (va != vb) {
                return va < vb;
            }
            const auto priority = [](const QJsonObject &task) {
                const auto kind = task.value("kind");
                return kind == "route" ? 0 : kind == "pair" ? 1 : 2;
            };
            return priority(a) < priority(b);
        });
        auto request = nativeRequest;
        request.insert("action", "measure");
        request.insert("criteria", criteria);
        request.insert("environment", inventory.value("environment"));
        request.insert("measurement_identity_sha256", measurementIdentity);
        request.insert("cache_key", cacheKey);
        const auto measured = measureCampaign(worker, request, inventory, pending, restored, measurementBudget);
        artifacts = measured.artifacts;
        QJsonObject fresh = measured.observations;
        qsizetype resumed = 0;
        for (auto it = restored.constBegin(); it != restored.constEnd(); ++it) {
            if (fresh.value(it.key()) == it.value()) {
                fresh.remove(it.key());
                ++resumed;
            }
        }
        publishDiagnostics(checkpoints, fresh);
        if (!measured.batches.isEmpty()) {
            phases.insert("batch", measured.batches.first());
            phases.insert("batches", measured.batches);
            artifacts.insert("scheduled.json", writeNew(run.filePath("scheduled.json"),
                json({{"cache_key", cacheKey}, {"ids", measured.attempted}, {"scheduled", measured.scheduled}})));
        }
        geometry = evaluateTasks(plan, measured, criteria.value("screening_only").toBool(true));
        geometry.insert("resumed_tasks", resumed);
        geometry.insert("aabb_exclusion_proof", "aabb_exclusions.json");
        artifacts.insert("aabb_exclusions.json", writeNew(run.filePath("aabb_exclusions.json"),
            json({{"schema", "drone-agricole.v21.xlink.aabb.v1"}, {"measurement_key", cacheKey},
                  {"inventory_sha256", worker.digests.value("inventory.result.json")}, {"cutoff_mm", plan.cutoff},
                  {"columns", QJsonArray{"a", "b", "lower_gap_mm"}}, {"exclusions", plan.excludedPairs}})));
        checkpointDigest = writeNew(run.filePath("checkpoint.json"),
            json({{"schema", checkpointSchema}, {"measurement_key", cacheKey},
                  {"observations", measured.observations}}));
        artifacts.insert("checkpoint.json", checkpointDigest);
        report.insert("checkpoint", QJsonObject{{"file", "checkpoint.json"}, {"sha256", checkpointDigest},
            {"observations", measured.observations.size()}, {"previous_sha256", checkpointPin},
            {"remaining_tasks", measured.pendingReasons.size()}});
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
        {"cache_key", cacheKey}, {"measurement_identity_sha256", measurementIdentity}, {"measurement_context", context},
        {"saved_worker", saved.value("worker_id")}, {"reopened_worker", inventory.value("worker_id")},
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
    artifacts.insert("campaign.json", writeNew(run.filePath("campaign.json"), json(report)));
    for (const auto *file : {"stage.result.json", "save.result.json", "inventory.result.json", "projection.result.json",
                             "verify.result.json", "audit-stage.result.json", "audit-save.result.json", "audit-root.result.json"}) {
        if (worker.digests.contains(file)) {
            artifacts.insert(file, worker.digests.value(file));
        }
    }
    t0.finalize(report, artifacts);
    if (!checkpointDigest.isEmpty()) {
        std::fprintf(stderr, "XLINK_CHECKPOINT %s %s\n", qPrintable(checkpointDigest),
                     qPrintable(relativePath(workspace, run.filePath("checkpoint.json"))));
    }
    std::printf("%s %s\n", verdict, qPrintable(relativePath(workspace, run.absolutePath())));
    return !available ? 2 : complete ? 0 : 3;
}

} // namespace electromechanical_validation
