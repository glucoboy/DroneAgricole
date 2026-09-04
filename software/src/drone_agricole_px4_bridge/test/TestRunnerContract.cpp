#include "drone_agricole_px4_bridge/RunnerContract.hpp"

#include <QJsonObject>
#include <QTemporaryDir>

#include <gtest/gtest.h>

using namespace drone_agricole::px4;

QJsonObject validPayload() {
  return {{QStringLiteral("run_id"), QStringLiteral("square-001")},
          {QStringLiteral("mode"), QStringLiteral("square")},
          {QStringLiteral("result_directory"), QStringLiteral("results/simulation/px4_lot_a/square-001")},
          {QStringLiteral("parameters"), QJsonObject{{QStringLiteral("takeoff_altitude_m"), 2.0},
                                                      {QStringLiteral("leg_m"), 2.0},
                                                      {QStringLiteral("warmup_s"), 2.0},
                                                      {QStringLiteral("hover_s"), 3.0},
                                                      {QStringLiteral("stage_timeout_s"), 12.0}}}};
}

TEST(Px4RunnerContract, AcceptsBoundedRequest) {
  QTemporaryDir workspace;
  const auto result = validateStartPayload(validPayload(), workspace.path());
  EXPECT_EQ(result.value(QStringLiteral("mode")).toString(), QStringLiteral("square"));
}

TEST(Px4RunnerContract, PreservesDoubleTypeForRosArguments) {
  EXPECT_EQ(rosDoubleParameterValue(1.0), QStringLiteral("1.0"));
  EXPECT_EQ(rosDoubleParameterValue(2.0), QStringLiteral("2.0"));
  EXPECT_EQ(rosDoubleParameterValue(0.5), QStringLiteral("0.5"));
}

TEST(Px4RunnerContract, RejectsTraversalAndUnknownFields) {
  QTemporaryDir workspace;
  auto payload = validPayload();
  payload.insert(QStringLiteral("result_directory"), QStringLiteral("../escape"));
  EXPECT_THROW(validateStartPayload(payload, workspace.path()), RunnerContractError);
  payload = validPayload();
  payload.insert(QStringLiteral("execute"), true);
  EXPECT_THROW(validateStartPayload(payload, workspace.path()), RunnerContractError);
}
