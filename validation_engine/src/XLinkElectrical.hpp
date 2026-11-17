#pragma once

#include <QJsonObject>

namespace electromechanical_validation {

// Le graphe et les sélecteurs proviennent du référentiel, les occurrences du rejeu natif.
QJsonObject joinXLinkElectrical(const QJsonObject &graph, const QJsonObject &mapping,
                              const QJsonObject &inventory, const QJsonObject &sourceHashes);

} // namespace electromechanical_validation
