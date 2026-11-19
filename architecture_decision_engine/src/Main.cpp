#include "Evidence.hpp"
#include "Exploration.hpp"
#include "InterconnectionAdapter.hpp"
#include "ProblemSpec.hpp"
#include "ResearchAdapter.hpp"

#include <QCommandLineParser>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLockFile>
#include <QSaveFile>
#include <QSysInfo>
#include <cstdio>
#include <stdexcept>

namespace {

using namespace architecture_decision;
const QString fixture = "architecture_decision_engine/fixtures/";

void require(bool condition, const QString &message)
{
    if (!condition) {
        throw std::runtime_error(message.toStdString());
    }
}

QByteArray read(const QString &path)
{
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "Lecture impossible : " + path);
    const auto bytes = file.readAll();
    require(file.error() == QFileDevice::NoError, "Lecture incomplète : " + path);
    return bytes;
}

QString sha(const QByteArray &bytes)
{
    return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
}

QString fileSha(const QString &path)
{
    QFile file(path);
    QCryptographicHash hash(QCryptographicHash::Sha256);
    require(file.open(QIODevice::ReadOnly) && hash.addData(&file), "Empreinte impossible : " + path);
    return QString::fromLatin1(hash.result().toHex());
}

QJsonObject json(const QByteArray &bytes, const QString &source)
{
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(bytes, &error);
    require(document.isObject(), source + " : " + error.errorString());
    return document.object();
}

QString write(const QString &path, const QJsonObject &value)
{
    QSaveFile file(path);
    const auto bytes = QJsonDocument(value).toJson(QJsonDocument::Indented);
    require(file.open(QIODevice::WriteOnly) && file.write(bytes) == bytes.size() && file.commit(),
            "Publication impossible : " + path);
    return sha(bytes);
}

QString relative(const QDir &root, const QString &path)
{
    const auto p = root.relativeFilePath(path);
    require(!p.isEmpty() && p != "." && p != ".." && !p.startsWith("../") && !QDir::isAbsolutePath(p),
            "Chemin hors espace de travail : " + path);
    return p;
}

struct Inputs {
    const QDir &root;
    QMap<QString, QByteArray> contents;
    QJsonArray references;

    QByteArray capture(const QString &id, const QString &path, const QString &kind = "other")
    {
        const auto absolute = QFileInfo(root.absoluteFilePath(path)).canonicalFilePath();
        require(!absolute.isEmpty() && QFileInfo(absolute).isFile(), "Entrée absente : " + path);
        const auto workspacePath = relative(root, absolute);
        const auto bytes = read(absolute);
        contents.insert(absolute, bytes);
        references.append(QJsonObject{{"input_id", id}, {"kind", kind},
            {"reference", QJsonObject{{"path", workspacePath}}}, {"checksums", QJsonObject{{"sha256", sha(bytes)}}}});
        return bytes;
    }

    void verify() const
    {
        for (auto it = contents.begin(); it != contents.end(); ++it) {
            require(read(it.key()) == it.value(), "Entrée modifiée pendant le banc : " + it.key());
        }
    }
};

