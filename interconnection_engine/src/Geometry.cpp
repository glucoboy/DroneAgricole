#include "Interconnection.hpp"

#include <QSet>
#include <algorithm>
#include <array>
#include <cmath>
#include <optional>
#include <stdexcept>

namespace interconnection {
namespace {

using Vec = std::array<double, 3>;
using Matrix = std::array<double, 16>;
using Box = std::array<double, 6>;
constexpr Matrix identity{1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1};
constexpr double pi = 3.14159265358979323846;

template <std::size_t N>
std::optional<std::array<double, N>> numbers(const QJsonValue &value)
{
    const auto array = value.toArray();
    if (array.size() != static_cast<qsizetype>(N)) {
        return std::nullopt;
    }
    std::array<double, N> result{};
    for (std::size_t i = 0; i < N; ++i) {
        if (!array[i].isDouble() || !std::isfinite(array[i].toDouble())) {
            return std::nullopt;
        }
        result[i] = array[i].toDouble();
    }
    return result;
}

template <std::size_t N>
QJsonArray json(const std::array<double, N> &data)
{
    QJsonArray result;
    for (const auto value : data) {
        result.append(value);
    }
    return result;
}

std::optional<Matrix> l0Matrix(const QJsonValue &value)
{
    const auto rows = value.toArray();
    if (rows.size() != 4) {
        return std::nullopt;
    }
    Matrix result{};
    for (qsizetype row = 0; row < rows.size(); ++row) {
        const auto values = numbers<4>(rows[row]);
        if (!values) {
            return std::nullopt;
        }
        std::copy(values->begin(), values->end(), result.begin() + row * 4);
    }
    return result;
}

Vec sub(const Vec &a, const Vec &b) { return {a[0] - b[0], a[1] - b[1], a[2] - b[2]}; }
Vec scale(const Vec &v, double factor) { return {v[0] * factor, v[1] * factor, v[2] * factor}; }
double dot(const Vec &a, const Vec &b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
double norm(const Vec &v) { return std::hypot(v[0], v[1], v[2]); }
Vec origin(const Matrix &m) { return {m[3], m[7], m[11]}; }
Vec axis(const Matrix &m, std::size_t col) { return {m[col], m[4 + col], m[8 + col]}; }

double angle(const Vec &a, const Vec &b)
{
    const Vec cross{a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]};
    return std::atan2(norm(cross), dot(a, b)) * 180 / pi;
}

Matrix multiply(const Matrix &a, const Matrix &b)
{
    Matrix result{};
    for (std::size_t row = 0; row < 4; ++row) {
        for (std::size_t col = 0; col < 4; ++col) {
            for (std::size_t k = 0; k < 4; ++k) {
                result[4 * row + col] += a[4 * row + k] * b[4 * k + col];
            }
        }
    }
    return result;
}

Matrix inverseRigid(const Matrix &m)
{
    auto result = identity;
    for (std::size_t row = 0; row < 3; ++row) {
        const auto column = axis(m, row);
        std::copy(column.begin(), column.end(), result.begin() + 4 * row);
        result[4 * row + 3] = -dot(column, origin(m));
    }
    return result;
}

Vec transform(const Matrix &m, const Vec &v)
{
    return {m[0] * v[0] + m[1] * v[1] + m[2] * v[2] + m[3],
            m[4] * v[0] + m[5] * v[1] + m[6] * v[2] + m[7],
            m[8] * v[0] + m[9] * v[1] + m[10] * v[2] + m[11]};
}

bool rigid(const Matrix &m)
{
    if (m[12] != 0 || m[13] != 0 || m[14] != 0 || m[15] != 1) {
        return false;
    }
    const Vec x = axis(m, 0), y = axis(m, 1), z = axis(m, 2);
    const Vec cross{x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0]};
    return std::abs(norm(x) - 1) < 1e-8 && std::abs(norm(y) - 1) < 1e-8 &&
        std::abs(norm(z) - 1) < 1e-8 && std::abs(dot(x, y)) < 1e-8 && norm(sub(cross, z)) < 1e-8;
}

bool near(const Matrix &a, const Matrix &b, double position, double rotation)
{
    return norm(sub(origin(a), origin(b))) <= position && angle(axis(a, 0), axis(b, 0)) <= rotation &&
        angle(axis(a, 1), axis(b, 1)) <= rotation && angle(axis(a, 2), axis(b, 2)) <= rotation;
}

class Frames {
public:
    Frames(const QJsonValue &entries, const QJsonArray &overrides) : frames_(index(entries, "frames"))
    {
        for (const auto &item : overrides) {
            const auto entry = item.toObject();
            const auto id = entry.value("frame_id").toString();
            if (!frames_.contains(id) || overrides_.contains(id) || frames_.value(id).value("parent_frame_id").isNull()) {
                throw std::runtime_error("Remplacement de pose hors repère enfant ou dupliqué");
            }
            overrides_.insert(id, entry.value("parent_from_local"));
        }
        int roots = 0;
        for (auto it = frames_.cbegin(); it != frames_.cend(); ++it) {
            roots += it.value().value("parent_frame_id").isNull();
            resolve(it.key(), {});
        }
        if (roots != 1) {
            throw std::runtime_error("Un seul repère racine L0 est requis");
        }
    }

