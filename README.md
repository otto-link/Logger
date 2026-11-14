# Logger

Shared C++17 logging library built on [spdlog](https://github.com/gabime/spdlog) (fetched via CMake `FetchContent`), designed to be shared across submodules.

## Features

- Thread-safe singleton [`Logger`](include/logger/logger.hpp)
- Console logging (colorized, aligned log levels) and optional file logging
- Automatic per-module log prefixing via `LOGGER_MODULE_NAME`
- RAII [`LogScope`](include/logger/scope.hpp) for thread-local indentation and optional scope timing (`LOGGER_ENABLE_TIMING`)

## Basic Usage

```cpp
#include "logger/logger.hpp"
#include "logger/scope.hpp"

void nested_work()
{
    LOG_FUNCTION();
    LOG_INFO("inside nested_work: {}", 42);
}

int main()
{
    auto& log = logger::Logger::instance();
    log.set_level(spdlog::level::trace);
    log.enable_file_logging("app.log");

    {
        LOG_SCOPE("outer_scope");
        LOG_WARN("warning in outer scope");
        nested_work();
    }

    log.flush();
    return 0;
}
```

Example output:

```text
[21:15:00.123] [info    ] [TestModule] <outer_scope>
[21:15:00.123] [warning ] [TestModule]   warning in outer scope
[21:15:00.123] [info    ] [TestModule]   <nested_work>
[21:15:00.123] [info    ] [TestModule]     inside nested_work: 42
[21:15:00.123] [info    ] [TestModule]   </nested_work> (0.02 ms)
[21:15:00.123] [info    ] [TestModule] </outer_scope> (0.09 ms)
```

Available log macros: `LOG_TRACE`, `LOG_DEBUG`, `LOG_INFO`, `LOG_WARN`, `LOG_ERROR`, `LOG_CRITICAL`.

## Linking with CMake

Add `Logger` as a subdirectory (e.g. git submodule) and link against `Logger::Logger`. Define `LOGGER_MODULE_NAME` per target to prefix logs with the consuming module's name:

```cmake
add_subdirectory(external/Logger)

add_executable(my_module main.cpp)
target_link_libraries(my_module PRIVATE Logger::Logger)
target_compile_definitions(my_module PRIVATE LOGGER_MODULE_NAME="MyModule")
```

> **Note:** Scope indentation (`t_indent_depth`) is preserved across modules on the same thread when they are linked into the same binary. Because `logger` is built as a `STATIC` library, if multiple separate shared libraries (`.so`/`.dll`) each link `Logger::Logger`, they may get separate `Logger` instances unless `logger` is built as `SHARED`.

### CMake Options

| Option | Default | Description |
| --- | --- | --- |
| `LOGGER_ENABLE_TIMING` | `ON` | Enable elapsed time output on `LogScope` exit |
| `LOGGER_BUILD_TESTS` | `ON` (top-level) / `OFF` (subproject) | Build the `test_logger` executable |

## License

This project is licensed under the GNU Lesser General Public License v2.1 — see [LICENSE](LICENSE) for details.
