cmake_minimum_required(VERSION 3.22)

project(DroneAgricole VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(DRONE_AGRICOLE_BUILD_DASHBOARD "Construire l'application desktop Qt 6" ON)
option(DRONE_AGRICOLE_BUILD_TESTS "Construire les tests C++" ON)
option(DRONE_AGRICOLE_WITH_ROS2 "Activer la lecture ROS 2 et les bridges lorsqu'ils sont disponibles" ON)

if(DRONE_AGRICOLE_BUILD_TESTS)
  include(CTest)
  enable_testing()
endif()

add_subdirectory(software/cpp)
