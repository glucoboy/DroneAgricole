cmake_minimum_required(VERSION 3.21)
project(interconnection_engine LANGUAGES CXX)

find_package(Qt6 REQUIRED COMPONENTS Core)

add_library(interconnection STATIC
    src/ConnectorCatalog.cpp
    src/Interconnection.cpp
    src/Geometry.cpp
    src/Reconcile.cpp
)
target_compile_features(interconnection PUBLIC cxx_std_17)
set_target_properties(interconnection PROPERTIES CXX_EXTENSIONS OFF)
target_link_libraries(interconnection PUBLIC Qt6::Core)

add_executable(interconnection_core src/Main.cpp)
target_link_libraries(interconnection_core PRIVATE interconnection)

include(CTest)
if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME l2_interconnection COMMAND "${Python3_EXECUTABLE}" -B
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_interconnection.py"
        "$<TARGET_FILE:interconnection_core>")
    add_test(NAME l2_reconcile COMMAND "${Python3_EXECUTABLE}" -B
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_reconcile.py"
        "$<TARGET_FILE:interconnection_core>")
endif()