    std::optional<Matrix> get(const QString &id) const { return global_.value(id); }

    bool under(QString child, const QString &ancestor) const
    {
        if (ancestor.isEmpty()) {
            return false;
        }
        while (frames_.contains(child)) {
            child = frames_.value(child).value("parent_frame_id").toString();
            if (child == ancestor) {
                return true;
            }
        }
        return false;
    }

private:
    std::optional<Matrix> resolve(const QString &id, QSet<QString> stack)
    {
        if (global_.contains(id)) {
            return global_.value(id);
        }
        if (stack.contains(id) || !frames_.contains(id)) {
            throw std::runtime_error("Graphe de repères cyclique ou référence hors modèle");
        }
        stack.insert(id);
        const auto frame = frames_.value(id);
        const auto parent = frame.value("parent_frame_id");
        const auto value = overrides_.value(id, frame.value("parent_from_local"));
        std::optional<Matrix> result;
        if (parent.isNull()) {
            if (!value.isNull() && l0Matrix(value) != std::optional<Matrix>{identity}) {
                throw std::runtime_error("Le repère racine n’a pas de transformation locale");
            }
            result = identity;
        } else {
            const auto parentPose = resolve(parent.toString(), stack);
            if (!value.isNull()) {
                const auto local = l0Matrix(value);
                if (!local || !rigid(*local)) {
                    throw std::runtime_error("Transformation L0 non rigide, indirecte ou invalide");
                }
                if (parentPose) {
                    result = multiply(*parentPose, *local);
                    if (!std::all_of(result->begin(), result->end(), [](double x) { return std::isfinite(x); })) {
                        throw std::runtime_error("Transformation composée non finie");
                    }
                }
            }
        }
        global_.insert(id, result);
        return result;
    }

    Index frames_;
    QMap<QString, QJsonValue> overrides_;
    QMap<QString, std::optional<Matrix>> global_;
};

std::optional<Box> box(const QJsonValue &value)
{
    const auto parsed = numbers<6>(value);
    if (!parsed || (*parsed)[0] >= (*parsed)[3] || (*parsed)[1] >= (*parsed)[4] || (*parsed)[2] >= (*parsed)[5]) {
        return std::nullopt;
    }
    return parsed;
}

Box transformedBox(const Matrix &frame, const Box &local)
{
    auto point = transform(frame, {local[0], local[1], local[2]});
    Box result{point[0], point[1], point[2], point[0], point[1], point[2]};
    for (int corner = 1; corner < 8; ++corner) {
        point = transform(frame, {local[(corner & 1) ? 3 : 0], local[(corner & 2) ? 4 : 1], local[(corner & 4) ? 5 : 2]});
        for (std::size_t i = 0; i < 3; ++i) {
            result[i] = std::min(result[i], point[i]);
            result[i + 3] = std::max(result[i + 3], point[i]);
        }
    }
    return result;
}

double clearance(const Box &a, const Box &b)
{
    Vec gaps{};
    for (std::size_t i = 0; i < 3; ++i) {
        gaps[i] = std::max({0.0, a[i] - b[i + 3], b[i] - a[i + 3]});
    }
    return norm(gaps);
}

bool contains(const Box &outer, const Box &inner, double tolerance)
{
    for (std::size_t i = 0; i < 3; ++i) {
        if (outer[i] > inner[i] + tolerance || outer[i + 3] < inner[i + 3] - tolerance) {
            return false;
        }
    }
    return true;
}

bool containsPoint(const Box &bounds, const Vec &point, double tolerance)
{
    return contains(bounds, {point[0], point[1], point[2], point[0], point[1], point[2]}, tolerance);
}

bool axisAligned(const Matrix &m)
{
    for (std::size_t i = 0; i < 3; ++i) {
        const auto col = axis(m, i);
        if (std::none_of(col.begin(), col.end(), [](double c) { return std::abs(c) >= 1.0 - 1e-12; })) {
            return false;
        }
    }
    return true;
}

struct GeometryChecks {
    const QJsonObject &dossier;
    const QJsonObject &state;
    Findings &findings;
    const InterfaceAuthority &authority;
    Frames frames;
    Index obstacles;
    Index evidence;
    QJsonObject references;
    double positionTolerance, angleTolerance, serviceClearance;

