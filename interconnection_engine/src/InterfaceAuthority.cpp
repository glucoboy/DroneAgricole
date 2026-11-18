#include "Interconnection.hpp"
#include "BenchInterfaceReference.hpp"

#include <QCryptographicHash>
#include <QFile>
#include <QJsonDocument>
#include <stdexcept>

namespace interconnection {
namespace {

InterfaceAuthority parse(const QByteArray &bytes, const QString &expectedSha256)
{
    const auto sha256 = QString::fromLatin1(
        QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
    if (sha256 != expectedSha256) {
        throw std::runtime_error("Empreinte du référentiel d'interface divergente");
    }
    const auto document = QJsonDocument::fromJson(bytes).object();
    const auto origin = document.value("origin").toString();
    const auto supplierDocuments = document.value("supplier_documents");
    if (document.value("schema") != "drone_agricole.interface_authority.v1" ||
        document.value("reference_id").toString().trimmed().isEmpty() ||
        document.value("source").toString().trimmed().isEmpty() ||
        !document.value("configurations").isObject() || !supplierDocuments.isArray() ||
        (origin != "SUPPLIER_DOCUMENT_VERIFIED" && !supplierDocuments.toArray().isEmpty()) ||
        (origin != "SYNTHETIC_BENCH" && origin != "SUPPLIER_DOCUMENT_VERIFIED" && origin != "DOCUMENTED_MEASUREMENT")) {
        throw std::runtime_error("Référentiel d'interface invalide");
    }
    return {document, sha256};
}

} // namespace

const InterfaceAuthority &defaultInterfaceAuthority()
{
    static const auto authority = parse(QByteArray(benchReference), QString::fromLatin1(benchReferenceSha256));
    return authority;
}

InterfaceAuthority loadInterfaceAuthority(const QString &path, const QString &expectedSha256)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        throw std::runtime_error(("Impossible de lire le référentiel d'interface : " + file.errorString()).toStdString());
    }
    const auto bytes = file.readAll();
    if (file.error() != QFileDevice::NoError) {
        throw std::runtime_error(("Erreur de lecture du référentiel d'interface : " + file.errorString()).toStdString());
    }
    return parse(bytes, expectedSha256);
}

} // namespace interconnection
