cmake_minimum_required(VERSION 3.21)
project(validation_engine VERSION 2.0.0 LANGUAGES CXX)

include(CTest)
find_package(Qt6 REQUIRED COMPONENTS Core)
add_subdirectory(../interconnection_engine interconnection)

add_library(electromechanical_validation STATIC
    src/Connectivity.cpp
    src/Mechanical.cpp
    src/Report.cpp
    src/XLinkElectrical.cpp
)
target_compile_features(electromechanical_validation PUBLIC cxx_std_17)
set_target_properties(electromechanical_validation PROPERTIES CXX_EXTENSIONS OFF)
target_include_directories(electromechanical_validation PUBLIC src PRIVATE ../interconnection_engine/src)
target_link_libraries(electromechanical_validation PUBLIC Qt6::Core PRIVATE interconnection)

add_executable(validation_core src/Main.cpp src/Reference.cpp src/XLink.cpp ../architecture_decision_engine/src/Evidence.cpp)
target_compile_features(validation_core PRIVATE cxx_std_17)
set_target_properties(validation_core PROPERTIES CXX_EXTENSIONS OFF)
target_compile_definitions(validation_core PRIVATE VALIDATOR_VERSION="${PROJECT_VERSION}")
target_include_directories(validation_core PRIVATE ../architecture_decision_engine/src)
target_link_libraries(validation_core PRIVATE electromechanical_validation)

if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_executable(test_mechanical tests/TestMechanical.cpp)
    target_link_libraries(test_mechanical PRIVATE electromechanical_validation)
    add_test(NAME l4_mechanical_rules COMMAND test_mechanical)
    add_executable(test_xlink_electrical tests/TestXLinkElectrical.cpp)
    target_link_libraries(test_xlink_electrical PRIVATE electromechanical_validation)
    add_test(NAME v21_xlink_electrical COMMAND test_xlink_electrical)
    add_test(NAME v21_xlink_native COMMAND "${Python3_EXECUTABLE}" -B -m unittest validation_engine.tests.test_xlink_native -v)
    set_tests_properties(v21_xlink_native PROPERTIES WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/..")
    add_test(NAME v21_xlink_cli COMMAND "${Python3_EXECUTABLE}" -B
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_xlink_cli.py" "$<TARGET_FILE:validation_core>")
    set_tests_properties(v21_xlink_cli PROPERTIES TIMEOUT 180 SKIP_RETURN_CODE 77
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/..")
    add_test(NAME l4_contract COMMAND "${Python3_EXECUTABLE}" -B
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_contract.py" "$<TARGET_FILE:validation_core>")
    set_tests_properties(l4_contract PROPERTIES TIMEOUT 90
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/..")
endif()
