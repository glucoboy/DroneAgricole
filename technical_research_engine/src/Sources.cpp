#include "Sources.hpp"

#include <QCryptographicHash>
#include <QDir>
#include <QEventLoop>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMetaEnum>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QRegularExpression>
#include <QStringDecoder>
#include <QTimer>
#include <QUrl>

#include <cmath>
#include <stdexcept>
#include <utility>

namespace technical_research {
namespace {

constexpr qsizetype maxSourceBytes = 16 * 1024 * 1024;
constexpr int networkTimeoutMs = 8000;

SourceInput sourceFailure(const QString &code, const QString &message)
{
    return {{}, {}, code, message};
}

SourceInput sourceRead(QByteArray bytes)
{
    const auto hash = QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex();
    return {std::move(bytes), QString::fromLatin1(hash), {}, {}};
}

QStringList pointerSegments(const QString &pointer)
{
    if (pointer.isEmpty()) {
        return {};
    }
    if (!pointer.startsWith('/') || QRegularExpression("~(?:[^01]|$)").match(pointer).hasMatch()) {
        throw std::runtime_error("Pointeur JSON invalide");
    }
    auto segments = pointer.mid(1).split('/');
    for (auto &segment : segments) {
        segment.replace("~1", "/");
        segment.replace("~0", "~");
    }
    return segments;
}

QJsonValue resolvePointer(QJsonValue value, const QStringList &segments)
{
    for (const auto &segment : segments) {
        if (value.isObject()) {
            value = value.toObject().value(segment);
        } else if (value.isArray()) {
            static const QRegularExpression arrayIndex("^(?:0|[1-9][0-9]*)$");
            bool indexValid = false;
            const auto index = segment.toLongLong(&indexValid);
            const auto array = value.toArray();
            if (!indexValid || !arrayIndex.match(segment).hasMatch() || index >= array.size()) {
                throw std::runtime_error("Indice de tableau JSON introuvable");
            }
            value = array.at(index);
        } else {
            throw std::runtime_error("Pointeur JSON introuvable");
        }
    }
    if (value.isUndefined()) {
        throw std::runtime_error("Pointeur JSON introuvable");
    }
    return value;
}

bool containsReference(const QString &text, const QString &partNumber)
{
    // A part number embedded in a longer MPN or revision cannot establish identity.
    const QRegularExpression pattern(
        "(?<![\\p{L}\\p{N}_.+/-])" + QRegularExpression::escape(partNumber)
        + "(?![\\p{L}\\p{N}_.+/-])");
    return pattern.match(text).hasMatch();
}

bool matchesReferenceField(const QString &observed, const QString &partNumber,
                           const QString &explicitPattern)
{
    if (explicitPattern.isEmpty()) {
        return observed == partNumber;
    }
    const QRegularExpression pattern(QRegularExpression::anchoredPattern(explicitPattern));
    if (explicitPattern.size() > 2048 || !pattern.isValid() || pattern.captureCount() != 1) {
        throw std::runtime_error("Sélecteur d'identité JSON invalide");
    }
    const auto match = pattern.match(observed);
    return match.hasMatch() && match.captured(1) == partNumber;
}

QJsonValue extractJson(const QByteArray &bytes, const QJsonObject &extraction,
                       const QString &partNumber)
{
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(bytes, &error);
    if (error.error != QJsonParseError::NoError) {
        throw std::runtime_error("Document JSON illisible");
    }
    const QJsonValue root = document.isArray() ? QJsonValue(document.array())
                                               : QJsonValue(document.object());
    if (!extraction.value("value").isString() || !extraction.value("checks").isObject()) {
        throw std::runtime_error("Sélecteurs JSON manquants");
    }
    const auto valueSegments = pointerSegments(extraction.value("value").toString());
    const auto checks = extraction.value("checks").toObject();
    const auto referenceCheck = extraction.value("reference_check").toObject();
    const auto referencePointer = referenceCheck.value("pointer").toString();
    const auto referencePattern = referenceCheck.value("pattern").toString();
    if (extraction.contains("reference_check")
        && (referencePattern.isEmpty() || !checks.contains(referencePointer))) {
        throw std::runtime_error("Le sélecteur d'identité JSON doit cibler un contrôle déclaré");
    }
    bool referenceMatched = false;
    for (auto check = checks.begin(); check != checks.end(); ++check) {
        const auto segments = pointerSegments(check.key());
        const auto observed = resolvePointer(root, segments);
        if (observed != check.value()) {
            throw std::runtime_error("Contrôle d'identité ou de contexte JSON non satisfait");
        }
        const auto referenceIndex = segments.indexOf(partNumber);
        const auto containerSize = segments.size() - 1;
        const bool sameKey = referenceIndex >= 0
            && valueSegments.mid(0, referenceIndex + 1) == segments.mid(0, referenceIndex + 1);
        const bool sameContainer = containerSize >= 0 && valueSegments.size() > containerSize
            && valueSegments.mid(0, containerSize) == segments.mid(0, containerSize);
        const bool fieldMatches = sameContainer && observed.isString()
            && matchesReferenceField(observed.toString(), partNumber,
                                     check.key() == referencePointer ? referencePattern : QString());
        referenceMatched = referenceMatched || sameKey || fieldMatches;
    }
    if (!referenceMatched) {
        throw std::runtime_error("Référence exacte absente des contrôles JSON");
    }
    const auto value = resolvePointer(root, valueSegments);
    if (value.isNull()) {
        throw std::runtime_error("La source déclare la valeur absente (null JSON)");
    }
    return value;
}

QJsonValue extractText(const QByteArray &bytes, const QJsonObject &extraction,
                       const QString &partNumber)
{
    QStringDecoder decoder(QStringDecoder::Utf8);
    const QString text = decoder(bytes);
    if (decoder.hasError()) {
        throw std::runtime_error("Document texte non UTF-8");
    }
    if (!extraction.value("markers").isArray()) {
        throw std::runtime_error("Liste de marqueurs texte manquante");
    }
    const auto markers = extraction.value("markers").toArray();
    for (const auto &marker : markers) {
        if (marker.toString().isEmpty() || !text.contains(marker.toString())) {
            throw std::runtime_error("Marqueur documentaire attendu absent du texte");
        }
    }
    const auto patternText = extraction.value("pattern").toString();
    const QRegularExpression pattern(patternText);
    if (patternText.size() > 2048 || !pattern.isValid() || pattern.captureCount() != 1) {
        throw std::runtime_error("Expression d'extraction invalide ou sans capture unique");
    }
    auto matches = pattern.globalMatch(text);
    if (!matches.hasNext()) {
        throw std::runtime_error("Valeur attendue absente du texte");
    }
    const auto match = matches.next();
    const auto value = match.captured(1).trimmed();
    if (value.isEmpty() || matches.hasNext()) {
        throw std::runtime_error("Valeur d'extraction vide ou ambiguë");
    }
    if (!containsReference(match.captured(0), partNumber)) {
        throw std::runtime_error("Référence exacte absente du passage extrait");
    }
    const auto type = extraction.value("value_type").toString();
    if (type == "STRING") {
        return value;
    }
    if (type == "BOOLEAN" && (value == "true" || value == "false")) {
        return value == "true";
    }
    bool parsed = false;
    if (type == "NUMBER") {
        const auto number = value.toDouble(&parsed);
        if (parsed && std::isfinite(number)) {
            return number;
        }
    }
    throw std::runtime_error("Valeur de type inattendu");
}

} // namespace

SourceInput readLocalSource(const QString &root, const QString &relativePath)
{
    const auto rootPath = QFileInfo(root).canonicalFilePath();
    const auto requestedPath = QDir::fromNativeSeparators(relativePath);
    if (rootPath.isEmpty() || !QFileInfo(rootPath).isDir() || requestedPath.isEmpty()
        || QDir::isAbsolutePath(requestedPath) || requestedPath.contains(':')
        || requestedPath.contains('\\') || requestedPath.contains(QChar::Null)
        || requestedPath.split('/').contains("..")) {
        return sourceFailure("SOURCE_PATH_INVALID", "Chemin hors du référentiel local");
    }
    const QFileInfo candidate(QDir(rootPath).filePath(requestedPath));
    const auto path = candidate.canonicalFilePath();
    if (path.isEmpty()) {
        return sourceFailure("SOURCE_NOT_FOUND", "Fichier source introuvable");
    }
    const auto rootPrefix = rootPath.endsWith('/') ? rootPath : rootPath + '/';
    if (!path.startsWith(rootPrefix) || !candidate.isFile()) {
        return sourceFailure("SOURCE_PATH_INVALID", "La source doit être un fichier dans le référentiel");
    }
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        return sourceFailure("SOURCE_READ_FAILED", "Ouverture de la source impossible");
    }
    if (file.size() > maxSourceBytes) {
        return sourceFailure("SOURCE_TOO_LARGE", "Source au-delà de 16 Mio");
    }
    auto bytes = file.read(maxSourceBytes + 1);
    if (file.error() != QFileDevice::NoError) {
        return sourceFailure("SOURCE_READ_FAILED", "Lecture de la source interrompue");
    }
    if (bytes.size() > maxSourceBytes) {
        return sourceFailure("SOURCE_TOO_LARGE", "Source au-delà de 16 Mio");
    }
    return sourceRead(std::move(bytes));
}

