#include "Graph.hpp"
#include "Import.hpp"

#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QTemporaryFile>
#include <cstdio>
#include <stdexcept>

namespace {

QJsonObject read(const QString &path, const QString &expectedSha256 = {})
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly))
        throw std::runtime_error((path + " : " + file.errorString()).toStdString());
    const auto bytes = file.readAll();
    if (!expectedSha256.isEmpty() &&
        QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex() != expectedSha256.toLatin1())
        throw std::runtime_error((path + " : empreinte SHA-256 divergente").toStdString());
    const auto document = QJsonDocument::fromJson(bytes);
    if (file.error() != QFileDevice::NoError || !document.isObject())
        throw std::runtime_error((path + " : objet JSON attendu").toStdString());
    return document.object();
}

void write(const QString &path, const QJsonObject &result)
{
    const auto bytes = QJsonDocument(result).toJson(QJsonDocument::Indented);
    if (!path.isEmpty()) {
        const QFileInfo target(path);
        if (target.exists() || target.suffix().compare("json", Qt::CaseInsensitive) != 0)
            throw std::runtime_error((path + " : une nouvelle destination JSON est requise").toStdString());
        QTemporaryFile output(target.absolutePath() + "/.v3-XXXXXX");
        if (!output.open() || output.write(bytes) != bytes.size() || !output.flush())
            throw std::runtime_error((path + " : " + output.errorString()).toStdString());
        output.close();
        if (!output.rename(target.absoluteFilePath()))
            throw std::runtime_error((path + " : " + output.errorString()).toStdString());
        output.setAutoRemove(false);
    } else if (std::fwrite(bytes.constData(), 1, bytes.size(), stdout) != static_cast<std::size_t>(bytes.size()) ||
               std::fflush(stdout) != 0) {
        throw std::runtime_error("Écriture JSON impossible");
    }
}

QString take(QStringList &args, const QString &option)
{
    const auto at = args.indexOf(option);
    if (at < 0)
        return {};
    if (at + 1 == args.size() || args.at(at + 1).startsWith("--"))
        throw std::runtime_error(("Valeur manquante : " + option).toStdString());
    args.removeAt(at);
    return args.takeAt(at);
}

} // namespace

int main(int argc, char **argv)
{
    const QCoreApplication application(argc, argv);
    auto args = application.arguments().mid(1);
    if (args.isEmpty() || args == QStringList{"--help"}) {
        std::puts("electromechanical_graph_core import RACINE NATIF_JSON AUTORITES_RELATIF --native-sha256 HEX [--cartographe-l2] [--output NOUVEAU_JSON]\n"
                  "electromechanical_graph_core validate GRAPHE [--root RACINE] [--graph-sha256 HEX]\n"
                  "electromechanical_graph_core impact GRAPHE MOVE|RETENTION|FRAME CIBLE [--root RACINE] [--graph-sha256 HEX] [--output NOUVEAU_JSON]\n"
                  "electromechanical_graph_core compare-frames REQUETE [--output JSON]");
        return args.isEmpty() ? 1 : 0;
    }
    using namespace electromechanical::graph;
    try {
        const auto command = args.takeFirst();
        const auto output = take(args, "--output");
        const auto root = take(args, "--root");
        const auto graphDigest = take(args, "--graph-sha256");
        QJsonObject result;
        if (command == "import" && root.isEmpty() && graphDigest.isEmpty()) {
            const bool l2 = args.removeOne("--cartographe-l2");
            const auto digest = take(args, "--native-sha256");
            if (args.size() != 3 || digest.size() != 64)
                throw std::runtime_error("import attend une racine, un inventaire natif épinglé et un fichier d'autorités relatif");
            result = importGraph(args[0], read(args[1], digest), args[2], l2);
        } else if (command == "validate" && args.size() == 1) {
            const auto graph = read(args[0], graphDigest);
            validate(graph);
            if (!root.isEmpty())
                verifySources(root, graph.value("sources").toObject());
            result = {{"status", "PASS"}, {"source_bytes_verified", !root.isEmpty()},
                      {"graph_bytes_verified", !graphDigest.isEmpty()}};
        } else if (command == "impact" && args.size() == 3) {
            const auto graph = read(args[0], graphDigest);
            if (!root.isEmpty())
                verifySources(root, graph.value("sources").toObject());
            result = impact(graph, args[1], args[2]);
        } else if (command == "compare-frames" && args.size() == 1 && root.isEmpty() && graphDigest.isEmpty()) {
            result = compareFrames(read(args[0]));
        } else {
            throw std::runtime_error("Commande ou arguments inconnus (voir --help)");
        }
        write(output, result);
        return command == "compare-frames" && result.value("status") == "FAIL" ? 2 : 0;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
