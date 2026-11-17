#include "drone_agricole/ui/GazeboModelPage.hpp"
#include "ui_gazebo_model_page.h"
#include <QDesktopServices>
#include <QFileDialog>
#include <QJsonArray>
#include <QUrl>
namespace drone_agricole::ui {
GazeboModelPage::GazeboModelPage(application::GazeboExportService& service,QWidget* parent)
    :QWidget(parent),service_(service),ui_(std::make_unique<Ui::GazeboModelPage>()) {
  ui_->setupUi(this);
  ui_->modelPreview->setMinimumFraming(.3F,.05F);
  ui_->modelPreview->setContentLabel(QStringLiteral("Prototype cartographe · aperçu CAO en mètres"));
  connect(ui_->exportButton,&QPushButton::clicked,this,[this] {
    application::GazeboExportRequest request;request.pythonProgram=ui_->pythonEdit->text().trimmed();
    request.regenerateMeshes=ui_->regenerateCheck->isChecked();service_.start(request);
  });
  connect(ui_->cancelExportButton,&QPushButton::clicked,&service_,&application::GazeboExportService::cancel);
  connect(ui_->pythonBrowseButton,&QPushButton::clicked,this,[this] {
    auto file=QFileDialog::getOpenFileName(this,QStringLiteral("Python fourni avec FreeCAD"),ui_->pythonEdit->text());
    if(!file.isEmpty())ui_->pythonEdit->setText(file);
  });
  connect(ui_->openPackageButton,&QPushButton::clicked,this,[this] {if(!directory_.isEmpty())QDesktopServices::openUrl(QUrl::fromLocalFile(directory_));});
  connect(ui_->fitModelButton,&QPushButton::clicked,ui_->modelPreview,&TrajectoryView::fitToData);
  connect(ui_->topModelButton,&QPushButton::clicked,ui_->modelPreview,&TrajectoryView::setTopView);
  connect(&service_,&application::GazeboExportService::changed,this,&GazeboModelPage::updateState);
  connect(&service_,&application::GazeboExportService::output,ui_->exportLog,&QPlainTextEdit::appendPlainText);
  connect(&service_,&application::GazeboExportService::completed,this,[this] {
    const auto result=service_.result();if(result.isEmpty())return;
    directory_=result.value(QStringLiteral("directory")).toString();ui_->outputLabel->setText(directory_);
    showPreview(result.value(QStringLiteral("preview")).toObject());
    ui_->previewNote->setText(QStringLiteral("Aperçu du dossier préparé · maillage simplifié pour l’affichage"));updateState();
  });
  refresh();updateState();
}
GazeboModelPage::~GazeboModelPage()=default;
void GazeboModelPage::refresh() {
  const auto info=service_.inspect();ui_->sourceLabel->setText(info.value(QStringLiteral("source")).toString());
  if(ui_->pythonEdit->text().isEmpty())ui_->pythonEdit->setText(info.value(QStringLiteral("python_program")).toString());
  ui_->sourceStateLabel->setText(info.value(QStringLiteral("source_available")).toBool()?QStringLiteral("CAO active disponible · empreintes contrôlées pendant la préparation"):QStringLiteral("CAO active indisponible"));
  if(directory_.isEmpty()&&!info.value(QStringLiteral("directory")).toString().isEmpty()) {
    directory_=info.value(QStringLiteral("directory")).toString();ui_->outputLabel->setText(directory_);
    showPreview(info.value(QStringLiteral("preview")).toObject());
  }
  if(!directory_.isEmpty() && directory_==info.value(QStringLiteral("directory")).toString()) {
    ui_->previewNote->setText(info.value(QStringLiteral("preview_stale")).toBool()
        ?QStringLiteral("Aperçu historique obsolète · les sources diffèrent de la configuration active · manifeste %1").arg(info.value(QStringLiteral("preview_source_manifest_sha256")).toString().left(12))
        :QStringLiteral("Dernier dossier préparé · sources concordantes · simplifié pour l’affichage"));
  }
}
void GazeboModelPage::updateState() {
  ui_->exportStatusLabel->setText(service_.message().isEmpty()?QStringLiteral("Prêt à préparer le modèle"):service_.message());
  ui_->exportProgress->setValue(service_.progress());ui_->exportProgress->setVisible(service_.active());
  ui_->exportButton->setEnabled(!service_.active());ui_->cancelExportButton->setEnabled(service_.active());
  ui_->regenerateCheck->setEnabled(!service_.active());ui_->pythonEdit->setEnabled(!service_.active());ui_->pythonBrowseButton->setEnabled(!service_.active());
  ui_->openPackageButton->setEnabled(!directory_.isEmpty());
}
void GazeboModelPage::showPreview(const QJsonObject& data) {
  QList<QVector3D> vertices;QList<std::array<int,3>> triangles;QList<QColor> colors;
  for(const auto& value:data.value(QStringLiteral("vertices")).toArray()){const auto p=value.toArray();if(p.size()==3)vertices.append(QVector3D(float(p[0].toDouble()),float(p[1].toDouble()),float(p[2].toDouble())));}
  for(const auto& value:data.value(QStringLiteral("triangles")).toArray()){const auto t=value.toArray();if(t.size()==3)triangles.append({t[0].toInt(),t[1].toInt(),t[2].toInt()});}
  for(const auto& c:data.value(QStringLiteral("colors")).toArray())for(int i=0;i<3;++i)colors.append(QColor(c.toString()));
  // A sampled triangle soup has gaps; display its vertices as a dense colored
  // preview rather than pretending that the simplified surface is watertight.
  ui_->modelPreview->setSurfaceVisible(false);
  ui_->modelPreview->setCameraProjectedPoints(vertices,colors);ui_->modelPreview->fitToData();
}
}
