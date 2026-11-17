#include "Research.hpp"

#include <QCommandLineParser>
#include <QCoreApplication>
#include <QFile>
#include <QJsonDocument>

#include <cstdio>
#include <stdexcept>

using namespace Qt::StringLiterals;

int main(int argc, char **argv)
{
    QCoreApplication application(argc, argv);
    QCoreApplication::setApplicationName(u"technical_research_core"_s);
    QCommandLineParser parser;
    parser.setApplicationDescription(u"Investigation technique hors ligne par défaut."_s);
    const auto help = parser.addHelpOption();
    parser.addPositionalArgument(u"command"_s, u"submit, get, list, invalidate"_s);
    parser.addOptions({
        {u"root"_s, u"Racine des sources locales"_s, u"path"_s},
        {u"store"_s, u"Dossier des rapports et du cache"_s, u"path"_s},
        {u"catalog"_s, u"Catalogue de questions et sources"_s, u"path"_s},
        {u"issue"_s, u"Identifiant du point à instruire"_s, u"id"_s},
        {u"view"_s, u"reports, evidence ou unknowns"_s, u"view"_s},
        QCommandLineOption(u"online"_s, u"Autoriser les sources HTTPS configurées"_s),
        QCommandLineOption(u"refresh"_s, u"Rejouer l'investigation"_s),
    });

    technical_research::Result result;
    try {
        if (!parser.parse(application.arguments()))
            throw std::runtime_error(parser.errorText().toUtf8().constData());
        if (parser.isSet(help))
            parser.showHelp();
        if (parser.positionalArguments().size() != 1)
            throw std::runtime_error("Une sous-commande est requise");
        const auto required = [&parser](const QString &option) {
            const auto value = parser.value(option);
            if (value.trimmed().isEmpty())
                throw std::runtime_error((u"Option requise : --"_s + option).toUtf8().constData());
            return value;
        };
        const auto command = parser.positionalArguments().first();
        const auto store = required(u"store"_s);
        if (command == u"submit") {
            result = technical_research::submit(required(u"root"_s), store, required(u"catalog"_s),
                required(u"issue"_s), parser.isSet(u"online"_s), parser.isSet(u"refresh"_s));
        } else if (command == u"get") {
            result = technical_research::get(required(u"root"_s), store, required(u"issue"_s));
        } else if (command == u"list") {
            result = technical_research::list(required(u"root"_s), store, required(u"view"_s));
        } else if (command == u"invalidate") {
            result = technical_research::invalidate(store, required(u"issue"_s));
        } else {
            throw std::runtime_error("Sous-commande inconnue");
        }
    } catch (const std::exception &error) {
        result = {{{u"error"_s, u"RESEARCH_ERROR"_s},
                   {u"message"_s, QString::fromUtf8(error.what())}}, 1};
    }
    QFile output;
    if (!output.open(stdout, QIODevice::WriteOnly))
        return 1;
    const auto bytes = QJsonDocument(result.json).toJson(QJsonDocument::Indented);
    if (output.write(bytes) != bytes.size() || !output.flush())
        return 1;
    return result.exitCode;
}
