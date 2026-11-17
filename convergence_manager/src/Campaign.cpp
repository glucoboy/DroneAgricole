#include "Campaign.hpp"
#include "Files.hpp"
#include "Selection.hpp"

#include <QFileInfo>
#include <QJsonArray>
#include <QLockFile>
#include <QSet>
#include <algorithm>

namespace convergence {
namespace {

void append(QJsonObject &object, const QString &key, const QJsonValue &value)
{
    auto items = object.value(key).toArray();
    items.append(value);
    object.insert(key, items);
}

QJsonObject overlay(QJsonObject base, const QJsonObject &changes)
{
    for (auto it = changes.begin(); it != changes.end(); ++it) {
        base.insert(it.key(), it.value());
    }
    return base;
}

QJsonObject indexed(const QJsonValue &entries)
{
    require(entries.isArray(), "Liste d'objets attendue");
    QJsonObject index;
    for (const auto &entry : entries.toArray()) {
        const auto object = entry.toObject();
        const auto id = identifier(object.value("id"));
        require(!index.contains(id), "Identifiant dupliqué : " + id);
        index.insert(id, object);
    }
    return index;
}

bool containsAll(const QJsonArray &actual, const QJsonArray &required)
{
    return std::all_of(required.begin(), required.end(), [&](const auto &id) { return actual.contains(id); });
}

bool hasMatchingDigest(const QDir &root, const QJsonObject &result, const QString &pathKey,
                       const QString &shaKey)
{
    try {
        const auto name = result.value(pathKey).toString();
        return !name.isEmpty() && fileDigest(fileInside(root, name)) == result.value(shaKey);
    } catch (const std::exception &) {
        return false;
    }
}

QJsonObject issueFinding(const QString &code, const QString &reason, const QString &status = "FAIL")
{
    return {{"code", code}, {"reason", reason}, {"status", status}};
}

bool closesIssue(const QJsonObject &issue)
{
    const auto report = issue.value("report").toObject();
    const auto observed = report.value("value").toObject().value("value");
    return report.value("outcome") == "RESOLVED" && !observed.isUndefined() && !observed.isNull() &&
        (!issue.contains("expected_value") || observed == issue.value("expected_value"));
}

QString issueReason(const QJsonObject &issue)
{
    const auto report = issue.value("report").toObject();
    if (report.value("outcome") == "RESOLVED" && !closesIssue(issue)) {
        return "La valeur fournisseur établie ne satisfait pas la valeur requise. " + issue.value("next_check").toString();
    }
    return "Preuve fournisseur applicable absente. " + issue.value("next_check").toString();
}

int limit(const QJsonValue &value, const QString &name, int minimum = 1)
{
    const auto integer = value.toInt(-1);
    require(integer >= minimum && integer <= 100, "Budget invalide : " + name);
    return integer;
}

} // namespace

Campaign::Campaign(QDir output, QJsonObject config, QJsonObject manifest, Backend &backend)
    : output_(std::move(output)), config_(std::move(config)), manifest_(std::move(manifest)), backend_(backend)
{
    require(output_.exists() && config_.value("version") == 1, "Dossier ou version de campagne invalide");
    identifier(config_.value("id"));
    const auto milestone = config_.value("milestone");
    require(milestone == "DIGITAL_BENCH" || milestone == "PHYSICAL", "Jalon inconnu");
    for (const auto &key : {"max_detailed", "local_corrections", "alternative_families",
                           "consolidation_attempts", "operation_retries"}) {
        budget(key);
    }
    const auto problems = indexed(config_.value("problems"));
    const auto candidates = indexed(config_.value("candidates"));
    const auto portfolios = indexed(config_.value("portfolios"));
    require(!problems.isEmpty() && !candidates.isEmpty() && !portfolios.isEmpty() &&
            candidates.size() <= 100 && portfolios.size() <= 100, "Inventaire de variantes hors bornes");
    require(!config_.value("required_links").toArray().isEmpty(), "Périmètre de liaisons absent");
    require(config_.value("geometry_tolerance_mm").toDouble() > 0, "Tolérance géométrique absente");
    compareCandidates({}, config_.value("objectives").toArray(), reference());
    const auto issues = config_.value("issues").toObject();
    for (auto it = issues.begin(); it != issues.end(); ++it) {
        const auto issue = it.value().toObject();
        const auto impact = issue.value("impact");
        require((impact == "ALTERNATIVE_ONLY" || impact == "CONDITION" || impact == "REQUIRED") &&
                issue.value("searches").isArray() && issue.value("sources").isArray() &&
                issue.value("calculations").isArray() && !issue.value("next_check").toString().isEmpty(),
                "Audit d'inconnue incomplet : " + it.key());
    }
    for (const auto &entry : problems) {
        for (const auto &issue : entry.toObject().value("research").toArray()) {
            require(issues.contains(identifier(issue)), "Recherche de problème inconnue");
        }
    }
    const auto limits = config_.value("budgets").toObject();
    for (const auto &entry : candidates) {
        const auto row = entry.toObject();
        const auto problemId = identifier(row.value("problem"));
        const auto family = identifier(row.value("family"));
        require(problems.contains(problemId) && !row.value("assignments").toObject().isEmpty(),
                "Variante sans problème ou affectation : " + row.value("id").toString());
        limit(limits.value("by_problem").toObject().value(problemId), problemId);
        limit(limits.value("by_family").toObject().value(family), family);
        for (const auto &issue : row.value("issues").toArray()) {
            require(issues.contains(identifier(issue)), "Inconnue de variante absente du registre");
        }
        for (const auto &field : {"dependencies", "exclusions"}) {
            require(!row.contains(field) || row.value(field).isArray(), "Relations de décision invalides");
            for (const auto &other : row.value(field).toArray()) {
                require(other != row.value("id") && candidates.contains(identifier(other)),
                        "Référence de décision inconnue ou réflexive");
            }
        }
    }
    for (const auto &entry : portfolios) {
        const auto members = entry.toObject().value("members").toArray();
        require(!members.isEmpty(), "Portefeuille vide");
        for (const auto &member : members) {
            require(candidates.contains(identifier(member)), "Membre de portefeuille inconnu");
        }
    }
}

QString Campaign::reference() const
{
    return manifest_.value("reference_sha256").toString();
}

int Campaign::budget(const QString &name) const
{
    return limit(config_.value("budgets").toObject().value(name), name, name == "operation_retries" ? 0 : 1);
}

QJsonObject Campaign::candidate(const QString &id) const
{
    return indexed(config_.value("candidates")).value(id).toObject();
}

QJsonObject Campaign::problem(const QString &id) const
{
    return indexed(config_.value("problems")).value(id).toObject();
}

QJsonObject Campaign::applied(const QJsonObject &row) const
{
    return overlay(overlay(config_.value("base").toObject(), row.value("context").toObject()),
                   row.value("assignments").toObject());
}

void Campaign::checkpoint()
{
    write(output_.filePath("checkpoint.json"), state_);
}

void Campaign::transition(const QString &next)
{
    state_.insert("state", next);
    append(state_, "transitions", next);
}

int Campaign::run(int steps)
{
    QLockFile lock(output_.filePath(".campaign.lock"));
    lock.setStaleLockTime(0);
    require(lock.tryLock(), "Campagne déjà en cours");
    const auto manifestPath = output_.filePath("manifest.json");
    if (QFileInfo::exists(manifestPath)) {
        require(load(manifestPath) == manifest_, "Le manifeste de campagne a changé");
    } else {
        require(!QFileInfo::exists(output_.filePath("checkpoint.json")), "Manifeste manquant pour la reprise");
        write(manifestPath, manifest_);
    }
    const auto checkpointPath = output_.filePath("checkpoint.json");
    if (QFileInfo::exists(checkpointPath)) {
        state_ = load(checkpointPath);
        require(state_.value("schema_version") == 1 &&
                state_.value("manifest_sha256") == fileDigest(manifestPath), "Checkpoint hors du manifeste gelé");
        const auto last = state_.value("last_consolidated").toObject();
        if (!last.isEmpty()) {
            require(hasMatchingDigest(output_, last, "path", "sha256"),
                    "Candidate consolidée modifiée depuis le checkpoint");
            const auto validation = last.value("validation").toObject();
            require(!validation.contains("report") || hasMatchingDigest(output_, validation, "report", "report_sha256"),
                    "Rapport de consolidation modifié depuis le checkpoint");
        }
    } else {
        state_ = {{"schema_version", 1}, {"manifest_sha256", fileDigest(manifestPath)},
                  {"attempts", QJsonArray{}}, {"transitions", QJsonArray{}}, {"unknowns", QJsonObject{}},
                  {"operations", QJsonObject{}}, {"detailed_used", 0}, {"consolidation_used", 0},
                  {"last_consolidated", QJsonValue::Null}, {"selected", QJsonArray{}}};
        transition("INVENTORY");
        checkpoint();
    }
    for (int count = 0; state_.value("state") != "VERDICT" && (steps < 0 || count < steps); ++count) {
        advance();
        checkpoint();
    }
    if (state_.value("state") != "VERDICT") {
        return 4;
    }
    const auto outcome = state_.value("outcome").toObject();
    const auto status = outcome.value("verdict");
    require(outcome == finalOutcome(),
            "Verdict terminal incohérent avec la consolidation et le référentiel gelé");
    for (const auto &entry : {qMakePair(QString("selection.json"), QString("selection")),
                             qMakePair(QString("campaign.json"), QString("outcome"))}) {
        const auto path = output_.filePath(entry.first);
        const auto document = state_.value(entry.second).toObject();
        if (QFileInfo::exists(path)) {
            require(load(path) == document, "Sortie terminale divergente : " + entry.first);
        } else {
            require(!QFileInfo::exists(output_.filePath("t0_run_manifest.json")), "Sortie terminale manquante : " + entry.first);
            write(path, document);
        }
    }
    return status == "L5_PASS" ? 0 : status == "L5_CONDITIONAL" ? 3 : 2;
}

QJsonObject Campaign::operation(const QString &kind, const QString &area, const QString &id,
                                const std::function<QJsonObject(const QDir &)> &execute)
{
    const auto key = area + '/' + id + '/' + kind;
    auto operations = state_.value("operations").toObject();
    auto runs = operations.value(key).toArray();
    const auto recordRun = [&](qsizetype index, const QJsonObject &run) {
        runs.replace(index, run);
        operations.insert(key, runs);
        state_.insert("operations", operations);
    };
    if (!runs.isEmpty()) {
        const auto previous = runs.last().toObject();
        const auto path = previous.value("path").toString() + "/operation.json";
        if (QFileInfo::exists(output_.filePath(path))) {
            const auto bytes = read(fileInside(output_, path));
            const auto hash = digest(bytes);
            const auto result = parse(bytes, path);
            require(result.value("operation") == key && result.value("manifest_sha256") == state_.value("manifest_sha256") &&
                    result.value("result").isObject() && (!previous.contains("sha256") || previous.value("sha256") == hash),
                    "Reçu d'opération hors campagne : " + key);
            recordRun(runs.size() - 1, overlay(previous, {{"state", "COMPLETED"}, {"sha256", hash}}));
            return result.value("result").toObject();
        }
        require(previous.value("state") != "COMPLETED", "Reçu d'opération disparu : " + key);
        recordRun(runs.size() - 1, overlay(previous, {{"state", "INTERRUPTED"}}));
    }
    if (runs.size() >= 1 + budget("operation_retries")) {
        operations.insert(key, runs);
        state_.insert("operations", operations);
        return {{"status", "ERROR"}, {"reason", "Budget de reprise épuisé pour " + key}};
    }

    const auto path = area + '/' + id + '/' + kind + '-' + QString::number(runs.size() + 1);
    runs.append(QJsonObject{{"path", path}, {"state", "RESERVED"}});
    operations.insert(key, runs);
    state_.insert("operations", operations);
    checkpoint();

    const QDir target(output_.filePath(path));
    require(!target.exists() && output_.mkpath(path) &&
            relative(output_, target.canonicalPath()) == path, "Dossier d'opération non isolé : " + path);
    QJsonObject result;
    try {
        result = execute(target);
        require(!result.isEmpty(), "Opération sans résultat : " + key);
    } catch (const std::exception &error) {
        result = {{"status", "ERROR"}, {"reason", QString::fromUtf8(error.what())}};
    }
    const auto hash = write(target.filePath("operation.json"), QJsonObject{{"operation", key},
        {"manifest_sha256", state_.value("manifest_sha256")}, {"result", result}});
    recordRun(runs.size() - 1, QJsonObject{{"path", path}, {"state", "COMPLETED"}, {"sha256", hash}});
    return result;
}

void Campaign::recordAttempt(QJsonObject observation)
{
    const auto current = state_.value("current").toObject();
    observation = overlay(current, observation);
    observation.insert("reference_sha256", reference());
    append(state_, "attempts", observation);
    state_.insert("cursor", state_.value("cursor").toInt() + 1);
    state_.remove("current");
    transition("DIAGNOSE");
}

void Campaign::precheck()
{
    const auto entries = config_.value("candidates").toArray();
    const auto cursor = state_.value("cursor").toInt();
    if (cursor >= entries.size()) {
        transition("CONSOLIDATE");
        return;
    }
    auto current = entries.at(cursor).toObject();
    const auto id = current.value("id").toString();
    const auto issueIds = current.value("issues").toArray();
    const auto problemId = current.value("problem").toString();
    const auto family = current.value("family").toString();
    const auto spec = problem(problemId);
    state_.insert("current", current);

    auto problems = state_.value("problem_state").toObject();
    auto progress = problems.value(problemId).toObject();
    const bool local = spec.value("local_family") == family;
    QString skip;
    if (local && (progress.value("local_pass") == true || progress.value("escalated") == true ||
                  progress.value("local_used").toInt() >= budget("local_corrections"))) {
        skip = "LOCAL_SERIES_CLOSED";
    } else if (!local && spec.contains("local_family") && progress.value("escalated") != true) {
        skip = "NO_ESCALATION_REQUIRED";
    }
    const auto proposal = current.value("proposal");
    if (skip.isEmpty() && !proposal.isUndefined()) {
        const auto screened = state_.value("exploration").toObject().value("alternatives").toArray();
        const auto found = std::find_if(screened.begin(), screened.end(), [&](const auto &entry) {
            return entry.toObject().value("id") == proposal;
        });
        if (found == screened.end() || found->toObject().value("status") == "FAIL") {
            skip = "L3_SCREENING_UNAVAILABLE_OR_REJECTED";
        }
    }
    if (!skip.isEmpty()) {
        recordAttempt({{"status", "SKIPPED"}, {"reason", skip}});
        return;
    }

    auto considered = progress.value("families_considered").toArray();
    if (!local && !considered.contains(family)) {
        considered.append(family);
        progress.insert("families_considered", considered);
        problems.insert(problemId, progress);
        state_.insert("problem_state", problems);
    }
    auto unknowns = state_.value("unknowns").toObject();
    QJsonArray missing;
    QStringList unresolved;
    for (const auto &issueValue : issueIds) {
        const auto issue = issueValue.toString();
        auto entry = unknowns.value(issue).toObject();
        if (entry.isEmpty()) {
            const auto report = operation("research", "investigations", issue,
                [&](const QDir &target) { return backend_.research(issue, target); });
            entry = overlay(config_.value("issues").toObject().value(issue).toObject(),
                            {{"report", report}, {"variants", QJsonArray{}}, {"repeat_count", 0}});
        }
        if (!entry.value("variants").toArray().contains(id)) {
            if (!entry.value("variants").toArray().isEmpty()) {
                entry.insert("repeat_count", entry.value("repeat_count").toInt() + 1);
            }
            append(entry, "variants", id);
        }
        unknowns.insert(issue, entry);
        if (!closesIssue(entry)) {
            missing.append(issue);
            unresolved.append(issueReason(entry));
        }
    }
    state_.insert("unknowns", unknowns);
    if (!missing.isEmpty()) {
        recordAttempt({{"status", "CONDITIONAL"}, {"missing_controls", missing},
                       {"reason", unresolved.join(' ')}});
        return;
    }

    const auto assignments = applied(current);
    const auto owned = config_.value("ownership").toObject();
    for (auto it = assignments.begin(); it != assignments.end(); ++it) {
        if (!owned.contains(it.key()) || !it.key().startsWith("route:")) {
            recordAttempt({{"status", "CONDITIONAL"}, {"missing_controls", QJsonArray{it.key()}},
                           {"reason", "Aucun contrôleur natif indépendant pour cette affectation"}});
            return;
        }
    }
    const auto definitions = manifest_.value("routes").toObject();
    QJsonObject geometry;
    for (auto it = assignments.begin(); it != assignments.end(); ++it) {
        geometry.insert(it.key(), definitions.value(it.value().toString()).toObject().isEmpty() ?
                        it.value() : definitions.value(it.value().toString()));
    }
    const auto signature = candidateSignature({{"assignments", geometry}, {"topology", manifest_.value("topology")}},
                                              config_.value("geometry_tolerance_mm").toDouble());
    auto seen = state_.value("signatures").toObject();
    if (seen.contains(signature)) {
        recordAttempt({{"status", "DUPLICATE"}, {"equivalent_to", seen.value(signature)}, {"signature", signature}});
        return;
    }
    const auto limits = config_.value("budgets").toObject();
    auto familyCounts = state_.value("family_counts").toObject();
    const auto familyCount = familyCounts.value(family).toInt();
    const auto problemCount = progress.value("detailed_used").toInt();
    const auto count = state_.value("detailed_used").toInt();
    if (count >= budget("max_detailed") ||
        familyCount >= limit(limits.value("by_family").toObject().value(family), family) ||
        problemCount >= limit(limits.value("by_problem").toObject().value(problemId), problemId)) {
        recordAttempt({{"status", "SKIPPED"}, {"reason", "DETAILED_BUDGET_EXHAUSTED"}});
        return;
    }
    seen.insert(signature, id);
    familyCounts.insert(family, familyCount + 1);
    progress.insert("detailed_used", problemCount + 1);
    if (local) {
        progress.insert("local_used", progress.value("local_used").toInt() + 1);
    }
    problems.insert(problemId, progress);
    current.insert("signature", signature);
    state_.insert("current", current);
    state_.insert("signatures", seen);
    state_.insert("detailed_used", count + 1);
    state_.insert("family_counts", familyCounts);
    state_.insert("problem_state", problems);
    transition("BUILD");
}

void Campaign::diagnose()
{
    const auto attempts = state_.value("attempts").toArray();
    const auto last = attempts.last().toObject();
    const auto id = last.value("problem").toString();
    const auto local = problem(id).value("local_family");
    if (local.isUndefined() || last.value("family") != local) {
        transition("PRECHECK");
        return;
    }
    auto problems = state_.value("problem_state").toObject();
    auto progress = problems.value(id).toObject();
    if (last.value("status") == "PASS") {
        progress.insert("local_pass", true);
    }
    QJsonArray localReports;
    for (const auto &entry : attempts) {
        const auto report = entry.toObject();
        if (report.value("problem") == id && report.value("family") == local) {
            localReports.append(report);
        }
    }
    const auto conflicts = constraintConflictAnalyzer(localReports);
    progress.insert("conflicts", conflicts);
    const bool recurrent = std::any_of(conflicts.begin(), conflicts.end(), [&](const auto &item) {
        return item.toObject().value("occurrences").toInt() >= budget("local_corrections");
    });
    const auto declared = config_.value("candidates").toArray();
    const auto next = declared.begin() + state_.value("cursor").toInt();
    const bool localSequenceEnded = std::none_of(next, declared.end(), [&](const auto &entry) {
        const auto row = entry.toObject();
        return row.value("problem") == id && row.value("family") == local;
    });
    if (recurrent || (progress.value("local_pass") != true &&
                      (localSequenceEnded || progress.value("local_used").toInt() >= budget("local_corrections")))) {
        progress.insert("escalation_reason", recurrent ? "REPEATED_CONSTRAINT" :
                        localSequenceEnded ? "LOCAL_SEQUENCE_EXHAUSTED" : "LOCAL_BUDGET_EXHAUSTED");
        state_.insert("escalating_problem", id);
        transition("CHANGE_FAMILY");
    } else {
        transition("CORRECT");
    }
    problems.insert(id, progress);
    state_.insert("problem_state", problems);
}

void Campaign::changeFamily()
{
    const auto id = state_.value("escalating_problem").toString();
    auto problems = state_.value("problem_state").toObject();
    auto progress = problems.value(id).toObject();
    auto unknowns = state_.value("unknowns").toObject();
    for (const auto &issueValue : problem(id).value("research").toArray()) {
        const auto issue = issueValue.toString();
        if (!unknowns.contains(issue)) {
            const auto report = operation("research", "investigations", issue,
                [&](const QDir &target) { return backend_.research(issue, target); });
            unknowns.insert(issue, overlay(config_.value("issues").toObject().value(issue).toObject(),
                                          {{"report", report}, {"variants", QJsonArray{}}, {"repeat_count", 0}}));
        }
    }
    state_.insert("unknowns", unknowns);
    const auto explored = operation("explore", "investigations", "l3",
        [&](const QDir &target) { return backend_.explore(target); });
    state_.insert("exploration", explored);
    progress.insert("escalated", true);
    problems.insert(id, progress);
    state_.insert("problem_state", problems);
    transition("GENERATE_FAMILIES");
}

void Campaign::consolidate()
{
    const auto portfolios = config_.value("portfolios").toArray();
    const auto cursor = state_.value("portfolio_cursor").toInt();
    auto pending = state_.value("pending_consolidation").toObject();
    if (cursor >= portfolios.size()) {
        verdict();
        return;
    }
    if (pending.isEmpty() && state_.value("consolidation_used").toInt() >= budget("consolidation_attempts")) {
        for (qsizetype index = cursor; index < portfolios.size(); ++index) {
            append(state_, "portfolios", overlay(portfolios.at(index).toObject(),
                {{"status", "SKIPPED"}, {"reason", "CONSOLIDATION_BUDGET_EXHAUSTED"}}));
        }
        state_.insert("portfolio_cursor", portfolios.size());
        verdict();
        return;
    }
    const auto portfolio = portfolios.at(cursor).toObject();
    const auto id = portfolio.value("id").toString();
    QJsonObject reports;
    for (const auto &entry : state_.value("attempts").toArray()) {
        const auto report = entry.toObject();
        reports.insert(report.value("id").toString(), report);
    }
    QJsonArray members;
    QSet<QString> represented;
    for (const auto &value : portfolio.value("members").toArray()) {
        const auto member = value.toString();
        const auto report = reports.value(member).toObject();
        const auto spec = candidate(member);
        members.append(overlay(spec, {{"status", report.value("status")},
            {"dependencies", spec.value("dependencies").toArray()}, {"exclusions", spec.value("exclusions").toArray()}}));
        represented.insert(spec.value("problem").toString());
    }
    auto merged = mergeDecisions(members, config_.value("ownership").toObject());
    if (represented.size() != config_.value("problems").toArray().size()) {
        append(merged, "conflicts", issueFinding("PROBLEM_COVERAGE_INCOMPLETE", "Un problème n'est pas représenté."));
    }
    const auto conflicts = merged.value("conflicts").toArray();
    if (!conflicts.isEmpty()) {
        append(state_, "portfolios", overlay(portfolio, {{"status", "REJECTED"}, {"conflicts", conflicts}}));
        state_.insert("portfolio_cursor", cursor + 1);
        return;
    }
    if (pending.isEmpty()) {
        state_.insert("consolidation_used", state_.value("consolidation_used").toInt() + 1);
        pending = overlay(portfolio, merged);
        state_.insert("pending_consolidation", pending);
        checkpoint();
    }
    const auto assignments = overlay(config_.value("base").toObject(), pending.value("assignments").toObject());
    const auto built = operation("build", "consolidations", id,
        [&](const QDir &target) { return backend_.build(assignments, target); });
    if (built.value("status") == "ERROR" || built.value("sha256").toString().isEmpty()) {
        append(state_, "portfolios", overlay(pending, {{"status", "ERROR"}, {"build", built}, {"rollback", true}}));
        state_.remove("pending_consolidation");
        state_.insert("portfolio_cursor", cursor + 1);
        transition("DIAGNOSE_CONSOLIDATION");
        return;
    }
    pending.insert("build", built);
    state_.insert("pending_consolidation", pending);
    transition("FINAL_REVALIDATION");
}

void Campaign::revalidate()
{
    auto pending = state_.value("pending_consolidation").toObject();
    const auto id = pending.value("id").toString();
    const auto built = pending.value("build").toObject();
    const auto sha = built.value("sha256");
    const auto result = operation("validate", "consolidations", id, [&](const QDir &target) {
        const auto native = fileInside(output_, built.value("path").toString());
        require(fileDigest(native) == sha, "Empreinte du natif avant rétrovalidation divergente");
        const auto observed = backend_.validate(built, target);
        require(fileDigest(native) == sha, "La rétrovalidation a modifié le natif");
        return observed;
    });
    const auto coverage = result.value("coverage").toArray();
    const bool proven = result.value("status") == "PASS" && result.value("native_sha256") == sha &&
        result.value("reference_sha256") == reference() &&
        hasMatchingDigest(output_, built, "path", "sha256") &&
        (!result.contains("report") || hasMatchingDigest(output_, result, "report", "report_sha256")) &&
        (!result.contains("evidence") || hasMatchingDigest(output_, result, "evidence", "evidence_sha256")) &&
        containsAll(coverage, config_.value("required_links").toArray()) &&
        containsAll(coverage, pending.value("affected_links").toArray());
    const auto status = proven ? QString("PASS") :
        result.value("status") == "PASS" ? QString("UNPROVEN") : result.value("status").toString();
    pending = overlay(pending, {{"status", status}, {"path", built.value("path")}, {"sha256", sha},
        {"metrics", result.value("metrics")}, {"reference_sha256", result.value("reference_sha256")},
        {"validation", result}, {"coverage", coverage}, {"rollback", !proven}});
    if (status == "UNPROVEN") {
        pending.insert("reason", "Empreinte, référence ou couverture indépendante insuffisante");
    }
    append(state_, "portfolios", pending);
    const auto portfolios = state_.value("portfolios").toArray();
    const auto comparison = compareCandidates(portfolios, config_.value("objectives").toArray(), reference());
    if (comparison.value("selected").isString()) {
        const auto winner = indexed(portfolios).value(comparison.value("selected").toString()).toObject();
        state_.insert("last_consolidated", winner);
        state_.insert("selected", winner.value("members"));
    }
    state_.remove("pending_consolidation");
    state_.insert("portfolio_cursor", state_.value("portfolio_cursor").toInt() + 1);
    transition(proven ? "CONSOLIDATE" : "DIAGNOSE_CONSOLIDATION");
}

QJsonObject Campaign::finalOutcome() const
{
    QJsonArray reasons;
    const auto integrated = state_.value("last_consolidated");
    if (!integrated.isObject()) {
        reasons.append(issueFinding("NO_REVALIDATED_CANDIDATE", "Aucune fusion n'a fourni la couverture indépendante demandée."));
    }
    const auto problems = state_.value("problem_state").toObject();
    for (auto it = problems.begin(); it != problems.end(); ++it) {
        const auto problem = it.value().toObject();
        if (problem.value("escalated") == true &&
            problem.value("families_considered").toArray().size() < budget("alternative_families")) {
            reasons.append(issueFinding("ALTERNATIVE_FAMILIES_INCOMPLETE",
                "Nombre de familles examinées insuffisant pour " + it.key(), "CONDITIONAL"));
        }
    }
    const auto unknowns = state_.value("unknowns").toObject();
    const auto declaredIssues = config_.value("issues").toObject();
    for (auto it = declaredIssues.begin(); it != declaredIssues.end(); ++it) {
        const auto issue = it.value().toObject();
        auto record = issue;
        record.insert("report", unknowns.value(it.key()).toObject().value("report"));
        if (issue.value("impact") != "ALTERNATIVE_ONLY" && !closesIssue(record)) {
            reasons.append(issueFinding(it.key(), issueReason(record),
                issue.value("impact") == "REQUIRED" ? "FAIL" : "CONDITIONAL"));
        }
    }
    if (config_.value("milestone") == "PHYSICAL") {
        reasons.append(issueFinding("PHYSICAL_EVIDENCE_REQUIRED", "Ce banc ne mesure aucun montage ni essai physique."));
    }
    const bool failed = std::any_of(reasons.begin(), reasons.end(), [](const auto &reason) {
        return reason.toObject().value("status") == "FAIL";
    });
    return {{"schema_version", 1}, {"finalized", true},
        {"milestone", config_.value("milestone")}, {"reference_sha256", reference()},
        {"verdict", failed ? "L5_FAIL" : reasons.isEmpty() ? "L5_PASS" : "L5_CONDITIONAL"},
        {"decision", failed ? "NO_GO_MOTIVE" : reasons.isEmpty() ? "GO" : "GO_CONDITIONNEL"},
        {"reasons", reasons}, {"consolidated", integrated}, {"detailed_used", state_.value("detailed_used")},
        {"consolidation_used", state_.value("consolidation_used")}, {"physical_go", false}};
}

void Campaign::verdict()
{
    QJsonObject comparisons;
    for (const auto &entry : config_.value("problems").toArray()) {
        const auto id = entry.toObject().value("id").toString();
        QJsonArray attempts;
        for (const auto &value : state_.value("attempts").toArray()) {
            if (value.toObject().value("problem") == id) {
                attempts.append(value);
            }
        }
        comparisons.insert(id, compareCandidates(attempts, config_.value("objectives").toArray(), reference()));
    }
    const auto portfolios = state_.value("portfolios").toArray();
    const auto comparison = compareCandidates(portfolios, config_.value("objectives").toArray(), reference());
    state_.insert("selection", QJsonObject{{"comparisons", comparisons}, {"portfolios", portfolios},
        {"consolidated", comparison}, {"selected", state_.value("selected")}, {"unknowns", state_.value("unknowns")}});
    state_.insert("outcome", finalOutcome());
    transition("VERDICT");
}

void Campaign::advance()
{
    const auto current = state_.value("state");
    if (current == "INVENTORY") {
        auto inventory = backend_.inventory();
        require(inventory.value("reference_sha256") == reference(), "Inventaire et référence de validation différents");
        state_.insert("inventory", inventory);
        transition("INVESTIGATE");
    } else if (current == "INVESTIGATE") {
        transition("GENERATE_FAMILIES");
    } else if (current == "GENERATE_FAMILIES" || current == "CORRECT") {
        transition("PRECHECK");
    } else if (current == "PRECHECK") {
        precheck();
    } else if (current == "BUILD") {
        const auto row = state_.value("current").toObject();
        const auto id = row.value("id").toString();
        const auto result = operation("build", "attempts", id,
            [&](const QDir &target) { return backend_.build(applied(row), target); });
        state_.insert("built", result);
        transition("VALIDATE");
    } else if (current == "VALIDATE") {
        const auto result = state_.take("built").toObject();
        recordAttempt(result);
    } else if (current == "DIAGNOSE") {
        diagnose();
    } else if (current == "CHANGE_FAMILY") {
        changeFamily();
    } else if (current == "CONSOLIDATE" || current == "DIAGNOSE_CONSOLIDATION") {
        consolidate();
    } else if (current == "FINAL_REVALIDATION") {
        revalidate();
    } else {
        require(false, "État de campagne inconnu : " + current.toString());
    }
}

} // namespace convergence