SourceInput readRemoteSource(const QString &uri)
{
    const QUrl url(uri, QUrl::StrictMode);
    if (!url.isValid() || url.scheme() != "https" || url.host().isEmpty()
        || url.authority().contains('@') || url.hasQuery()) {
        return sourceFailure("NETWORK_URL_INVALID", "URL HTTPS sans identifiants ni chaîne de requête requise");
    }
    QNetworkAccessManager manager;
    QNetworkRequest request(url.adjusted(QUrl::RemoveFragment));
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
    request.setAttribute(QNetworkRequest::AuthenticationReuseAttribute, QNetworkRequest::Manual);
    auto *reply = manager.get(request);
    reply->setReadBufferSize(maxSourceBytes + 1);

    QEventLoop loop;
    QTimer timer;
    timer.setSingleShot(true);
    bool timedOut = false;
    bool tooLarge = false;
    QByteArray bytes;
    const auto drain = [&]() {
        if (tooLarge) {
            return;
        }
        bytes.append(reply->read(maxSourceBytes + 1 - bytes.size()));
        tooLarge = bytes.size() > maxSourceBytes;
        if (tooLarge && !reply->isFinished()) {
            reply->abort();
        }
    };
    QObject::connect(reply, &QNetworkReply::readyRead, &loop, drain);
    QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    QObject::connect(&timer, &QTimer::timeout, &loop, [&]() {
        timedOut = true;
        reply->abort();
    });
    if (!reply->isFinished()) {
        timer.start(networkTimeoutMs);
        loop.exec();
        timer.stop();
    }
    if (reply->bytesAvailable() > 0) {
        drain();
    }
    if (timedOut) {
        return sourceFailure("NETWORK_TIMEOUT", "Source distante indisponible dans le délai de 8 s");
    }
    if (tooLarge) {
        return sourceFailure("SOURCE_TOO_LARGE", "Source au-delà de 16 Mio");
    }
    const auto status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
    if (status >= 300 && status < 400) {
        return sourceFailure("NETWORK_REDIRECT", "Redirection non suivie, vérifier l'URL canonique");
    }
    if (status >= 400) {
        return sourceFailure("NETWORK_HTTP_ERROR", "Source distante indisponible, HTTP " + QString::number(status));
    }
    if (reply->error() != QNetworkReply::NoError || status != 200) {
        const auto error = QMetaEnum::fromType<QNetworkReply::NetworkError>().valueToKey(reply->error());
        return sourceFailure("NETWORK_UNAVAILABLE",
                             QString("Transport HTTPS indisponible ou incomplet (%1)")
                                 .arg(QString::fromLatin1(error)));
    }
    return sourceRead(std::move(bytes));
}

QJsonValue extractSourceValue(const SourceInput &input, const QJsonObject &extraction,
                              const QString &partNumber)
{
    if (!input.code.isEmpty() || partNumber.isEmpty()) {
        throw std::runtime_error("Source indisponible ou référence exacte absente");
    }
    const auto format = extraction.value("format").toString();
    if (format == "JSON_POINTER") {
        return extractJson(input.bytes, extraction, partNumber);
    }
    if (format == "TEXT_REGEX") {
        return extractText(input.bytes, extraction, partNumber);
    }
    throw std::runtime_error("Format d'extraction documentaire inconnu");
}

} // namespace technical_research