int runProblemSpec(const QCommandLineParser &options)
{
    for (const auto &key : {"request", "domain", "model", "observation", "output"}) {
        require(options.isSet(key), "Option requise : --" + QString(key));
    }
    const QFileInfo workspace(options.value("root"));
    require(workspace.isDir(), "Racine du dépôt absente");
    const QDir root(workspace.canonicalFilePath());
    const QFileInfo output(QDir::cleanPath(root.absoluteFilePath(options.value("output"))));
    relative(root, output.absoluteFilePath());
    const QFileInfo parent(output.absolutePath());
    require(parent.isDir() && parent.canonicalFilePath() == parent.absoluteFilePath(),
            "Dossier parent absent ou redirigé");
    QLockFile lock(output.absoluteFilePath() + ".lock");
    require(lock.tryLock(), "Publication du problème déjà en cours");
    require(!output.exists() && !output.isSymLink(), "Un fichier de sortie neuf est requis");

    Inputs inputs{root, {}, {}};
    const auto requestBytes = inputs.capture("v3_problem_request", options.value("request"));
    const auto domainBytes = inputs.capture("v3_parametric_domain", options.value("domain"));
    const auto observation = inputs.capture("v3_native_observation", options.value("observation"));
    parseProblemObject(observation, options.value("observation"));
    const QFileInfo model(root.absoluteFilePath(options.value("model")));
    require(model.isFile() && model.size() > 0, "Natif XLink absent ou vide");
    const auto modelPath = model.canonicalFilePath();
    relative(root, modelPath);
    const ProblemSources sources{parseProblemObject(domainBytes, options.value("domain")),
                                 sha(domainBytes), fileSha(modelPath), sha(observation)};
    std::optional<BaseProblem> base;
    if (options.isSet("base-problem")) {
        const auto bytes = inputs.capture("v3_base_problem", options.value("base-problem"));
        base = BaseProblem{parseProblemObject(bytes, options.value("base-problem")), sha(bytes)};
    }
    const auto problem = validateProblemSpec(parseProblemObject(requestBytes, options.value("request")), sources, base);
    inputs.verify();
    require(fileSha(modelPath) == sources.modelSha256, "Natif XLink modifié pendant la préparation");
    const auto outputSha = write(output.absoluteFilePath(), problem);
    std::printf("%s\n", outputSha.toLatin1().constData());
    return 0;
}

QJsonObject indexedBenches(const QJsonObject &source)
{
    require(source.value("schema_version") == "1.0.0" && source.value("scope") == "SYNTHETIC_BENCH",
            "Version ou périmètre de banc inconnu");
    QJsonObject entries;
    for (const auto &entry : source.value("benches").toArray()) {
        const auto object = entry.toObject();
        const auto id = object.value("id").toString();
        require(!id.isEmpty() && !entries.contains(id), "Banc sans identifiant unique");
        entries.insert(id, object);
    }
    require(!entries.isEmpty(), "Aucun banc déclaré");
    return entries;
}

QJsonValue lookup(QJsonValue value, const QJsonArray &path)
{
    for (const auto &part : path) {
        if (part.isString() && value.isObject()) {
            value = value.toObject().value(part.toString());
        } else if (part.isDouble() && value.isArray()) {
            value = value.toArray().at(part.toInt(-1));
        } else {
            return QJsonValue::Undefined;
        }
    }
    return value;
}

QJsonObject acceptance(const QJsonObject &policy, const QDir &output, const QMap<QString, QString> &published)
{
    const auto checks = policy.value("checks").toArray();
    require(policy.value("schema_version") == "1.0.0" && !checks.isEmpty(), "Critères de réception absents");
    QJsonArray findings;
    QString verdict = "L3_PASS";
    for (const auto &entry : checks) {
        const auto check = entry.toObject();
        const auto path = check.value("artifact").toString();
        const auto expected = check.value("equals");
        require(!path.isEmpty() && !expected.isUndefined() && check.value("path").isArray() &&
                (check.value("criticality") == "REQUIRED" || check.value("criticality") == "ADDITIONAL"),
                "Critère de réception invalide");
        QJsonValue observed = QJsonValue::Undefined;
        if (published.contains(path)) {
            const auto content = read(output.filePath(path));
            require(sha(content) == published.value(path), "Preuve modifiée : " + path);
            observed = lookup(json(content, path), check.value("path").toArray());
        }
        const bool pass = observed == expected;
        if (!pass && check.value("criticality") == "REQUIRED") {
            verdict = "L3_FAIL";
        } else if (!pass && verdict == "L3_PASS") {
            verdict = "L3_CONDITIONAL";
        }
        auto finding = check;
        finding.insert("observed", observed.isUndefined() ? QJsonValue(QJsonValue::Null) : observed);
        finding.insert("status", pass ? "PASS" : "FAIL");
        findings.append(finding);
    }
    return {{"verdict", verdict}, {"checks", findings}};
}

