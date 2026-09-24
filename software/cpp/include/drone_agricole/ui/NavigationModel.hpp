#pragma once
#include <QObject>
#include <QHash>
#include <QStringList>
#include <QVector>
namespace drone_agricole::ui {
struct PageRoute { QString page; QString object; };
class NavigationModel final : public QObject {
  Q_OBJECT
 public:
  using QObject::QObject;
  void registerPage(const QString& id, const QString& title);
  bool navigate(const QString& id, const QString& object = {});
  void back();
  PageRoute current() const;
  QString title() const;
  bool canGoBack() const { return history_.size() > 1; }
 signals:
  void changed();
 private:
  QHash<QString, QString> pages_;
  QVector<PageRoute> history_;
};
}
