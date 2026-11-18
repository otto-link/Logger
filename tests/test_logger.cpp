#include "logger/logger.hpp"
#include "logger/scope.hpp"

#include <cassert>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <thread>

namespace
{

void nested_work()
{
    LOG_FUNCTION();
    LOG_INFO("inside nested_work: {}", 42);

    {
      LOG_SCOPE("further inside");
      LOG_TRACE("trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside trace further inside ");
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

    // --- Nested fire-and-forget threads (3 levels)

    {
        std::atomic<int> remaining{2};

        auto launch_level1 = [&remaining]() {
            LOG_CONTEXT(ctx1, "level1_fct");
            LOG_INFO("level1 started");

            for (int i = 0; i < 2; ++i)
            {
                std::thread([ctx1, i, &remaining]() {
                    LOG_CONTEXT_ATTACH(ctx1);
                    LOG_CONTEXT(ctx2, "level2_sub");
                    LOG_INFO("level2 {} started", i);

                    std::thread([ctx2, i, &remaining]() {
                        LOG_CONTEXT_ATTACH(ctx2);
                        LOG_CONTEXT(ctx3, "level3_leaf");
                        std::this_thread::sleep_for(std::chrono::milliseconds(50));
                        LOG_INFO("level3 {} finished", i);
                        remaining.fetch_sub(1);
                    }).detach();
                }).detach();
            }
        };

        launch_level1();
        assert(logger::Logger::current_context() == 0);

        while (remaining.load() > 0)
            std::this_thread::sleep_for(std::chrono::milliseconds(10));

        logger::Logger::instance().flush();

        const std::string ctx_contents = read_file(log_path);
        assert(ctx_contents.find("[ctx:1] <level1_fct>") != std::string::npos);
        assert(ctx_contents.find("[ctx:1]   level1 started") != std::string::npos);
        assert(ctx_contents.find("[ctx:1/") != std::string::npos);
        assert(ctx_contents.find("level2 0 started") != std::string::npos);
        assert(ctx_contents.find("level3 0 finished") != std::string::npos);
        assert(ctx_contents.find("level3 1 finished") != std::string::npos);
    }

    // --- Periodic logging loop

    for (int i = 0; i < 10; ++i)
    {
        LOG_SCOPE("periodic_tick");
        LOG_DEBUG("tick {}", i);
        if (i % 3 == 0)
            LOG_WARN("periodic warning at tick {}", i);

        logger::Logger::instance().flush();
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }

    // std::filesystem::remove(log_path);
    return 0;
}