    GeometryChecks(const QJsonObject &input, const QJsonObject &selected, Findings &results,
                   const InterfaceAuthority &referenceAuthority)
        : dossier(input), state(selected), findings(results), authority(referenceAuthority),
          frames(input.value("model").toObject().value("frames"), selected.value("frame_overrides").toArray()),
          obstacles(index(input.value("geometry").toObject().value("obstacles"), "geometry.obstacles")),
          evidence(index(input.value("model").toObject().value("records").toObject().value("technical_evidence"),
                         "technical_evidence")),
          references(authorizedInterfaces()),
          positionTolerance(tolerance("position_tolerance_mm")), angleTolerance(tolerance("angle_tolerance_deg")),
          serviceClearance(tolerance("service_clearance_mm")) {}

    QJsonObject authorizedInterfaces() const
    {
        const bool synthetic = dossier.value("mode") == "SYNTHETIC_BENCH";
        if (synthetic != (authority.document.value("origin") == "SYNTHETIC_BENCH")) {
            return {};
        }
        const auto configuration = dossier.value("model").toObject().value("configuration_id").toString();
        return authority.document.value("configurations").toObject().value(configuration).toObject()
            .value(state.value("id").toString()).toObject();
    }

    double tolerance(const QString &key) const
    {
        return dossier.value("geometry").toObject().value(key).toDouble(-1);
    }

    void finding(const QString &code, const QString &subject, const QString &status, const QString &reason)
    {
        findings.append({"geometry", code, subject, status, reason});
    }

    std::optional<Box> checkEnvelope(const QString &id, const Matrix &frame, const QJsonValue &value,
                                     const QString &kind, bool eligible = true)
    {
        const auto local = box(value);
        const auto geometry = dossier.value("geometry").toObject();
        if (!local) {
            finding(kind, id, "INCONCLUSIVE", "Enveloppe de service sans dimensions établies");
            return std::nullopt;
        }
        const auto global = transformedBox(frame, *local);
        const bool conclusive = eligible && dossier.value("mode") == "SYNTHETIC_BENCH" &&
            geometry.value("obstacles_complete") == true && serviceClearance > 0 && axisAligned(frame);
        bool complete = conclusive;
        for (const auto &obstacle : obstacles) {
            const auto obstacleBox = box(obstacle.value("box_mm"));
            if (!obstacleBox) {
                complete = false;
            } else if (clearance(global, *obstacleBox) < serviceClearance) {
                finding(kind, id, conclusive ? "FAIL" : "INCONCLUSIVE",
                        (conclusive ? QString("Enveloppe obstruée par ") : QString("Conflit possible des boîtes avec ")) +
                            obstacle.value("id").toString());
                return global;
            }
        }
        finding(kind, id, complete ? "PASS" : "INCONCLUSIVE", complete ? "Dégagement vérifié sur les boîtes du banc" :
                "Provenance, couverture d’obstacles, orientation ou domaine de mesure insuffisant");
        return global;
    }

    bool checkGeometrySource(const QString &id, const QString &kind, const QJsonObject &envelope)
    {
        const bool synthetic = dossier.value("mode") == "SYNTHETIC_BENCH";
        const auto origin = envelope.value("geometry_class").toString();
        const auto dimensions = envelope.value("dimensions").toObject();
        const QSet<QString> classes{"SUPPLIER", "MEASURED", "CONSERVATIVE_ENVELOPE", "APPROXIMATION", "UNKNOWN"};
        if (!classes.contains(origin) || !box(dimensions.value("value")) || dimensions.value("unit") != "mm") {
            finding("GEOMETRY_SOURCE", id, "INCONCLUSIVE", kind + " : classe ou dimensions absentes ou invalides");
            return false;
        }
        const bool established = synthetic && origin == "CONSERVATIVE_ENVELOPE" && sourced(dimensions, evidence, true);
        finding("GEOMETRY_SOURCE", id, established ? "PASS" : "INCONCLUSIVE",
                kind + " : " + origin + (established ? " avec preuve" : " sans preuve applicable à la réception"));
        return established;
    }

    void checkSweep(const QString &id, const QJsonValue &extraction, std::optional<Box> plugBody,
                    double travel, bool established)
    {
        const auto extractionLocal = box(extraction);
        if (!extractionLocal || !plugBody || travel <= 0) {
            finding("EXTRACTION_SWEEP", id, "INCONCLUSIVE", "Corps ou course de retrait non établi");
            return;
        }
        (*plugBody)[5] += travel;
        const bool included = contains(*extractionLocal, *plugBody, positionTolerance);
        finding("EXTRACTION_SWEEP", id, established ? (included ? "PASS" : "FAIL") : "INCONCLUSIVE",
                included ? "Enveloppe de retrait contenant le balayage axial déclaré" :
                           "Enveloppe de retrait incomplète pour le balayage axial déclaré");
    }

