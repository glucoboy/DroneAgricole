#include "drone_agricole/core/LiveTelemetry.hpp"

#include "drone_agricole/core/TelemetryBridge.hpp"

#include <QDateTime>
#include <QJsonDocument>
#include <QMutex>
#include <QMutexLocker>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QTimer>
#include <QUrl>

namespace drone_agricole::core {

namespace {

constexpr qint64 maximumSnapshotBytes = 8LL * 1024LL * 1024LL;
constexpr qint64 telemetryFreshnessMilliseconds = 1500;

QString telemetryRootUrl() {
  auto value = qEnvironmentVariable("DRONE_AGRICOLE_TELEMETRY_URL",
                                    QStringLiteral("http://127.0.0.1:8092"));
  while (value.endsWith(QLatin1Char('/'))) {
    value.chop(1);
  }
  return value;
}

}  // namespace

class LiveTelemetry::Impl final {
 public:
  Impl() : rootUrl_(telemetryRootUrl()) {
    timer_.setInterval(250);
    QObject::connect(&timer_, &QTimer::timeout, &manager_, [this] { requestSnapshot(); });
    timer_.start();
    requestSnapshot();
  }

  void reset() {
    ++generation_;
    {
      QMutexLocker locker(&mutex_);
      snapshot_ = {};
      lastUpdateMilliseconds_ = 0;
    }
    QNetworkRequest request(QUrl(rootUrl_ + QStringLiteral("/api/reset")));
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    auto* reply = manager_.post(request, QByteArrayLiteral("{}"));
    QObject::connect(reply, &QNetworkReply::finished, reply, &QObject::deleteLater);
  }

  [[nodiscard]] LiveTelemetrySnapshot snapshot() const {
    QMutexLocker locker(&mutex_);
    auto value = snapshot_;
    const auto fresh = lastUpdateMilliseconds_ > 0 &&
                       QDateTime::currentMSecsSinceEpoch() - lastUpdateMilliseconds_ <=
                           telemetryFreshnessMilliseconds;
    value.available = value.available && fresh;
    return value;
  }

 private:
  void requestSnapshot() {
    if (activeReply_ != nullptr) {
      return;
    }
    QNetworkRequest request(QUrl(rootUrl_ + QStringLiteral("/api/snapshot")));
    request.setRawHeader(QByteArrayLiteral("Accept"), QByteArrayLiteral("application/json"));
    request.setAttribute(QNetworkRequest::CacheLoadControlAttribute, QNetworkRequest::AlwaysNetwork);
    const auto requestGeneration = generation_;
    activeReply_ = manager_.get(request);
    QObject::connect(activeReply_, &QNetworkReply::finished, &manager_, [this, requestGeneration] {
      auto* reply = activeReply_;
      activeReply_ = nullptr;
      if (reply == nullptr) {
        return;
      }
      const auto body = reply->readAll();
      if (reply->error() == QNetworkReply::NoError && body.size() <= maximumSnapshotBytes &&
          requestGeneration == generation_) {
        QJsonParseError error;
        const auto document = QJsonDocument::fromJson(body, &error);
        if (error.error == QJsonParseError::NoError && document.isObject()) {
          const auto parsed = telemetrySnapshotFromJson(document.object());
          if (parsed.available) {
            QMutexLocker locker(&mutex_);
            snapshot_ = parsed;
            lastUpdateMilliseconds_ = QDateTime::currentMSecsSinceEpoch();
          }
        }
      }
      reply->deleteLater();
    });
  }

  QString rootUrl_;
  QNetworkAccessManager manager_;
  QTimer timer_;
  QNetworkReply* activeReply_{nullptr};
  int generation_{0};
  mutable QMutex mutex_;
  LiveTelemetrySnapshot snapshot_;
  qint64 lastUpdateMilliseconds_{0};
};

LiveTelemetry::LiveTelemetry() : impl_(std::make_unique<Impl>()) {}
LiveTelemetry::~LiveTelemetry() = default;
void LiveTelemetry::reset() { impl_->reset(); }
LiveTelemetrySnapshot LiveTelemetry::snapshot() const { return impl_->snapshot(); }

}  // namespace drone_agricole::core
