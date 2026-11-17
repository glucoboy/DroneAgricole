#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

using Vector = std::array<double, 3>;
Vector operator-(Vector a, Vector b) { return {a[0]-b[0], a[1]-b[1], a[2]-b[2]}; }
Vector operator+(Vector a, Vector b) { return {a[0]+b[0], a[1]+b[1], a[2]+b[2]}; }
Vector operator*(Vector a, double t) { return {a[0]*t, a[1]*t, a[2]*t}; }
double dot(Vector a, Vector b) { return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }
double norm(Vector a) { return std::sqrt(dot(a,a)); }

struct Edge {
    std::string id;
    double diameter;
    Vector start, end;
};

int main(int argc, char* argv[]) {
    if (argc != 2) return 2;
    std::ifstream input(argv[1]);
    if (!input) return 2;
    Edge edge{};
    std::vector<Edge> edges;
    while (input >> edge.id >> edge.diameter >> edge.start[0] >> edge.start[1] >> edge.start[2]
                >> edge.end[0] >> edge.end[1] >> edge.end[2]) {
        edges.push_back(edge);
    }
    if (!input.eof() || edges.empty()) return 2;
    std::cout << std::fixed << std::setprecision(6);
    for (std::size_t i = 0; i < edges.size(); ++i) {
        const Edge& a = edges[i];
        const Vector ab = a.end-a.start;
        const double len = norm(ab);
        const Vector axis = ab * (1./len);
        for (std::size_t j = i+1; j < edges.size(); ++j) {
            const Edge& b = edges[j];
            if (a.id == b.id) continue;
            const Vector bb = b.end-b.start;
            if (std::abs(dot(axis,bb)) < (1.-1e-10)*norm(bb)) continue;
            const double b0 = dot(axis,b.start-a.start);
            const double b1 = dot(axis,b.end-a.start);
            const double begin = std::max(0., std::min(b0,b1));
            const double end = std::min(len, std::max(b0,b1));
            const double overlap = end-begin;
            if (overlap < 4.) continue;
            const Vector offset = b.start-a.start-axis*b0;
            const double spacing = norm(offset);
            if (spacing > 15. || spacing < (a.diameter+b.diameter)/2.-1e-7) continue;
            const Vector start = a.start+axis*begin;
            const Vector finish = a.start+axis*end;
            std::cout << a.id << '\t' << b.id << '\t' << a.diameter << '\t' << b.diameter
                      << '\t' << overlap << '\t' << spacing;
            for (const auto& v : {start, finish, start+offset, finish+offset})
                for (double value : v) std::cout << '\t' << value;
            std::cout << '\n';
        }
    }
}