    QJsonObject checkPhysicalGeometry(const QJsonObject &entry, const Matrix &mating)
    {
        const auto id = entry.value("id").toString();
        const auto geometry = entry.value("physical_geometry").toObject();
        const auto receptacleId = geometry.value("receptacle_frame_id").toString();
        const auto plugId = geometry.value("plug_frame_id").toString();
        const auto receptacle = frames.get(receptacleId);
        const auto plug = frames.get(plugId);
        const auto matingId = entry.value("receptacle_mating_frame_id").toString();
        if (!receptacle || !plug) {
            finding("BODY_FRAMES", id, "INCONCLUSIVE", "Repère du corps d’embase ou de fiche inconnu");
            return {};
        }
        const bool attached = frames.under(receptacleId, entry.value("mount_frame_id").toString()) &&
            frames.under(matingId, receptacleId) && frames.under(plugId, entry.value("mate_mating_frame_id").toString()) &&
            frames.under(entry.value("exit_frame_id").toString(), plugId);
        finding("BODY_FRAMES", id, attached ? "PASS" : "FAIL", attached ? "Corps attachés aux repères de l’interface" :
                "Repères sans relation entre montage, embase, accouplement, fiche et sortie");

        const auto body = geometry.value("plug_body").toObject();
        const auto receptacleBody = geometry.value("receptacle_body").toObject();
        const auto sweep = geometry.value("extraction_sweep").toObject();
        const auto tool = geometry.value("tool_access_envelope").toObject();
        const auto dimensions = [](const QJsonObject &e) {
            return e.value("dimensions").toObject().value("value");
        };
        const bool plugEvidence = checkGeometrySource(id, "Fiche accouplée", body);
        const bool receptacleEvidence = checkGeometrySource(id, "Embase", receptacleBody);
        const bool sweepEvidence = checkGeometrySource(id, "Retrait", sweep);
        const bool toolEvidence = checkGeometrySource(id, "Accès verrou", tool);
        const auto plugBox = checkEnvelope(id, *plug, dimensions(body), "MATED_PLUG", attached && plugEvidence);
        const auto receptacleBox = checkEnvelope(id, *receptacle, dimensions(receptacleBody), "MATED_RECEPTACLE",
                                                 attached && receptacleEvidence);
        const auto extractionBox = checkEnvelope(id, mating, dimensions(sweep), "EXTRACTION_ENVELOPE", attached && sweepEvidence);
        const auto toolBox = checkEnvelope(id, mating, dimensions(tool), "TOOL_ENVELOPE", attached && toolEvidence);
        const auto travel = sweep.value("travel").toObject();
        const bool travelSourced = travel.value("unit") == "mm" &&
            sourced(travel, evidence, dossier.value("mode") == "SYNTHETIC_BENCH");
        const auto localBody = box(dimensions(body));
        const auto localReceptacle = box(dimensions(receptacleBody));
        const auto relativeBody = localBody ? std::optional<Box>{transformedBox(multiply(inverseRigid(mating), *plug), *localBody)}
                                            : std::nullopt;
        checkSweep(id, dimensions(sweep), relativeBody, travel.value("value").toDouble(-1),
                   attached && plugEvidence && sweepEvidence && travelSourced);

        const auto exit = frames.get(entry.value("exit_frame_id").toString());
        if (attached && plugEvidence && receptacleEvidence && localBody && localReceptacle && exit) {
            const auto plugFromWorld = inverseRigid(*plug);
            const bool spansFrames = containsPoint(*localBody, transform(plugFromWorld, origin(mating)), positionTolerance) &&
                containsPoint(*localReceptacle, transform(inverseRigid(*receptacle), origin(mating)), positionTolerance) &&
                containsPoint(*localBody, transform(plugFromWorld, origin(*exit)), positionTolerance);
            finding("BODY_ANCHORS", id, spansFrames ? "PASS" : "FAIL", spansFrames ?
                    "Enveloppes atteignant l’accouplement et la sortie" : "Enveloppe détachée de l’accouplement ou de la sortie");
        } else {
            finding("BODY_ANCHORS", id, "INCONCLUSIVE", "Enveloppes ou repères d’ancrage sans preuve applicable");
        }

        const auto accessPoint = tool.value("lock_access_point").toObject();
        const auto lockPoint = numbers<3>(accessPoint.value("value"));
        const auto toolLocal = box(dimensions(tool));
        if (!attached || !plugEvidence || !toolEvidence || !lockPoint || !toolLocal || !localBody ||
            accessPoint.value("unit") != "mm" ||
            !sourced(accessPoint, evidence, dossier.value("mode") == "SYNTHETIC_BENCH")) {
            finding("LOCK_ACCESS_POINT", id, "INCONCLUSIVE", "Point d’actionnement ou enveloppe du verrou non établi");
        } else {
            const auto inPlug = transform(multiply(inverseRigid(*plug), mating), *lockPoint);
            const bool reaches = containsPoint(*localBody, inPlug, positionTolerance) &&
                containsPoint(*toolLocal, *lockPoint, positionTolerance);
            finding("LOCK_ACCESS_POINT", id, reaches ? "PASS" : "FAIL", reaches ?
                    "Enveloppe d’outil atteignant le point d’actionnement sur la fiche" :
                    "Enveloppe d’outil ou point d’actionnement détaché de la fiche");
        }
        const auto projected = [](const std::optional<Box> &envelope) {
            return envelope ? QJsonValue(json(*envelope)) : QJsonValue::Null;
        };
        return {{"receptacle_frame", json(*receptacle)}, {"plug_frame", json(*plug)},
                {"receptacle_box_mm", projected(receptacleBox)}, {"plug_box_mm", projected(plugBox)},
                {"extraction_box_mm", projected(extractionBox)}, {"tool_box_mm", projected(toolBox)},
                {"source_geometry", geometry}};
    }

