#include "Interconnection.hpp"
#include "Reconcile.hpp"

#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QJsonDocument>
#include <QSaveFile>
#include <cstdio>
#include <stdexcept>

namespace {

QJsonObject read(const QString &path, QString &digest)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        throw std::runtime_error((path + " : " + file.errorString()).toStdString());
    }
    const auto bytes = file.readAll();
    if (file.error() != QFileDevice::NoError) {
        throw std::runtime_error((path + " : " + file.errorString()).toStdString());
    }
    digest = QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(bytes, &error);
    if (!document.isObject()) {
        throw std::runtime_error((path + " : objet JSON attendu : " + error.errorString()).toStdString());
    }
    return document.object();
}

QString option(QStringList &args, const QString &key, const QString &fallback = {})
{
    const auto position = args.indexOf(key);
    if (position < 0) {
        return fallback;
    }
    if (position == args.size() - 1 || args[position + 1].startsWith("--")) {
        throw std::runtime_error(("Valeur attendue pour " + key).toStdString());
    }
    args.removeAt(position);
    return args.takeAt(position);
}

} // namespace

int main(int argc, char **argv)
{
    const QCoreApplication application(argc, argv);
    auto args = application.arguments().mid(1);
    if (args.isEmpty() || args == QStringList{"--help"}) {
        std::puts("interconnection_core validate DOSSIER [--state ID] [--research RAPPORT]... [--output JSON]\n"
                  "interconnection_core mates DOSSIER EMBASE [--output JSON]\n"
                  "interconnection_core reconcile --root DEPOT [--output JSON]\n"
                  "interconnection_core inspect-cartographe --root DEPOT [--output JSON]");
        return args.isEmpty() ? 1 : 0;
    }
    try {
        const auto command = args.takeFirst();
        const auto output = option(args, "--output");
        QJsonObject report;
        if (command == "validate") {
            const auto state = option(args, "--state", "nominal");
            QJsonArray research, digests;
            while (args.contains("--research")) {
                QString sha;
                const auto item = read(option(args, "--research"), sha);
                research.append(item);
                digests.append(QJsonObject{{"issue_id", item.value("issue_id")}, {"sha256", sha}});
            }
            if (args.size() != 1) {
                throw std::runtime_error("validate attend un dossier JSON");
            }
            QString sha;
            const auto dossier = read(args.first(), sha);
            report = interconnection::validate(dossier, state, research);
            report.insert("input_sha256", sha);
            report.insert("research_sha256", digests);
        } else if (command == "mates" && args.size() == 2) {
            QString sha;
            const auto dossier = read(args.first(), sha);
            report = interconnection::findCompatibleMates(dossier, args.last());
            report.insert("input_sha256", sha);
        } else if (command == "reconcile" || command == "inspect-cartographe") {
            const auto root = option(args, "--root", ".");
            if (!args.isEmpty()) {
                throw std::runtime_error("Option inconnue pour le rapprochement cartographe");
            }
            report = command == "reconcile" ? interconnection::reconcileInterconnections(root)
                                             : interconnection::inspectCartographeInterfaces(root);
        } else {
            throw std::runtime_error("Commande ou arguments inconnus (voir --help)");
        }
        const auto bytes = QJsonDocument(report).toJson(QJsonDocument::Indented);
        if (!output.isEmpty()) {
            QSaveFile target(output);
            if (!target.open(QIODevice::WriteOnly) || target.write(bytes) != bytes.size() || !target.commit()) {
                throw std::runtime_error((output + " : " + target.errorString()).toStdString());
            }
        }
        if (std::fwrite(bytes.constData(), 1, bytes.size(), stdout) != static_cast<std::size_t>(bytes.size()) ||
            std::fflush(stdout) != 0) {
            throw std::runtime_error("Écriture du rapport sur stdout impossible");
        }
        if (command == "validate" && report.value("status") == "FAIL") {
            return 2;
        }
        return command == "validate" && report.value("status") == "INCONCLUSIVE" ? 3 : 0;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
