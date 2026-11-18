/* Copyright (c) 2026 Otto Link. Distributed under the terms of the GNU General
   Public License. The full license is in the file LICENSE, distributed with
   this software. */
   
#include "logger/logger.hpp"

#include <algorithm>
#include <atomic>
#include <vector>

#include <spdlog/sinks/basic_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>

namespace logger
{

namespace
{

std::atomic<ContextId>      g_next_context_id{1};
thread_local int            t_indent_depth = 0;
thread_local std::vector<ContextId> t_context_stack;

} // namespace

// --- Singleton access

Logger& Logger::instance()
{
    static Logger instance;
    return instance;
}

// --- Construction

Logger::Logger()
{
    auto console_sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
#ifdef LOGGER_LOG_THREAD_ID
    console_sink->set_pattern("[%H:%M:%S.%e] [%t] [%^%-8l%$] %v");
#else
    console_sink->set_pattern("[%H:%M:%S.%e] [%^%-8l%$] %v");
#endif

    std::vector<spdlog::sink_ptr> sinks{console_sink};
    m_logger = std::make_shared<spdlog::logger>("logger", sinks.begin(), sinks.end());
    m_logger->set_level(spdlog::level::trace);
}

// --- Configuration

void Logger::enable_file_logging(const std::string& file_path, bool truncate)
{
    std::lock_guard<std::mutex> lock(m_mutex);

    auto file_sink = std::make_shared<spdlog::sinks::basic_file_sink_mt>(file_path, truncate);
#ifdef LOGGER_LOG_THREAD_ID
    file_sink->set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%t] [%-8l] %v");
#else
    file_sink->set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%-8l] %v");
#endif

    m_logger->sinks().push_back(file_sink);
}

void Logger::set_level(spdlog::level::level_enum level)
{
    std::lock_guard<std::mutex> lock(m_mutex);
    m_logger->set_level(level);
}

void Logger::flush()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    m_logger->flush();
}

// --- Thread-local indentation helpers

void Logger::push_indent()
{
    ++t_indent_depth;
}

void Logger::pop_indent()
{
    t_indent_depth = std::max(0, t_indent_depth - 1);
}

int Logger::indent_depth()
{
    return t_indent_depth;
}

std::string Logger::indent_prefix()
{
    return std::string(static_cast<size_t>(t_indent_depth) * 2, ' ');
}

// --- Thread-local context helpers

ContextId Logger::next_context_id()
{
    return g_next_context_id.fetch_add(1, std::memory_order_relaxed);
}

void Logger::push_context(ContextId id)
{
    t_context_stack.push_back(id);
}

void Logger::pop_context()
{
    if (!t_context_stack.empty())
        t_context_stack.pop_back();
}

ContextId Logger::current_context()
{
    return t_context_stack.empty() ? 0 : t_context_stack.back();
}

std::string Logger::context_prefix()
{
    if (t_context_stack.empty())
        return {};

    std::string prefix = "[ctx:";

    for (size_t i = 0; i < t_context_stack.size(); ++i)
    {
        if (i > 0)
            prefix += '/';

        prefix += std::to_string(t_context_stack[i]);
    }

    prefix += "] ";
    return prefix;
}

// --- Internal logging

void Logger::log_raw(const char*               module,
                     spdlog::level::level_enum level,
                     const std::string&        message)
{
    std::lock_guard<std::mutex> lock(m_mutex);

    const char* safe_module = (module != nullptr) ? module : "default";
    m_logger->log(level,
                  "[{}] {}{}{}",
                  safe_module,
                  context_prefix(),
                  indent_prefix(),
                  message);
}

} // namespace logger