    QJsonObject compareReference(const QJsonObject &entry, const Matrix &equipment, const Matrix &mount,
                                 const Matrix &receptacle, const Matrix &mate, const Matrix &exit,
                                 const std::optional<Box> &sweep, double travel)
    {
        const auto id = entry.value("id").toString();
        const auto reference = references.value(id).toObject();
        if (reference.isEmpty()) {
            const auto domain = dossier.value("mode") == "SYNTHETIC_BENCH" && references.isEmpty()
                ? "reference" : "geometry";
            findings.append({domain, "INTERFACE_REFERENCE", id, "INCONCLUSIVE",
                             "Aucune interface indépendante pour cet équipement et cet état"});
            return {};
        }
        const auto position = authority.document.value("position_tolerance_mm").toDouble(-1);
        const auto rotation = authority.document.value("angle_tolerance_deg").toDouble(-1);
        if (!std::isfinite(position) || position < 0 || !std::isfinite(rotation) || rotation < 0 || rotation >= 90) {
            throw std::runtime_error("Tolérance du référentiel d'interface invalide");
        }
        const auto identityFields = entry.value("identity").toObject();
        bool identityMatches = true;
        const auto compareIdentity = [&reference, &identityMatches](const QString &key, const QJsonObject &observed) {
            const auto value = reference.value(key);
            if (value.toString().trimmed().isEmpty()) {
                throw std::runtime_error("Identité obligatoire absente du référentiel d'interface");
            }
            identityMatches &= observed.value(key) == value;
        };
        for (const auto &key : {"equipment_id", "port_id", "receptacle_id", "mate_id"}) {
            compareIdentity(key, entry);
        }
        for (const auto &key : {"equipment_mpn", "equipment_revision", "receptacle_mpn", "receptacle_revision",
                                "mate_mpn", "mate_revision", "keying", "polarity"}) {
            compareIdentity(key, identityFields);
        }
        finding("INTERFACE_REFERENCE_IDENTITY", id, identityMatches ? "PASS" : "FAIL",
                identityMatches ? "Identité, révisions, clé et polarité de l'interface de référence"
                                : "Conflit équipement, port, référence, révision, détrompage ou polarité");

        const auto expectedContacts = reference.value("contacts").toArray();
        const auto actualContacts = entry.value("contacts").toArray();
        Index contactsByPin;
        for (const auto &contact : actualContacts) {
            const auto record = contact.toObject();
            contactsByPin.insert(record.value("pin_id").toString(), record);
        }
        bool contactsMatch = !expectedContacts.isEmpty() && expectedContacts.size() == actualContacts.size() &&
            contactsByPin.size() == actualContacts.size();
        for (const auto &value : expectedContacts) {
            const auto expected = value.toObject();
            const auto pinId = expected.value("pin_id").toString();
            const auto contact = contactsByPin.take(pinId);
            contactsMatch &= !pinId.isEmpty() && !contact.isEmpty();
            for (const auto &key : {"pin_number", "cavity", "mate_cavity", "receptacle_contact_id", "mate_contact_id"}) {
                contactsMatch &= !expected.value(key).toString().isEmpty() && contact.value(key) == expected.value(key);
            }
        }
        findings.append({"electrical", "INTERFACE_REFERENCE_CONTACTS", id, contactsMatch ? "PASS" : "FAIL",
                         contactsMatch ? "Broches, cavités et indexation de l'interface de référence"
                                       : "Contacts de l'interface différents du brochage de référence"});

        struct Datum { QString key; Matrix observed; };
        const std::array<Datum, 5> chain{{
            {"world_from_equipment", equipment}, {"equipment_from_mount", mount},
            {"mount_from_receptacle_contact", receptacle}, {"receptacle_contact_from_mate_contact", mate},
            {"mate_contact_from_exit", exit}
        }};
        Matrix expectedWorld = identity;
        Matrix expectedContactPose = identity;
        Matrix observedParent = identity;
        QJsonObject comparisons;
        bool posesMatch = true;
        for (const auto &datum : chain) {
            const auto local = numbers<16>(reference.value(datum.key));
            if (!local || !rigid(*local)) {
                throw std::runtime_error("Matrice non rigide ou absente du référentiel d'interface");
            }
            expectedWorld = multiply(expectedWorld, *local);
            if (datum.key == "mount_from_receptacle_contact") {
                expectedContactPose = expectedWorld;
            }
            const auto measuredLocal = multiply(inverseRigid(observedParent), datum.observed);
            const bool matches = near(expectedWorld, datum.observed, position, rotation) &&
                near(*local, measuredLocal, position, rotation);
            posesMatch &= matches;
            comparisons.insert(datum.key, QJsonObject{
                {"expected_local", json(*local)}, {"observed_local", json(measuredLocal)},
                {"expected_world", json(expectedWorld)}, {"observed_world", json(datum.observed)},
                {"status", matches ? "PASS" : "FAIL"}});
            observedParent = datum.observed;
        }
        finding("INTERFACE_REFERENCE_POSE", id, posesMatch ? "PASS" : "FAIL",
                posesMatch ? "Repères locaux et mondiaux conformes au référentiel indépendant"
                           : "Translation ou rotation d'un repère différente du référentiel indépendant");

        const auto minimumSweep = box(reference.value("extraction_box_local_mm"));
        const auto requiredTravel = reference.value("extraction_travel_mm").toDouble(-1);
        if (!minimumSweep || requiredTravel <= 0) {
            throw std::runtime_error("Volume ou course de retrait absent du référentiel d'interface");
        }
        const bool withdrawalMatches = sweep && contains(*sweep, transformedBox(expectedContactPose, *minimumSweep), position)
            && std::abs(travel - requiredTravel) <= position;
        finding("INTERFACE_REFERENCE_WITHDRAWAL", id, !sweep || travel <= 0 ? "INCONCLUSIVE" : withdrawalMatches ? "PASS" : "FAIL",
                withdrawalMatches ? "Volume minimal et course de retrait couverts"
                                  : "Volume minimal ou course de retrait de référence non démontrés");
        return {{"reference_id", authority.document.value("reference_id")}, {"sha256", authority.sha256},
                {"origin", authority.document.value("origin")}, {"source", authority.document.value("source")},
                {"position_tolerance_mm", position}, {"angle_tolerance_deg", rotation}, {"poses", comparisons},
                {"expected_exit_world", json(expectedWorld)}};
    }

