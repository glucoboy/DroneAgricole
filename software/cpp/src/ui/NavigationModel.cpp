#include "drone_agricole/ui/NavigationModel.hpp"
#include <stdexcept>
namespace drone_agricole::ui {
void NavigationModel::registerPage(const QString& id, const QString& title) {
  if (id.isEmpty() || pages_.contains(id)) throw std::invalid_argument("Route vide ou déjà enregistrée");
  pages_.insert(id, title);
}
bool NavigationModel::navigate(const QString& id, const QString& object) {
  if (!pages_.contains(id)) return false;
  const auto route = current();
  if (route.page == id && route.object == object) return true;
  history_.append({id, object});
  if (history_.size() > 100) history_.removeFirst();
  emit changed();
  return true;
}
void NavigationModel::back() {
  if (!canGoBack()) return;
  history_.removeLast();
  emit changed();
}
PageRoute NavigationModel::current() const { return history_.isEmpty() ? PageRoute{} : history_.last(); }
QString NavigationModel::title() const { return pages_.value(current().page); }
}
