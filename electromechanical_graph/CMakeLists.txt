cmake_minimum_required(VERSION 3.21)
project(electromechanical_graph VERSION 1.0.0 LANGUAGES CXX)

include(CTest)
find_package(Qt6 REQUIRED COMPONENTS Core)
add_subdirectory(../interconnection_engine interconnection)

add_library(electromechanical_graph STATIC src/Graph.cpp)
target_compile_features(electromechanical_graph PUBLIC cxx_std_17)
set_target_properties(electromechanical_graph PROPERTIES CXX_EXTENSIONS OFF)
target_include_directories(electromechanical_graph PUBLIC src)
target_link_libraries(electromechanical_graph PUBLIC Qt6::Core)

add_executable(electromechanical_graph_core src/Main.cpp src/Import.cpp)
target_include_directories(electromechanical_graph_core PRIVATE ../interconnection_engine/src)
target_link_libraries(electromechanical_graph_core PRIVATE electromechanical_graph interconnection)

if(BUILD_TESTING)
    add_executable(test_graph tests/TestGraph.cpp)
    target_link_libraries(test_graph PRIVATE electromechanical_graph)
    add_test(NAME v3_graph_contract COMMAND test_graph)
endif()
