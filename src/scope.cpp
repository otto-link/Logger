/* Copyright (c) 2026 Otto Link. Distributed under the terms of the GNU General
   Public License. The full license is in the file LICENSE, distributed with
   this software. */

#include "logger/scope.hpp"

namespace logger
{

LogScope::LogScope(const char*               module,
                   std::string               name,
                   spdlog::level::level_enum level)
    : m_module(module)
    , m_name(std::move(name))
    , m_level(level)
{
    Logger::instance().log(m_module, m_level, "<{}>", m_name);
    Logger::push_indent();

#ifdef LOGGER_ENABLE_TIMING
    m_start = std::chrono::steady_clock::now();
#endif
}

LogScope::~LogScope()
{
    Logger::pop_indent();

#ifdef LOGGER_ENABLE_TIMING
    const auto end = std::chrono::steady_clock::now();
    const auto elapsed_ms =
        std::chrono::duration<double, std::milli>(end - m_start).count();

    Logger::instance().log(m_module, m_level, "</{}> ({:.2f} ms)", m_name, elapsed_ms);
#else
    Logger::instance().log(m_module, m_level, "</{}>", m_name);
#endif
}

} // namespace logger
