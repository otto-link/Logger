/* Copyright (c) 2026 Otto Link. Distributed under the terms of the GNU General
   Public License. The full license is in the file LICENSE, distributed with
   this software. */
   
#pragma once

#include <memory>
#include <mutex>
#include <string>

#include <spdlog/spdlog.h>

#ifndef LOGGER_MODULE_NAME
#define LOGGER_MODULE_NAME "default"
#endif

namespace logger
{

class Logger
{
public:
    static Logger& instance();

    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;
    Logger(Logger&&) = delete;
    Logger& operator=(Logger&&) = delete;

    void enable_file_logging(const std::string& file_path, bool truncate = false);
    void set_level(spdlog::level::level_enum level);
    void flush();

    // --- Thread-local indentation helpers

    static void        push_indent();
    static void        pop_indent();
    static int         indent_depth();
    static std::string indent_prefix();

    // --- Logging methods

    template <typename... Args>
    void log(const char*                    module,
             spdlog::level::level_enum      level,
             spdlog::format_string_t<Args...> fmt,
             Args&&...                      args)
    {
        std::string message = fmt::format(fmt, std::forward<Args>(args)...);
        log_raw(module, level, message);
    }

private:
    Logger();
    ~Logger() = default;

    void log_raw(const char*               module,
                 spdlog::level::level_enum level,
                 const std::string&        message);

    std::shared_ptr<spdlog::logger> m_logger;
    std::mutex                      m_mutex;
};

} // namespace logger

// --- Convenience macros

#define LOG_TRACE(...) \
    ::logger::Logger::instance().log(LOGGER_MODULE_NAME, spdlog::level::trace, __VA_ARGS__)

#define LOG_DEBUG(...) \
    ::logger::Logger::instance().log(LOGGER_MODULE_NAME, spdlog::level::debug, __VA_ARGS__)

#define LOG_INFO(...) \
    ::logger::Logger::instance().log(LOGGER_MODULE_NAME, spdlog::level::info, __VA_ARGS__)

#define LOG_WARN(...) \
    ::logger::Logger::instance().log(LOGGER_MODULE_NAME, spdlog::level::warn, __VA_ARGS__)

#define LOG_ERROR(...) \
    ::logger::Logger::instance().log(LOGGER_MODULE_NAME, spdlog::level::err, __VA_ARGS__)

#define LOG_CRITICAL(...) \
    ::logger::Logger::instance().log(LOGGER_MODULE_NAME, spdlog::level::critical, __VA_ARGS__)
