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

class LogContext
{
public:
    LogContext(const char*               module,
               std::string               name,
               spdlog::level::level_enum level = spdlog::level::info);
    explicit LogContext(ContextId id);
    ~LogContext();

    LogContext(const LogContext&) = delete;
    LogContext& operator=(const LogContext&) = delete;
    LogContext(LogContext&&) = delete;
    LogContext& operator=(LogContext&&) = delete;

    ContextId id() const { return m_id; }

private:
    const char*               m_module = nullptr;
    std::string               m_name;
    spdlog::level::level_enum m_level = spdlog::level::info;
    ContextId                 m_id = 0;
    bool                      m_attached = false;

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

#define LOG_CONTEXT(id_var, name)                                                           \
    ::logger::LogContext LOGGER_CONCAT(_log_context_, __LINE__)(LOGGER_MODULE_NAME, name); \
    const ::logger::ContextId id_var = LOGGER_CONCAT(_log_context_, __LINE__).id()

#define LOG_CONTEXT_ATTACH(id) \
    ::logger::LogContext LOGGER_CONCAT(_log_context_attach_, __LINE__)(id)