    QJsonObject buildMatingFrames(const QJsonObject &entry, const QJsonObject &port, const QJsonObject &receptacle)
    {
        const auto id = entry.value("id").toString();
        const auto equipmentFrame = entry.value("equipment_frame_id").toString();
        const auto mountId = entry.value("mount_frame_id").toString();
        const auto receptacleId = entry.value("receptacle_mating_frame_id").toString();
        const auto mateId = entry.value("mate_mating_frame_id").toString();
        const auto exitId = entry.value("exit_frame_id").toString();
        const auto mount = frames.get(mountId), receptaclePose = frames.get(receptacleId);
        const auto mate = frames.get(mateId), exit = frames.get(exitId), equipment = frames.get(equipmentFrame);
        if (positionTolerance < 0 || angleTolerance < 0 || angleTolerance >= 90 ||
            !equipment || !mount || !receptaclePose || !mate || !exit) {
            finding("MATING_FRAMES", id, "INCONCLUSIVE", "Repère équipement, montage, accouplement ou sortie inconnu");
            return {};
        }
        const auto referenceFrame = receptacle.value("frame_id").toString();
        const auto reference = frames.get(referenceFrame);
        auto orientation = l0Matrix(receptacle.value("orientation"));
        const auto receptacleOrigin = numbers<3>(receptacle.value("origin_mm"));
        const auto portOrigin = numbers<3>(port.value("origin_mm"));
        const auto portAxis = numbers<3>(port.value("exit_axis"));
        if (!reference || !orientation || !rigid(*orientation) || norm(origin(*orientation)) != 0 || !receptacleOrigin ||
            port.value("frame_id").toString().isEmpty() || !portOrigin || !portAxis || norm(*portAxis) == 0) {
            finding("MATING_FRAMES", id, "INCONCLUSIVE", "Repère fonctionnel du port ou pose L0 de l’embase inconnus");
            return {};
        }
        (*orientation)[3] = (*receptacleOrigin)[0];
        (*orientation)[7] = (*receptacleOrigin)[1];
        (*orientation)[11] = (*receptacleOrigin)[2];
        const auto graphPose = multiply(*reference, *orientation);
        if (port.value("frame_id") != mountId || !frames.under(mountId, equipmentFrame) ||
            !frames.under(receptacleId, mountId) || !frames.under(exitId, mateId) ||
            (referenceFrame != mountId && !frames.under(referenceFrame, mountId)) ||
            norm(*portOrigin) > positionTolerance || angle(*portAxis, Vec{0, 0, 1}) > angleTolerance ||
            !near(graphPose, *receptaclePose, positionTolerance, angleTolerance)) {
            finding("FRAME_BINDING", id, "FAIL", "Repères et identités du graphe désynchronisés");
        } else {
            finding("FRAME_BINDING", id, "PASS", "Chaîne de poses attachée aux objets attendus");
        }
        const bool aligned = near(*mate, *receptaclePose, positionTolerance, angleTolerance);
        finding("MATING_ORIENTATION", id, aligned ? "PASS" : "FAIL",
                aligned ? "Trièdres et origines d’accouplement concordants" : "Décalage ou rotation de la fiche incompatible");

        QJsonObject physical;
        std::optional<Box> extraction, tooling;
        const auto travel = entry.value("extraction_travel_mm").toDouble(-1);
        if (entry.contains("physical_geometry")) {
            physical = checkPhysicalGeometry(entry, *receptaclePose);
            extraction = box(physical.value("extraction_box_mm"));
            tooling = box(physical.value("tool_box_mm"));
        } else {
            const bool synthetic = dossier.value("mode") == "SYNTHETIC_BENCH";
            if (!synthetic) {
                finding("PHYSICAL_GEOMETRY", id, "INCONCLUSIVE", "Géométries d’interface typées et prouvées requises");
            }
            extraction = checkEnvelope(id, *receptaclePose, entry.value("extraction_box_local_mm"), "EXTRACTION_ENVELOPE");
            tooling = checkEnvelope(id, *receptaclePose, entry.value("tool_box_local_mm"), "TOOL_ENVELOPE");
            checkSweep(id, entry.value("extraction_box_local_mm"), box(entry.value("plug_body_box_local_mm")), travel, synthetic);
        }
        const auto measuredTravel = entry.contains("physical_geometry")
            ? entry.value("physical_geometry").toObject().value("extraction_sweep").toObject()
                  .value("travel").toObject().value("value") : entry.value("extraction_travel_mm");
        const auto independent = compareReference(entry, *equipment, *mount, *receptaclePose, *mate, *exit,
                                                  extraction, measuredTravel.toDouble(-1));
        return {{"interface_id", entry.value("id")}, {"end_id", entry.value("end_id")}, {"equipment_id", entry.value("equipment_id")},
            {"port_id", entry.value("port_id")}, {"receptacle_id", entry.value("receptacle_id")},
            {"mate_id", entry.value("mate_id")}, {"mount", json(*mount)}, {"receptacle_mating", json(*receptaclePose)},
            {"mate_mating", json(*mate)}, {"exit", json(*exit)}, {"contacts", entry.value("contacts")},
            {"interface_reference", independent.isEmpty() ? QJsonValue::Null : QJsonValue(independent)},
            {"physical_geometry", physical.isEmpty() ? QJsonValue::Null : QJsonValue(physical)},
            {"extraction_box_mm", extraction ? QJsonValue(json(*extraction)) : QJsonValue::Null},
            {"extraction_travel_mm", measuredTravel},
            {"tool_box_mm", tooling ? QJsonValue(json(*tooling)) : QJsonValue::Null}};
    }

