#pragma once

class QCommandLineParser;
class QDir;

namespace electromechanical_validation {
int validateXLink(const QDir &workspace, const QCommandLineParser &options);
}
