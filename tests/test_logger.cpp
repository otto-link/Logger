#include "logger/logger.hpp"
#include "logger/scope.hpp"

#include <cassert>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

namespace
{

void nested_work()
{
    LOG_FUNCTION();
    LOG_INFO("inside nested_work: {}", 42);

    {
      LOG_SCOPE("further inside");
      LOG_TRACE("trace");
      LOG_ERROR("error");
      LOG_CRITICAL("critical");
    }
}

std::string read_file(const std::string& path)
{
    std::ifstream file(path);
    std::ostringstream ss;
    ss << file.rdbuf();
    return ss.str();
}

} // namespace

int main()
{
    // --- Singleton identity

    assert(&logger::Logger::instance() == &logger::Logger::instance());

    // --- File logging setup

    const std::string log_path = "test_logger_output.log";
    std::filesystem::remove(log_path);

    logger::Logger::instance().enable_file_logging(log_path, true);
    logger::Logger::instance().set_level(spdlog::level::trace);

    // --- Scoped logging and indentation

    LOG_INFO("starting test");
    {
        LOG_SCOPE("outer_scope");
        assert(logger::Logger::indent_depth() == 1);

        LOG_WARN("warning in outer scope");
        nested_work();

        assert(logger::Logger::indent_depth() == 1);
    }
    assert(logger::Logger::indent_depth() == 0);

    logger::Logger::instance().flush();

    // --- Verify log file contents

    const std::string contents = read_file(log_path);
    assert(contents.find("[TestModule] starting test") != std::string::npos);
    assert(contents.find("[TestModule] <outer_scope>") != std::string::npos);
    assert(contents.find("[TestModule]   warning in outer scope") != std::string::npos);
    assert(contents.find("[TestModule]   <nested_work>") != std::string::npos);
    assert(contents.find("[TestModule]     inside nested_work: 42") != std::string::npos);
    assert(contents.find("[TestModule]   </nested_work>") != std::string::npos);
    assert(contents.find("[TestModule] </outer_scope>") != std::string::npos);

#ifdef LOGGER_ENABLE_TIMING
    assert(contents.find("ms)") != std::string::npos);
#endif

    std::filesystem::remove(log_path);
    return 0;
}