    void checkWireExit(const QString &subject, const QJsonObject &interface, const Matrix &frame,
                       const Vec &point, const Vec &direction)
    {
        bool matches = norm(direction) > 0 && norm(sub(origin(frame), point)) <= positionTolerance &&
            angle(axis(frame, 2), direction) <= angleTolerance;
        const auto reference = interface.value("interface_reference").toObject();
        const auto expected = numbers<16>(reference.value("expected_exit_world"));
        if (expected) {
            matches = matches && norm(sub(origin(*expected), point)) <= reference.value("position_tolerance_mm").toDouble()
                && angle(axis(*expected, 2), direction) <= reference.value("angle_tolerance_deg").toDouble();
        }
        const bool tentative = !expected && dossier.value("mode") != "SYNTHETIC_BENCH";
        finding("WIRE_EXIT", subject, !matches ? "FAIL" : tentative ? "INCONCLUSIVE" : "PASS",
                !matches ? "Extrémité ou tangente incompatible avec la sortie du connecteur"
                         : expected ? "Extrémité et tangente sur la sortie indépendante"
                                    : "Extrémité et tangente cohérentes avec la sortie déclarée du modèle");
    }
};

} // namespace

QJsonObject checkGeometry(const QJsonObject &dossier, const QJsonObject &state,
                         const QJsonArray &interfaces, Findings &findings, const InterfaceAuthority &authority)
{
    GeometryChecks checks(dossier, state, findings, authority);
    const auto model = dossier.value("model").toObject();
    const auto records = model.value("records").toObject();
    const auto cables = index(records.value("cables"), "cables");
    const auto ports = index(records.value("ports"), "ports");
    const auto receptacles = index(records.value("connector_receptacles"), "connector_receptacles");
    const auto terminals = index(records.value("terminals"), "terminals");
    const auto routes = index(records.value("routes"), "routes");
    QJsonArray nativeInterfaces, nativeCables, obstacles;
    QMap<QPair<QString, QString>, QJsonObject> ends;
    for (const auto &value : interfaces) {
        const auto entry = value.toObject();
        const auto projection = checks.buildMatingFrames(entry, ports.value(entry.value("port_id").toString()),
                                                         receptacles.value(entry.value("receptacle_id").toString()));
        if (!projection.isEmpty()) {
            ends.insert({entry.value("cable_id").toString(), entry.value("end_id").toString()}, projection);
            nativeInterfaces.append(projection);
        }
    }
    for (const auto &obstacle : checks.obstacles) {
        obstacles.append(obstacle);
    }
    if (nativeInterfaces.isEmpty()) {
        checks.finding("GEOMETRY_COVERAGE", model.value("configuration_id").toString(), "INCONCLUSIVE", "Aucune interface géométrique complète");
    }
    for (const auto &cable : cables) {
        const auto id = cable.value("id").toString();
        const auto endIds = cable.value("end_ids").toArray();
        QList<QJsonObject> located;
        for (const auto &route : routes) {
            if (route.value("state_id") == state.value("id") && route.value("representation") == "CABLE_AXIS" &&
                route.value("cable_ids").toArray() == QJsonArray{id}) {
                located.append(route);
            }
        }
        if (endIds.size() != 2 || located.size() != 1) {
            checks.finding("WIRE_EXIT", id, "INCONCLUSIVE", "Pas d’axe univoque pour les deux sorties dans cet état");
            continue;
        }
        const auto route = located.first();
        const auto frame = checks.frames.get(route.value("frame_id").toString());
        QList<Vec> points;
        QJsonArray projected;
        for (const auto &point : route.value("points_mm").toArray()) {
            const auto p = numbers<3>(point);
            if (!p || !frame) {
                points.clear();
                break;
            }
            points.append(transform(*frame, *p));
            projected.append(json(points.last()));
        }
        const auto first = ends.value({id, endIds[0].toString()});
        const auto last = ends.value({id, endIds[1].toString()});
        const auto a = numbers<16>(first.value("exit"));
        const auto b = numbers<16>(last.value("exit"));
        if (points.size() < 2 || !a || !b || route.value("geometry_kind") != "POLYLINE") {
            checks.finding("WIRE_EXIT", id, "INCONCLUSIVE", "Sorties ou points de route inaccessibles pour ce contrôle");
            continue;
        }
        checks.checkWireExit(id + "/" + endIds[0].toString(), first, *a, points.first(), sub(points[1], points.first()));
        checks.checkWireExit(id + "/" + endIds[1].toString(), last, *b, points.last(), sub(points[points.size() - 2], points.last()));
        const auto length = dossier.value("cable_parts").toObject().value(id).toObject()
            .value("specifications").toObject().value("length_mm").toObject();
        const auto declaredLength = length.value("value").toDouble(-1);
        double routeLength = 0;
        for (qsizetype i = 1; i < points.size(); ++i) {
            routeLength += norm(sub(points[i], points[i - 1]));
        }
        if (declaredLength >= 0 && length.value("unit") == "mm" &&
            declaredLength + checks.positionTolerance < routeLength) {
            checks.finding("CORD_LENGTH", id, "FAIL", "Longueur du cordon inférieure à celle de l’axe déclaré");
        }
        QJsonArray conductors;
        for (const auto &entry : cable.value("conductors").toArray()) {
            const auto conductor = entry.toObject();
            QJsonArray contacts;
            for (const auto &terminalId : conductor.value("terminal_ids").toArray()) {
                const auto terminal = terminals.value(terminalId.toString());
                contacts.append(terminal.value("contact_id"));
            }
            conductors.append(QJsonObject{{"id", conductor.value("id")}, {"mate_contact_ids", contacts}});
        }
        nativeCables.append(QJsonObject{{"id", id}, {"points_mm", projected}, {"conductors", conductors},
            {"diameter_mm", cable.value("outer_diameter_mm").toObject().value("value")}});
    }
    return {{"configuration_id", model.value("configuration_id")}, {"state_id", state.value("id")},
        {"interfaces", nativeInterfaces}, {"cables", nativeCables}, {"obstacles", obstacles}};
}

} // namespace interconnection
