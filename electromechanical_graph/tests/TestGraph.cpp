#include "Graph.hpp"

#include <QJsonArray>
#include <cstdio>
#include <stdexcept>

using namespace electromechanical::graph;

namespace {

const QString digestA(64, 'a');
const QString digestB(64, 'b');
const auto proof = QJsonObject{{"state", "DOCUMENTED"}, {"source", "contract"}, {"locator", "#sample"},
                              {"scope", "test"}, {"unit", QJsonValue::Null}, {"reception", "NOT_RUN"}};

void check(bool condition, const char *message)
{
    if (!condition)
        throw std::runtime_error(message);
}

template<typename Action>
void rejects(Action action)
{
    bool rejected = false;
    try {
        action();
    } catch (const std::runtime_error &) {
        rejected = true;
    }
    check(rejected, "Un cas invalide a été admis");
}

QJsonObject node(const QString &id, const QString &kind, const QJsonArray &claims = {})
{
    return {{"id", id}, {"kind", kind}, {"version", 1}, {"claims", claims}, {"evidence", proof}};
}

QJsonObject edge(const QString &kind, const QString &from, const QString &to,
                 const QString &direction = "FORWARD", bool terminal = false)
{
    return {{"id", kind + ':' + from + "->" + to}, {"kind", kind}, {"from", from}, {"to", to},
            {"impact", direction}, {"terminal", terminal}, {"evidence", proof}};
}

QJsonObject bench()
{
    return {{"schema", "v3.graph/1"}, {"configuration", "bench"},
            {"sources", QJsonObject{{"contract", QJsonObject{{"path", "bench.json"}, {"sha256", digestA}}}}},
            {"nodes", QJsonArray{node("device", "DEVICE"), node("hold", "SUPPORT"),
                                 node("datum", "OBSERVATION"), node("test", "CONTROL"), node("cable", "HARNESS_SEGMENT"),
                                 node("adjacent", "KEEP_OUT"), node("outside", "DEVICE")}},
            {"edges", QJsonArray{edge("TRANSFORMS", "device", "datum"), edge("VERIFIES", "datum", "test"),
                                 edge("RETAINS", "hold", "cable"), edge("DEPENDS_ON", "datum", "cable"),
                                 edge("ACCESS", "cable", "adjacent", "FORWARD", true),
                                 edge("DEPENDS_ON", "adjacent", "outside")}},
            {"constraints", QJsonArray{}}, {"issues", QJsonArray{}}};
}

void topology()
{
    auto graph = bench();
    auto nodes = graph.value("nodes").toArray();
    const QJsonArray path{QJsonObject{{"route_id", "stem"}, {"sense", "direct"}},
                          QJsonObject{{"route_id", "branch"}, {"sense", "inverse"}}};
    const QJsonObject topology{{"id", "bus"}, {"path", path}, {"path_kind", "branched"},
                               {"junction_ids", QJsonArray{"joint"}}, {"cord_ids", QJsonArray{"loom"}}};
    nodes.append(node("link:bus", "ELECTRICAL_LINK", QJsonArray{
        QJsonObject{{"key", "topology"}, {"value", topology}, {"evidence", proof}}}));
    nodes.append(node("port:bus/A", "PORT"));
    nodes.append(node("port:bus/B", "PORT"));
    nodes.append(node("axis:stem", "HARNESS_SEGMENT"));
    nodes.append(node("axis:branch", "HARNESS_SEGMENT"));
    nodes.append(node("junction:joint", "JUNCTION"));
    nodes.append(node("cord:loom", "BUNDLE"));
    graph.insert("nodes", nodes);
    auto edges = graph.value("edges").toArray();
    edges.append(edge("ELECTRICAL", "port:bus/A", "link:bus", "BOTH"));
    edges.append(edge("ELECTRICAL", "port:bus/B", "link:bus", "BOTH"));
    edges.append(edge("ELECTRICAL", "link:bus", "junction:joint", "BOTH"));
    edges.append(edge("MEMBER_OF", "link:bus", "cord:loom", "BOTH"));
    for (int i = 0; i < path.size(); ++i) {
        const auto step = path.at(i).toObject();
        auto route = edge("ROUTING", "link:bus", "axis:" + step.value("route_id").toString(), "BOTH");
        route.insert("order", i);
        route.insert("sense", step.value("sense"));
        edges.append(route);
    }
    graph.insert("edges", edges);
    check(impact(graph, "FRAME", "port:bus/A").value("nodes").toArray().contains("axis:branch"),
          "Branche du bus perdue");
    edges.removeLast();
    graph.insert("edges", edges);
    rejects([&] { validate(graph); });
}

void frames()
{
    const auto point = QJsonArray{0, 0, 0};
    const auto forward = QJsonArray{1, 0, 0};
    QJsonObject reference{{"origin_role", "FIXTURE_DATUM"}, {"artifact_sha256", digestA}, {"frame", "bench"},
                          {"origin_mm", point}, {"direction", forward}};
    QJsonObject observed{{"artifact_sha256", digestB}, {"frame", "bench"}, {"origin_mm", point}, {"direction", forward}};
    QJsonObject request{{"schema", "v3.frame_comparison/1"}, {"reference", reference}, {"observed", observed},
                        {"axis", observed}, {"position_tolerance_mm", 0.1}, {"angle_tolerance_deg", 1}};
    check(compareFrames(request).value("status") == "PASS", "Repère nominal refusé");
    observed.insert("origin_mm", QJsonArray{3, 0, 0});
    request.insert("observed", observed);
    request.insert("axis", observed);
    check(compareFrames(request).value("status") == "FAIL" && compareFrames(request).value("axis_to_observed_mm") == 0,
          "Faux repère et axe déplacés ensemble acceptés");
    observed.insert("origin_mm", point);
    observed.insert("direction", QJsonArray{-1, 0, 0});
    request.insert("observed", observed);
    check(compareFrames(request).value("status") == "FAIL", "Retournement du repère signé accepté");
    reference.insert("origin_role", "ROUTE_AXIS");
    request.insert("reference", reference);
    rejects([&] { compareFrames(request); });
}

} // namespace

int main()
{
    try {
        auto graph = bench();
        const auto move = impact(graph, "MOVE", "device");
        check(move.value("checks").toArray() == QJsonArray{"test"}, "Contrôle oublié");
        check(move.value("invalidate_observations").toArray() == QJsonArray{"datum"}, "Observation oubliée");
        check(move.value("recompose_volumes").toArray() == QJsonArray{"adjacent"}, "Voisin oublié");
        check(!move.value("nodes").toArray().contains("outside"), "Le voisin terminal a propagé l'impact");
        check(impact(graph, "RETENTION", "hold").value("rebuild_cables").toArray() == QJsonArray{"cable"},
              "Câble de la retenue oublié");
        check(impact(graph, "FRAME", "datum").value("checks").toArray() == QJsonArray{"test"},
              "Modification du repère non propagée");
        auto assumption = proof;
        assumption.insert("state", "ASSUMED");
        graph.insert("constraints", QJsonArray{QJsonObject{
            {"id", "fixed"}, {"policy", "HARD_FIXED"}, {"subjects", QJsonArray{"hold"}}, {"authority", "contract"},
            {"state", "NOMINAL"}, {"criticality", "physical"}, {"threshold", QJsonValue::Null},
            {"unit", QJsonValue::Null}, {"tolerance", QJsonValue::Null}, {"evidence", assumption}}});
        rejects([&] { validate(graph); });
        graph = bench();
        graph.insert("schema", "v9.graph/1");
        rejects([&] { validate(graph); });
        topology();
        frames();
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
