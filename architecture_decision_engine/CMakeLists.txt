cmake_minimum_required(VERSION 3.21)
project(architecture_decision_engine LANGUAGES CXX)

include(CTest)
find_package(Qt6 REQUIRED COMPONENTS Core Network)
add_subdirectory(../interconnection_engine interconnection)
add_subdirectory(../technical_research_engine research)

add_executable(architecture_decision_core
    src/Main.cpp
    src/Exploration.cpp
    src/Evidence.cpp
    src/InterconnectionAdapter.cpp
    src/ResearchAdapter.cpp
)
set_target_properties(architecture_decision_core PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS OFF
)
target_link_libraries(architecture_decision_core PRIVATE Qt6::Core interconnection)
target_include_directories(architecture_decision_core PRIVATE ../interconnection_engine/src)
add_dependencies(architecture_decision_core technical_research_core)

if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME l3_architecture_decision
        COMMAND "${Python3_EXECUTABLE}" -B "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_decisions.py"
        "$<TARGET_FILE:architecture_decision_core>" "$<TARGET_FILE:technical_research_core>")
    set_tests_properties(l3_architecture_decision PROPERTIES TIMEOUT 120
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/..")
endif()
