find_package(Qt6 6.2 REQUIRED COMPONENTS Core Gui Network)
find_package(yaml-cpp REQUIRED)
find_package(TIFF REQUIRED)
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
set(CMAKE_AUTORCC ON)
function(station_library target)
  add_library(${target} STATIC ${ARGN})
  target_include_directories(${target} PUBLIC include)
  target_compile_definitions(${target} PUBLIC QT_NO_CAST_FROM_ASCII QT_NO_CAST_TO_ASCII)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4 /permissive-)
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
  endif()
endfunction()
station_library(drone_agricole_station src/station/StationArchitecture.cpp)
target_link_libraries(drone_agricole_station Qt6::Core)
station_library(drone_agricole_support src/support/Types.cpp src/support/JsonUtils.cpp src/support/BenchmarkSupport.cpp)
target_link_libraries(drone_agricole_support Qt6::Core Qt6::Gui)
station_library(drone_agricole_algorithms src/algorithms/AdaptivePointMap.cpp src/algorithms/TrajectoryAnalysis.cpp src/algorithms/RowDetection.cpp src/algorithms/CameraColorFusion.cpp)
target_sources(drone_agricole_algorithms PRIVATE src/algorithms/ScanReconstruction.cpp)
target_link_libraries(drone_agricole_algorithms drone_agricole_support)
station_library(drone_agricole_storage src/adapters/storage/ResultAdapter.cpp src/adapters/storage/Ros1Bag.cpp src/adapters/storage/Ros1Messages.cpp src/adapters/storage/DatasetAdapterCommon.cpp)
target_link_libraries(drone_agricole_storage drone_agricole_support)
station_library(drone_agricole_mapping src/adapters/mapping/VineyardMap.cpp src/adapters/mapping/FriulBotMap.cpp)
target_sources(drone_agricole_mapping PRIVATE src/adapters/mapping/FriulBotReconstruction.cpp)
target_link_libraries(drone_agricole_mapping drone_agricole_storage drone_agricole_algorithms TIFF::TIFF ${DRONE_AGRICOLE_YAML_CPP_TARGET})
station_library(drone_agricole_runtime src/adapters/runtime/TelemetryBridge.cpp src/adapters/runtime/LioOrchestrator.cpp)
target_link_libraries(drone_agricole_runtime drone_agricole_storage drone_agricole_algorithms Qt6::Network)
station_library(drone_agricole_catalog src/application/ContractRegistry.cpp)
target_link_libraries(drone_agricole_catalog drone_agricole_support)
station_library(drone_agricole_runners src/adapters/runners/RunnerRegistry.cpp src/adapters/runners/BuiltInRunners.cpp)
target_link_libraries(drone_agricole_runners drone_agricole_catalog ${DRONE_AGRICOLE_YAML_CPP_TARGET})
station_library(drone_agricole_data_services src/application/ResultRepository.cpp src/application/ComparisonService.cpp)
target_link_libraries(drone_agricole_data_services drone_agricole_catalog drone_agricole_mapping drone_agricole_runtime)
# Le cycle de tâche ne dépend que de Qt Core et des ports du domaine.
station_library(drone_agricole_application include/drone_agricole/application/RunService.hpp include/drone_agricole/application/RunPorts.hpp src/application/RunService.cpp)
target_link_libraries(drone_agricole_application Qt6::Core)
station_library(drone_agricole_process include/drone_agricole/adapters/ProcessRunBackend.hpp src/adapters/ProcessRunBackend.cpp)
target_link_libraries(drone_agricole_process drone_agricole_application)
station_library(drone_agricole_composition src/composition/StationComposition.cpp src/composition/StationCommand.cpp)
target_link_libraries(drone_agricole_composition drone_agricole_data_services drone_agricole_runners drone_agricole_process)
# Compatibilité des outils historiques ; aucune source n'est compilée dans ce nom.
add_library(drone_agricole_core INTERFACE)
target_link_libraries(drone_agricole_core INTERFACE drone_agricole_data_services drone_agricole_runners)
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
    target_sources(drone_agricole_runtime PRIVATE
      src/adapters/runtime/BenchmarkTelemetry.cpp
      src/adapters/runtime/LiveTelemetry.cpp
      src/adapters/runtime/DatasetAdapter.cpp
      src/adapters/runtime/RosbagAnalysis.cpp
      src/adapters/runtime/RosbagTrajectoryReader.cpp
      src/adapters/runtime/RosRuntimeTools.cpp
    )
    target_compile_definitions(drone_agricole_runtime PUBLIC DRONE_AGRICOLE_WITH_ROS2=1)
    target_link_libraries(drone_agricole_runtime Eigen3::Eigen)
    if(COMMAND ament_target_dependencies)
      ament_target_dependencies(drone_agricole_runtime rclcpp rosbag2_cpp nav_msgs geometry_msgs sensor_msgs std_msgs)
    else()
      target_link_libraries(drone_agricole_runtime PUBLIC rclcpp::rclcpp rosbag2_cpp::rosbag2_cpp)
    endif()
    if(livox_ros_driver2_FOUND)
      target_compile_definitions(drone_agricole_runtime PRIVATE DRONE_AGRICOLE_WITH_LIVOX_MESSAGES=1)
      if(TARGET livox_ros_driver2::livox_ros_driver2__rosidl_typesupport_cpp)
        target_link_libraries(drone_agricole_runtime
          livox_ros_driver2::livox_ros_driver2__rosidl_typesupport_cpp)
      elseif(COMMAND ament_target_dependencies)
        ament_target_dependencies(drone_agricole_runtime livox_ros_driver2)
      endif()
    endif()
  endif()
