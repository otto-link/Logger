/* Copyright (c) 2026 Otto Link. Distributed under the terms of the GNU General
   Public License. The full license is in the file LICENSE, distributed with
   this software. */

#pragma once

#include <chrono>
#include <string>

#include "logger/logger.hpp"

namespace logger
{

class LogScope
{
public:
    LogScope(const char*               module,
             std::string               name,
             spdlog::level::level_enum level = spdlog::level::info);
    ~LogScope();

    LogScope(const LogScope&) = delete;
    LogScope& operator=(const LogScope&) = delete;
    LogScope(LogScope&&) = delete;
    LogScope& operator=(LogScope&&) = delete;

private:
    const char*               m_module;
    std::string               m_name;
    spdlog::level::level_enum m_level;

#ifdef LOGGER_ENABLE_TIMING
    std::chrono::steady_clock::time_point m_start;
#endif
};

} // namespace logger

// --- Scope macros

#define LOGGER_CONCAT_IMPL(a, b) a##b
#define LOGGER_CONCAT(a, b) LOGGER_CONCAT_IMPL(a, b)

#define LOG_SCOPE(name) \
    ::logger::LogScope LOGGER_CONCAT(_log_scope_, __LINE__)(LOGGER_MODULE_NAME, name)

#define LOG_FUNCTION() LOG_SCOPE(__func__)