int run(const QCommandLineParser &options)
{
    const auto workspace = QFileInfo(options.value("root")).canonicalFilePath();
    require(!workspace.isEmpty() && QFileInfo(workspace).isDir(), "Racine du dépôt absente");
    const QDir root(workspace);
    const auto output = QDir::cleanPath(root.absoluteFilePath(options.value("output")));
    require(options.isSet("output") && !QFileInfo::exists(output), "Un dossier de sortie neuf est requis");
    relative(root, output);
    const auto parent = QFileInfo(output).absolutePath();
    const auto parentCanonical = QFileInfo(parent).canonicalFilePath();
    require(!parentCanonical.isEmpty(), "Le dossier parent doit déjà exister");
    relative(root, QDir(parentCanonical).filePath(QFileInfo(output).fileName()));
    const QDir target(output);
    const auto executable = QFileInfo(root.absoluteFilePath(options.value("l1"))).canonicalFilePath();
    require(!executable.isEmpty() && QFileInfo(executable).isFile(), "Exécutable L1 absent");

    Inputs inputs{root, {}, {}};
    const auto benchesPath = options.value("benches");
    const auto requirementsPath = options.value("requirements");
    const auto policyPath = options.value("acceptance");
    const auto benchesBytes = inputs.capture("l3_benches", benchesPath, "scenario");
    const auto requirementBytes = inputs.capture("l3_requirements", requirementsPath);
    const auto benches = json(benchesBytes, benchesPath);
    const auto rules = indexedBenches(json(requirementBytes, requirementsPath));
    const auto benchIndex = indexedBenches(benches);
    require(benchIndex.keys() == rules.keys(), "Couverture de la fixture et des exigences différente");
    const auto policy = json(inputs.capture("l3_acceptance", policyPath), policyPath);
    const auto sourcePath = "interconnection_engine/examples/banc_l2.json";
    const auto projectionPath = fixture + "f31_interconnection.json";
    const auto catalog = fixture + "f31_research.json";
    const auto l2 = json(inputs.capture("l2_bench", sourcePath, "model"), sourcePath);
    const auto projection = json(inputs.capture("l3_f31_projection", projectionPath), projectionPath);
    inputs.capture("l1_catalog", catalog);
    inputs.capture("l1_straight_observation", fixture + "f31_straight_observation.json");
    inputs.capture("l0_contract", "docs/electromechanical_v2/DATA_CONTRACTS.schema.json");
    inputs.capture("l1_contract", "docs/electromechanical_v2/RESEARCH_REPORT.schema.json");
    const auto researchSha = sha(read(executable));
    const auto baseline = QJsonObject{{"schema_version", "1.0.0"}, {"scope", "SYNTHETIC_BENCH"},
        {"inputs", inputs.references}};

    require(QDir(parent).mkdir(QFileInfo(output).fileName()), "Création du dossier neuf impossible");
    require(target.mkdir("candidates"), "Création du dossier des candidats impossible");
    QJsonObject parameters{{"seed", benches.value("seed")}, {"enumeration", benches.value("enumeration")}};
    const QJsonObject software{{"qt_version", QString::fromLatin1(qVersion())},
        {"os", QSysInfo::prettyProductName()}, {"architecture", QSysInfo::currentCpuArchitecture()},
#if defined(_MSC_VER)
        {"compiler", QString("MSVC %1").arg(_MSC_VER)},
#elif defined(__VERSION__)
        {"compiler", QString::fromLatin1(__VERSION__)},
#endif
        {"l1_executable_sha256", researchSha},
        {"l3_executable_sha256", sha(read(QCoreApplication::applicationFilePath()))}};
    Evidence evidence(output, inputs.references, parameters, software);
    QMap<QString, QString> published;
    const auto publish = [&](const QString &path, const QJsonObject &object) {
        require(!published.contains(path), "Sortie dupliquée : " + path);
        const auto hash = write(target.filePath(path), object);
        published.insert(path, hash);
        return hash;
    };
    const auto baselineSha = publish("baseline.json", baseline);
    const auto requirementsSha = sha(requirementBytes);
    const auto interconnection = [&](const QJsonObject &p, const QJsonArray &research) {
        return validateInterconnection(l2, p, projection, research);
    };
    const auto research = [&](const QString &issue) {
        return researchIssue(executable, root.absolutePath(), target.filePath("research-cache"), catalog, issue);
    };
    QJsonObject results, decisions, comparison;
    for (auto it = benchIndex.begin(); it != benchIndex.end(); ++it) {
        const auto result = explore(it.value().toObject(), rules.value(it.key()).toObject(),
                                    baselineSha, requirementsSha, interconnection, research, publish);
        results.insert(it.key(), result);
        comparison.insert(it.key(), result.value("comparison"));
        for (const auto &entry : result.value("decisions").toArray()) {
            const auto key = entry.toObject().value("id").toString();
            require(!decisions.contains(key), "Identifiant de décision dupliqué dans la campagne");
            decisions.insert(key, entry);
        }
    }
    publish("decisions.json", {{"schema_version", "1.0.0"}, {"scope", "SYNTHETIC_BENCH"}, {"decisions", decisions}});
    publish("comparison.json", comparison);
    const auto outcome = acceptance(policy, target, published);
    const auto verdict = outcome.value("verdict");
    inputs.verify();
    require(sha(read(executable)) == researchSha, "Exécutable L1 modifié pendant le banc");
    const QJsonObject campaign{{"schema_version", "1.0.0"}, {"scope", "SYNTHETIC_BENCH"},
        {"finalized", true}, {"verdict", verdict}, {"baseline_sha256", baselineSha},
        {"requirements_sha256", requirementsSha}, {"parameters", parameters},
        {"benches", results}, {"acceptance", outcome.value("checks")},
        {"decisions_sha256", published.value("decisions.json")}};
    publish("campaign.json", campaign);
    evidence.finalize(campaign, published);
    const auto bytes = QJsonDocument(campaign).toJson(QJsonDocument::Indented);
    require(std::fwrite(bytes.constData(), 1, bytes.size(), stdout) == static_cast<std::size_t>(bytes.size()) &&
            std::fflush(stdout) == 0, "Publication du résultat sur stdout impossible");
    return verdict == "L3_PASS" ? 0 : verdict == "L3_CONDITIONAL" ? 3 : 2;
}

} // namespace

