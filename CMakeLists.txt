cmake_minimum_required(VERSION 3.16)
project(Logger LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# --- Options

option(LOGGER_ENABLE_TIMING "Enable RAII scope timing in log output" ON)
option(LOGGER_BUILD_TESTS "Build Logger tests" ${PROJECT_IS_TOP_LEVEL})

# --- Dependencies

include(FetchContent)

FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG        v1.14.1
)
FetchContent_MakeAvailable(spdlog)

# --- Library target

add_library(logger STATIC
    src/logger.cpp
    src/scope.cpp
)
add_library(Logger::Logger ALIAS logger)

target_include_directories(logger
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(logger
    PUBLIC
        spdlog::spdlog
)

if(LOGGER_ENABLE_TIMING)
    target_compile_definitions(logger PUBLIC LOGGER_ENABLE_TIMING)
endif()

# --- Tests

if(LOGGER_BUILD_TESTS)
    enable_testing()
    add_executable(test_logger tests/test_logger.cpp)
    target_link_libraries(test_logger PRIVATE Logger::Logger)
    target_compile_definitions(test_logger PRIVATE LOGGER_MODULE_NAME="TestModule")
    add_test(NAME test_logger COMMAND test_logger)
endif()
