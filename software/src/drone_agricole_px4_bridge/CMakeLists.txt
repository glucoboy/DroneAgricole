cmake_minimum_required(VERSION 3.16)
project(drone_agricole_px4_bridge VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(diagnostic_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(px4_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(Qt6 6.2 REQUIRED COMPONENTS Core Network)

add_library(px4_bridge_support STATIC
  src/Frames.cpp
  src/OffboardPlan.cpp
  src/RunnerContract.cpp
)
target_include_directories(px4_bridge_support PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_link_libraries(px4_bridge_support PUBLIC Qt6::Core)
target_compile_options(px4_bridge_support PRIVATE -Wall -Wextra -Wpedantic)

add_executable(state_bridge src/StateBridge.cpp)
ament_target_dependencies(state_bridge
  rclcpp diagnostic_msgs geometry_msgs nav_msgs px4_msgs std_msgs tf2_ros)
target_link_libraries(state_bridge px4_bridge_support Qt6::Core)

add_executable(offboard_test src/OffboardTest.cpp)
ament_target_dependencies(offboard_test rclcpp px4_msgs)
target_link_libraries(offboard_test px4_bridge_support Qt6::Core)

add_executable(runner_server src/RunnerServer.cpp)
target_link_libraries(runner_server px4_bridge_support Qt6::Core Qt6::Network)

install(TARGETS px4_bridge_support state_bridge offboard_test runner_server
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_frames test/TestFrames.cpp)
  target_link_libraries(test_frames px4_bridge_support)
  ament_add_gtest(test_offboard_plan test/TestOffboardPlan.cpp)
  target_link_libraries(test_offboard_plan px4_bridge_support)
  ament_add_gtest(test_runner_contract test/TestRunnerContract.cpp)
  target_link_libraries(test_runner_contract px4_bridge_support)
endif()

ament_export_include_directories(include)
ament_package()
