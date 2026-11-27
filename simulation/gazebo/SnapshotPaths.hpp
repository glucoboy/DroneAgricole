#pragma once

#include <QDir>
#include <QFileInfo>
#include <filesystem>
#include <stdexcept>

namespace cartographe::gazebo {

// The workspace is canonical. Reject aliases at each existing component before
// opening any input or allocating an output below it.
inline QString snapshotPath(const QString& workspace, const QString& path) {
  const auto normalized = QDir::fromNativeSeparators(path);
  const auto absolute = QFileInfo(normalized).isAbsolute() ? normalized : QDir(workspace).filePath(normalized);
#ifdef Q_OS_WIN
  constexpr auto sensitivity = Qt::CaseInsensitive;
#else
  constexpr auto sensitivity = Qt::CaseSensitive;
#endif
  const auto refuse = [&path] {
    throw std::runtime_error(QStringLiteral("NON_CANONICAL_PATH: %1").arg(path).toStdString());
  };
  if (workspace.isEmpty() || QDir::cleanPath(absolute) != absolute ||
      !absolute.startsWith(workspace + QLatin1Char('/'), sensitivity)) {
    refuse();
  }
  QString prefix = workspace;
  for (const auto& part : absolute.mid(workspace.size() + 1).split(QLatin1Char('/'))) {
#ifdef Q_OS_WIN
    if (part.endsWith(QLatin1Char('.')) || part.endsWith(QLatin1Char(' ')) || part.contains(QLatin1Char(':'))) {
      refuse();
    }
#endif
    prefix += QLatin1Char('/') + part;
    const QFileInfo info(prefix);
    if (info.isSymLink() || info.isJunction()) {
      refuse();
    }
    if (!info.exists()) {
      continue;
    }
    if (info.canonicalFilePath().compare(prefix, sensitivity) != 0 || (!info.isFile() && !info.isDir())) {
      refuse();
    }
    if (info.isFile()) {
      std::error_code error;
      const auto count = std::filesystem::hard_link_count(std::filesystem::u8path(prefix.toUtf8().constData()), error);
      if (error || count != 1) {
        refuse();
      }
    }
  }
  return absolute;
}

} // namespace cartographe::gazebo
