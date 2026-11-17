#include "drone_agricole/application/GazeboExportService.hpp"
#include <exception>
#include <memory>
namespace drone_agricole::application {
GazeboExportService::GazeboExportService(IGazeboExportBackend& backend,QObject* parent)
    : QObject(parent), backend_(backend) {}
GazeboExportService::~GazeboExportService() {
  cancelled_ = true;
  if (worker_) worker_->wait();
}
QJsonObject GazeboExportService::inspect() const { return backend_.inspect(); }
bool GazeboExportService::start(const GazeboExportRequest& request) {
  if (active() || worker_) return false;
  cancelled_ = false; state_ = QStringLiteral("running"); progress_ = 0; result_ = {};
  message_ = QStringLiteral("Préparation du modèle…"); emit changed();
  struct Outcome { QJsonObject result; QString failure; };
  const auto outcome=std::make_shared<Outcome>();
  worker_ = QThread::create([this,request,outcome] {
    try {
      outcome->result = backend_.execute(request,cancelled_,[this](int value,const QString& text) {
        QMetaObject::invokeMethod(this,[this,value,text] {
          progress_ = value; message_ = text; emit output(text); emit changed();
        },Qt::QueuedConnection);
      });
    } catch (const std::exception& error) { outcome->failure = QString::fromUtf8(error.what()); }
  });
  worker_->setParent(this);
  connect(worker_,&QThread::finished,this,[this,outcome] {
      auto* done=worker_;worker_=nullptr;done->deleteLater();
      const auto& result=outcome->result;
      result_ = result;
      // The backend's finalized package is the commit point: a late cancel
      // must not relabel a successfully published artifact as cancelled.
      state_ = !result.isEmpty() ? QStringLiteral("completed") : cancelled_ ? QStringLiteral("cancelled") : QStringLiteral("failed");
      message_ = !result.isEmpty() ? QStringLiteral("Modèle Gazebo prêt · physique À valider")
          : cancelled_ ? QStringLiteral("Export annulé · aucun nouveau modèle publié") : outcome->failure;
      if (!result.isEmpty()) progress_ = 100;
      emit changed(); emit completed();
  });
  worker_->start(); return true;
}
void GazeboExportService::cancel() {
  if (active()) { cancelled_=true; message_=QStringLiteral("Annulation en cours…"); emit changed(); }
}
}