endif()

if(NOT DRONE_AGRICOLE_ROS2_AVAILABLE)
  target_sources(drone_agricole_runtime PRIVATE
    src/adapters/runtime/BenchmarkTelemetryStub.cpp
    src/adapters/runtime/HttpLiveTelemetry.cpp
    src/adapters/runtime/DatasetAdapterStub.cpp
    src/adapters/runtime/RosbagAnalysisStub.cpp
    src/adapters/runtime/HttpTrajectoryReader.cpp
    src/adapters/runtime/RosRuntimeToolsStub.cpp
  )
endif()


# Le client sans interface reste disponible dans les builds headless.
qt_add_executable(drone-agricole-px4-client src/cli/Px4RemoteClient.cpp)
target_link_libraries(drone-agricole-px4-client PRIVATE drone_agricole_support Qt6::Network)
install(TARGETS drone-agricole-px4-client RUNTIME DESTINATION bin)
qt_add_executable(drone-agricole-tools src/cli/ProjectTools.cpp)
target_link_libraries(drone-agricole-tools PRIVATE drone_agricole_composition drone_agricole_station)
install(TARGETS drone-agricole-tools RUNTIME DESTINATION bin)
if(DRONE_AGRICOLE_BUILD_DASHBOARD)
  find_package(Qt6 6.2 REQUIRED COMPONENTS Widgets)
  station_library(drone_agricole_presentation
    include/drone_agricole/ui/MainWindow.hpp
    include/drone_agricole/ui/ExecutionPage.hpp
    include/drone_agricole/ui/ResultsPage.hpp
    include/drone_agricole/ui/ComparisonPage.hpp
    include/drone_agricole/ui/ResultViewPage.hpp
    include/drone_agricole/ui/NavigationModel.hpp
    include/drone_agricole/ui/TrajectoryView.hpp
    include/drone_agricole/ui/MetricsPlotWidget.hpp
    src/ui/MainWindow.cpp src/ui/ExecutionPage.cpp src/ui/ResultsPage.cpp
    src/ui/ComparisonPage.cpp src/ui/ResultViewPage.cpp src/ui/NavigationModel.cpp
    src/ui/TrajectoryView.cpp src/ui/MetricsPlotWidget.cpp
    ui/main_window.ui ui/execution_page.ui ui/results_page.ui ui/comparison_page.ui ui/result_view_page.ui)
  set_target_properties(drone_agricole_presentation PROPERTIES AUTOUIC_SEARCH_PATHS "${CMAKE_CURRENT_SOURCE_DIR}/ui")
  # Recompiler les pages dès la modification d'un formulaire, y compris sous Ninja/Windows.
  set_source_files_properties(src/ui/MainWindow.cpp PROPERTIES OBJECT_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/ui/main_window.ui")
  set_source_files_properties(src/ui/ExecutionPage.cpp PROPERTIES OBJECT_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/ui/execution_page.ui")
  set_source_files_properties(src/ui/ResultsPage.cpp PROPERTIES OBJECT_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/ui/results_page.ui")
  set_source_files_properties(src/ui/ComparisonPage.cpp PROPERTIES OBJECT_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/ui/comparison_page.ui")
  set_source_files_properties(src/ui/ResultViewPage.cpp PROPERTIES OBJECT_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/ui/result_view_page.ui")
  target_link_libraries(drone_agricole_presentation drone_agricole_application drone_agricole_support Qt6::Widgets)
  qt_add_executable(drone-agricole-dashboard WIN32 src/app/main.cpp resources/dashboard.qrc)
  target_link_libraries(drone-agricole-dashboard PRIVATE drone_agricole_presentation drone_agricole_composition)
  # Le dashboard lance ces exécutables : compiler la cible UI doit aussi les actualiser.
  add_dependencies(drone-agricole-dashboard drone-agricole-tools drone-agricole-px4-client)
  target_compile_definitions(drone-agricole-dashboard PRIVATE DRONE_AGRICOLE_VERSION="${PROJECT_VERSION}")
  install(TARGETS drone-agricole-dashboard RUNTIME DESTINATION bin BUNDLE DESTINATION .)
endif()
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
  drone_agricole_add_test(test_vineyard_map tests/TestVineyardMap.cpp)
  qt_add_executable(test_row_detection tests/TestRowDetection.cpp)
  target_link_libraries(test_row_detection PRIVATE drone_agricole_algorithms Qt6::Test)
  add_test(NAME test_row_detection COMMAND test_row_detection)
  qt_add_executable(test_camera_color_fusion tests/TestCameraColorFusion.cpp)
  target_link_libraries(test_camera_color_fusion PRIVATE drone_agricole_algorithms Qt6::Test)
  add_test(NAME test_camera_color_fusion COMMAND test_camera_color_fusion)
  qt_add_executable(test_scan_reconstruction tests/TestScanReconstruction.cpp)
  target_link_libraries(test_scan_reconstruction PRIVATE drone_agricole_algorithms Qt6::Test)
  add_test(NAME test_scan_reconstruction COMMAND test_scan_reconstruction)
  drone_agricole_add_test(test_station_architecture tests/TestStationArchitecture.cpp)
  target_link_libraries(test_station_architecture PRIVATE drone_agricole_station)

  qt_add_executable(test_run_service tests/TestRunService.cpp)
  target_link_libraries(test_run_service PRIVATE drone_agricole_application Qt6::Test)
  add_test(NAME test_run_service COMMAND test_run_service)
  qt_add_executable(test_process_backend tests/TestProcessBackend.cpp)
  target_link_libraries(test_process_backend PRIVATE drone_agricole_process Qt6::Test)
  add_test(NAME test_process_backend COMMAND test_process_backend)
  if(DRONE_AGRICOLE_BUILD_DASHBOARD)
    qt_add_executable(test_trajectory_view tests/TestTrajectoryView.cpp)
    target_link_libraries(test_trajectory_view PRIVATE drone_agricole_presentation Qt6::Test)
    add_test(NAME test_trajectory_view COMMAND test_trajectory_view)
    qt_add_executable(test_dashboard_mapping tests/TestDashboardMapping.cpp resources/dashboard.qrc)
    target_link_libraries(test_dashboard_mapping PRIVATE drone_agricole_presentation drone_agricole_composition Qt6::Test)
    target_compile_definitions(test_dashboard_mapping PRIVATE DRONE_AGRICOLE_TEST_WORKSPACE="${CMAKE_SOURCE_DIR}")
    add_test(NAME test_dashboard_mapping COMMAND test_dashboard_mapping)
    qt_add_executable(test_station_navigation tests/TestStationNavigation.cpp resources/dashboard.qrc)
    target_link_libraries(test_station_navigation PRIVATE drone_agricole_presentation drone_agricole_composition Qt6::Test)
    target_compile_definitions(test_station_navigation PRIVATE DRONE_AGRICOLE_TEST_WORKSPACE="${CMAKE_SOURCE_DIR}")
    add_test(NAME test_station_navigation COMMAND test_station_navigation)
    add_test(NAME test_dashboard_smoke COMMAND drone-agricole-dashboard --workspace "${CMAKE_SOURCE_DIR}" --smoke-test-ms 400)
    set_tests_properties(test_trajectory_view test_dashboard_mapping test_station_navigation test_dashboard_smoke PROPERTIES WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}" ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
  endif()
endif()

include(cmake/ArchitectureChecks.cmake)
