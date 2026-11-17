#include "drone_agricole/adapters/JsonWorkspaceStore.hpp"

#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QLockFile>
#include <QSaveFile>
#include <stdexcept>

namespace drone_agricole::adapters {
namespace {
[[noreturn]] void fail(const QString& text) { throw std::runtime_error(text.toStdString()); }

QByteArray readBytes(const QString& path, bool optional = false) {
  if (optional && !QFileInfo::exists(path)) return {};
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly)) fail(QStringLiteral("Lecture impossible : %1").arg(path));
  if (file.size() > 8 * 1024 * 1024) fail(QStringLiteral("Document station trop volumineux : %1").arg(path));
  const auto bytes = file.readAll();
  if (file.error() != QFileDevice::NoError) fail(QStringLiteral("Lecture incomplète : %1").arg(path));
  return bytes;
}

QJsonObject parseDocument(const QByteArray& bytes, const QString& path) {
  QJsonParseError error;
  const auto document = QJsonDocument::fromJson(bytes, &error);
  if (error.error != QJsonParseError::NoError || !document.isObject())
    fail(QStringLiteral("Document JSON invalide, fichier conservé : %1 (%2)").arg(path, error.errorString()));
  return document.object();
}

void writeDocument(const QString& path, const QJsonObject& document) {
  const auto bytes = QJsonDocument(document).toJson(QJsonDocument::Indented);
  if (bytes.size() > 8 * 1024 * 1024) fail(QStringLiteral("Document station trop volumineux"));
  QSaveFile file(path);
  file.setDirectWriteFallback(false);
  if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size() || !file.commit())
    fail(QStringLiteral("Enregistrement atomique impossible : %1").arg(path));
}

void requireInsideWorkspace(const QString& workspace, const QString& path) {
  const auto root = QFileInfo(workspace).canonicalFilePath();
  const auto absolute = QDir::cleanPath(QFileInfo(path).absoluteFilePath());
  const auto relative = QDir(workspace).relativeFilePath(absolute);
  if (root.isEmpty() || relative == QStringLiteral("..") || relative.startsWith(QStringLiteral("../")) || QDir::isAbsolutePath(relative))
    fail(QStringLiteral("Le document doit rester dans l'espace projet : %1").arg(path));
  // Contrôler aussi les parents existants pour refuser les redirections par lien.
  auto current = QFileInfo(absolute);
  while (!current.exists() && !current.isSymLink()) {
    const auto parent = current.dir().absolutePath();
    if (parent == current.absoluteFilePath()) break;
    current.setFile(parent);
  }
  const auto canonical = current.canonicalFilePath();
  const auto canonicalRelative = QDir(root).relativeFilePath(canonical);
  if (canonical.isEmpty() || canonicalRelative == QStringLiteral("..") || canonicalRelative.startsWith(QStringLiteral("../")) ||
      QDir::isAbsolutePath(canonicalRelative))
    fail(QStringLiteral("Le chemin sort de l'espace projet : %1").arg(path));
}
}

JsonWorkspaceStore::JsonWorkspaceStore(const QString& workspace)
    : workspace_(QDir(workspace).absolutePath()), path_(QDir(workspace_).filePath(QStringLiteral("results/station/workspace.json"))) {}

void JsonWorkspaceStore::validateStateLocation() const { requireInsideWorkspace(workspace_, path_); }

bool JsonWorkspaceStore::exists() const { return QFileInfo::exists(path_); }

QJsonObject JsonWorkspaceStore::load() const {
  validateStateLocation();
  const bool present = exists();
  const auto bytes = readBytes(path_, true);
  const auto document = present ? parseDocument(bytes, path_) : QJsonObject{};
  lastReadDigest_ = QCryptographicHash::hash(bytes, QCryptographicHash::Sha256);
  hasLoaded_ = true;
  return document;
}

void JsonWorkspaceStore::save(const QJsonObject& document) {
  validateStateLocation();
  if (!hasLoaded_) fail(QStringLiteral("L'espace station doit être lu avant enregistrement"));
  if (!QDir().mkpath(QFileInfo(path_).absolutePath())) fail(QStringLiteral("Création du dossier station impossible"));
  validateStateLocation();
  QLockFile lock(path_ + QStringLiteral(".lock"));
  if (!lock.tryLock(0)) fail(QStringLiteral("L'espace station est modifié par une autre instance ; réessayez"));
  const auto current = readBytes(path_, true);
  if (QCryptographicHash::hash(current, QCryptographicHash::Sha256) != lastReadDigest_)
    fail(QStringLiteral("L'espace station a changé ; rechargez avant enregistrement"));
  writeDocument(path_, document);
  lastReadDigest_ = QCryptographicHash::hash(QJsonDocument(document).toJson(QJsonDocument::Indented), QCryptographicHash::Sha256);
}

QJsonObject JsonWorkspaceStore::readMissionDocument(const QString& path) const { return parseDocument(readBytes(path), path); }

void JsonWorkspaceStore::writeMissionDocument(const QString& path, const QJsonObject& document) const {
  const auto absolute = QFileInfo(path).absoluteFilePath();
  requireInsideWorkspace(workspace_, absolute);
  if (QFileInfo(absolute).suffix().compare(QStringLiteral("json"), Qt::CaseInsensitive) != 0)
    fail(QStringLiteral("L'export de brouillon exige un fichier .json"));
  if (QFileInfo::exists(absolute)) fail(QStringLiteral("L'export refuse d'écraser un fichier existant : %1").arg(absolute));
  if (!QFileInfo(QFileInfo(absolute).absolutePath()).isDir())
    fail(QStringLiteral("Le dossier d'export doit exister"));
  writeDocument(absolute, document);
}

}  // namespace drone_agricole::adapters
