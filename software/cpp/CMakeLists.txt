find_package(Qt6 6.2 REQUIRED COMPONENTS Core Gui Network)
find_package(yaml-cpp REQUIRED)

if(TARGET yaml-cpp::yaml-cpp)
  set(DRONE_AGRICOLE_YAML_CPP_TARGET yaml-cpp::yaml-cpp)
else()
  set(DRONE_AGRICOLE_YAML_CPP_TARGET yaml-cpp)
endif()

if(COMMAND qt_standard_project_setup)
  qt_standard_project_setup()
else()
  set(CMAKE_AUTOMOC ON)
  set(CMAKE_AUTOUIC ON)
  set(CMAKE_AUTORCC ON)
endif()

add_library(drone_agricole_station STATIC
  include/drone_agricole/station/IStationModule.hpp
  include/drone_agricole/station/StationArchitecture.hpp
  src/station/StationArchitecture.cpp
)
target_include_directories(drone_agricole_station PUBLIC include)
target_link_libraries(drone_agricole_station PUBLIC Qt6::Core)
target_compile_definitions(drone_agricole_station PUBLIC QT_NO_CAST_FROM_ASCII QT_NO_CAST_TO_ASCII)
if(MSVC)
  target_compile_options(drone_agricole_station PRIVATE /W4 /permissive-)
