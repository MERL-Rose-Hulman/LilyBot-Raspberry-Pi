#pragma once

#include "lilybot/gpio_line.hpp"

#include <chrono>
#include <optional>

namespace lilybot {

class UltrasonicSensor {
public:
    struct Options {
        std::chrono::microseconds timeout_wait_high{1000};
        std::chrono::microseconds timeout_wait_low{10000};
        unsigned retries{3};
    };

    UltrasonicSensor(int pin, Options opts = Options{});

    std::optional<float> read_distance_cm();

private:
    std::optional<float> perform_read();

    GpioLine dio_;
    Options options_;
};

}  // namespace lilybot
