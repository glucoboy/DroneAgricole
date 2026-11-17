cmake_minimum_required(VERSION 3.21)
project(technical_research_engine LANGUAGES CXX)

find_package(Qt6 REQUIRED COMPONENTS Core Network)

add_executable(technical_research_core
    src/Main.cpp
    src/Research.cpp
    src/Sources.cpp
)
set_target_properties(technical_research_core PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS OFF
)
target_link_libraries(technical_research_core PRIVATE Qt6::Core Qt6::Network)

include(CTest)
if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME technical_research_engine
        COMMAND ${CMAKE_COMMAND} -E env
            "TECHNICAL_RESEARCH_CORE=$<TARGET_FILE:technical_research_core>"
            "${Python3_EXECUTABLE}" -B -m unittest discover -s technical_research_engine/tests -v
    )
    set_tests_properties(technical_research_engine PROPERTIES
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/.."
        TIMEOUT 120
    )
endif()