int main(int argc, char **argv)
{
    const QCoreApplication application(argc, argv);
    QCommandLineParser options;
    options.setApplicationDescription("Bancs d’exploration d’architectures électromécaniques L3");
    options.addHelpOption();
    options.addPositionalArgument("commande", "Tests historiques (par défaut) ou v3-problem");
    options.addOptions({
        {"root", "Racine du dépôt", "path", "."},
        {"output", "Dossier historique ou fichier problem_spec.json neuf", "path"},
        {"l1", "Exécutable du moteur L1", "path"},
        {"benches", "Définition des bancs", "path", fixture + "benches.json"},
        {"requirements", "Exigences des bancs", "path", fixture + "requirements.json"},
        {"acceptance", "Critères de réception", "path", fixture + "acceptance.json"},
        {"request", "Paramètres du problème V3", "path"},
        {"domain", "Domaine paramétrique scellé", "path"},
        {"model", "Fichier natif racine du modèle XLink", "path"},
        {"observation", "Observation indépendante de géométrie de référence", "path"},
        {"base-problem", "Problem_spec T1 pour une restriction T2", "path"}
    });
    options.process(application);
    try {
        const auto commands = options.positionalArguments();
        if (commands == QStringList{"v3-problem"}) {
            return runProblemSpec(options);
        }
        require(commands.isEmpty(), "Commande L3 inconnue");
        return run(options);
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