else()
  target_compile_options(drone_agricole_station PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_library(drone_agricole_core STATIC
  include/drone_agricole/core/AdaptivePointMap.hpp
  include/drone_agricole/core/ComparisonService.hpp
  include/drone_agricole/core/BenchmarkSupport.hpp
  include/drone_agricole/core/BenchmarkTelemetry.hpp
  include/drone_agricole/core/ContractRegistry.hpp
  include/drone_agricole/core/DatasetAdapter.hpp
  include/drone_agricole/core/JsonUtils.hpp
  include/drone_agricole/core/LioOrchestrator.hpp
  include/drone_agricole/core/LiveTelemetry.hpp
  include/drone_agricole/core/TelemetryBridge.hpp
  include/drone_agricole/core/ResultAdapter.hpp
  include/drone_agricole/core/ResultRepository.hpp
  include/drone_agricole/core/RosbagAnalysis.hpp
  include/drone_agricole/core/RosbagTrajectoryReader.hpp
  include/drone_agricole/core/RosRuntimeTools.hpp
  include/drone_agricole/core/Ros1Bag.hpp
  include/drone_agricole/core/RunnerRegistry.hpp
  include/drone_agricole/core/TrajectoryAnalysis.hpp
  include/drone_agricole/core/Types.hpp
  src/core/ComparisonService.cpp
  src/core/AdaptivePointMap.cpp
  src/core/BenchmarkSupport.cpp
  src/core/ContractRegistry.cpp
  src/core/DatasetAdapterCommon.cpp
  src/core/JsonUtils.cpp
  src/core/LioOrchestrator.cpp
  src/core/ResultAdapter.cpp
  src/core/ResultRepository.cpp
  src/core/Ros1Bag.cpp
  src/core/RunnerRegistry.cpp
  src/core/TrajectoryAnalysis.cpp
  src/core/TelemetryBridge.cpp
  src/core/Types.cpp
)

target_include_directories(drone_agricole_core PUBLIC include)
target_link_libraries(drone_agricole_core
  Qt6::Core
  Qt6::Gui
  Qt6::Network
  ${DRONE_AGRICOLE_YAML_CPP_TARGET}
)
target_compile_definitions(drone_agricole_core PUBLIC QT_NO_CAST_FROM_ASCII QT_NO_CAST_TO_ASCII)

if(MSVC)
  target_compile_options(drone_agricole_core PRIVATE /W4 /permissive-)
else()
  target_compile_options(drone_agricole_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

set(DRONE_AGRICOLE_ROS2_AVAILABLE OFF)
if(DRONE_AGRICOLE_WITH_ROS2)
  find_package(ament_cmake QUIET)
  find_package(rclcpp QUIET)
  find_package(rosbag2_cpp QUIET)
  find_package(nav_msgs QUIET)
  find_package(geometry_msgs QUIET)
  find_package(sensor_msgs QUIET)
  find_package(std_msgs QUIET)
  find_package(livox_ros_driver2 QUIET)
  find_package(Eigen3 QUIET)
  if(rclcpp_FOUND AND rosbag2_cpp_FOUND AND nav_msgs_FOUND AND geometry_msgs_FOUND AND sensor_msgs_FOUND AND
     std_msgs_FOUND AND Eigen3_FOUND)
    set(DRONE_AGRICOLE_ROS2_AVAILABLE ON)
    target_sources(drone_agricole_core PRIVATE
      src/core/BenchmarkTelemetry.cpp
      src/core/LiveTelemetry.cpp
      src/core/DatasetAdapter.cpp
      src/core/RosbagAnalysis.cpp
      src/core/RosbagTrajectoryReader.cpp
      src/core/RosRuntimeTools.cpp
    )
    target_compile_definitions(drone_agricole_core PUBLIC DRONE_AGRICOLE_WITH_ROS2=1)
    target_link_libraries(drone_agricole_core Eigen3::Eigen)
    if(COMMAND ament_target_dependencies)
      ament_target_dependencies(drone_agricole_core rclcpp rosbag2_cpp nav_msgs geometry_msgs sensor_msgs std_msgs)
    else()
      target_link_libraries(drone_agricole_core PUBLIC rclcpp::rclcpp rosbag2_cpp::rosbag2_cpp)
    endif()
    if(livox_ros_driver2_FOUND)
      target_compile_definitions(drone_agricole_core PRIVATE DRONE_AGRICOLE_WITH_LIVOX_MESSAGES=1)
      if(TARGET livox_ros_driver2::livox_ros_driver2__rosidl_typesupport_cpp)
        target_link_libraries(drone_agricole_core
          livox_ros_driver2::livox_ros_driver2__rosidl_typesupport_cpp)
      elseif(COMMAND ament_target_dependencies)
        ament_target_dependencies(drone_agricole_core livox_ros_driver2)
      endif()
    endif()
  endif()
endif()

if(NOT DRONE_AGRICOLE_ROS2_AVAILABLE)
  target_sources(drone_agricole_core PRIVATE
    src/core/BenchmarkTelemetryStub.cpp
    src/core/LiveTelemetryStub.cpp
    src/core/DatasetAdapterStub.cpp
    src/core/RosbagAnalysisStub.cpp
    src/core/RosbagTrajectoryReaderStub.cpp
    src/core/RosRuntimeToolsStub.cpp
  )
endif()

if(DRONE_AGRICOLE_BUILD_DASHBOARD)
  find_package(Qt6 6.2 REQUIRED COMPONENTS Widgets OpenGLWidgets)

  qt_add_executable(drone-agricole-dashboard WIN32
    include/drone_agricole/ui/MainWindow.hpp
    include/drone_agricole/ui/MetricsPlotWidget.hpp
    include/drone_agricole/ui/TrajectoryView.hpp
    src/app/main.cpp
    src/ui/MainWindow.cpp
    src/ui/MetricsPlotWidget.cpp
    src/ui/TrajectoryView.cpp
    ui/main_window.ui
    resources/dashboard.qrc
  )

  set_target_properties(drone-agricole-dashboard PROPERTIES
    AUTOUIC_SEARCH_PATHS "${CMAKE_CURRENT_SOURCE_DIR}/ui"
    OUTPUT_NAME "drone-agricole-dashboard"
  )

  target_include_directories(drone-agricole-dashboard PRIVATE include)
  target_link_libraries(drone-agricole-dashboard PRIVATE
    drone_agricole_station
    drone_agricole_core
    Qt6::Widgets
    Qt6::OpenGLWidgets
  )
  target_compile_definitions(drone-agricole-dashboard PRIVATE
    DRONE_AGRICOLE_VERSION="${PROJECT_VERSION}"
  )

  install(TARGETS drone-agricole-dashboard RUNTIME DESTINATION bin BUNDLE DESTINATION .)

  qt_add_executable(drone-agricole-px4-client
    src/cli/Px4RemoteClient.cpp
  )
  target_link_libraries(drone-agricole-px4-client PRIVATE drone_agricole_core Qt6::Core Qt6::Network)
  install(TARGETS drone-agricole-px4-client RUNTIME DESTINATION bin)
endif()

qt_add_executable(drone-agricole-tools
  src/cli/ProjectTools.cpp
)
target_link_libraries(drone-agricole-tools PRIVATE drone_agricole_station drone_agricole_core Qt6::Core)
install(TARGETS drone-agricole-tools RUNTIME DESTINATION bin)

if(DRONE_AGRICOLE_BUILD_TESTS AND BUILD_TESTING)
  find_package(Qt6 6.2 REQUIRED COMPONENTS Test)

  function(drone_agricole_add_test target source)
    qt_add_executable(${target} ${source})
    target_include_directories(${target} PRIVATE include)
    target_link_libraries(${target} PRIVATE drone_agricole_core Qt6::Test)
    target_compile_definitions(${target} PRIVATE DRONE_AGRICOLE_TEST_WORKSPACE="${CMAKE_SOURCE_DIR}")
    add_test(NAME ${target} COMMAND ${target})
    set_tests_properties(${target} PROPERTIES WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}" ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
  endfunction()

  drone_agricole_add_test(test_contract_registry tests/TestContractRegistry.cpp)
  drone_agricole_add_test(test_result_repository tests/TestResultRepository.cpp)
  drone_agricole_add_test(test_comparison_service tests/TestComparisonService.cpp)
  drone_agricole_add_test(test_runner_registry tests/TestRunnerRegistry.cpp)
  drone_agricole_add_test(test_benchmark_support tests/TestBenchmarkSupport.cpp)
  drone_agricole_add_test(test_trajectory_analysis tests/TestTrajectoryAnalysis.cpp)
  drone_agricole_add_test(test_ros1_bag tests/TestRos1Bag.cpp)
  drone_agricole_add_test(test_telemetry_bridge tests/TestTelemetryBridge.cpp)
  drone_agricole_add_test(test_adaptive_point_map tests/TestAdaptivePointMap.cpp)
  drone_agricole_add_test(test_station_architecture tests/TestStationArchitecture.cpp)
  target_link_libraries(test_station_architecture PRIVATE drone_agricole_station)
  if(DRONE_AGRICOLE_BUILD_DASHBOARD)
    qt_add_executable(test_trajectory_view
      include/drone_agricole/ui/TrajectoryView.hpp
      src/ui/TrajectoryView.cpp
      tests/TestTrajectoryView.cpp
    )
    target_include_directories(test_trajectory_view PRIVATE include)
    target_link_libraries(test_trajectory_view PRIVATE Qt6::Core Qt6::Gui Qt6::Test Qt6::Widgets Qt6::OpenGLWidgets)
    target_compile_definitions(test_trajectory_view PRIVATE QT_NO_CAST_FROM_ASCII QT_NO_CAST_TO_ASCII)
    add_test(NAME test_trajectory_view COMMAND test_trajectory_view)
    set_tests_properties(test_trajectory_view PROPERTIES
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
      ENVIRONMENT "QT_QPA_PLATFORM=offscreen;QT_OPENGL=software")

    add_test(NAME test_dashboard_smoke
      COMMAND drone-agricole-dashboard --workspace "${CMAKE_SOURCE_DIR}" --smoke-test-ms 400)
    set_tests_properties(test_dashboard_smoke PROPERTIES
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
      ENVIRONMENT "QT_QPA_PLATFORM=offscreen;QT_OPENGL=software")
  endif()
endif()
