#pragma once

#include "lilybot/hal/gpio_line.hpp"
#include "lilybot/hal/grove_hat.hpp"

#include <chrono>
#include <optional>

namespace lilybot {

class UltrasonicSensor {
public:
    struct Options {
        std::chrono::microseconds timeout_wait_high;
        std::chrono::microseconds timeout_wait_low;
        unsigned retries;

        constexpr Options(
            std::chrono::microseconds high = std::chrono::microseconds{1000},
            std::chrono::microseconds low = std::chrono::microseconds{10000},
            unsigned retry_count = 3)
            : timeout_wait_high(high),
              timeout_wait_low(low),
              retries(retry_count) {}
    };

    UltrasonicSensor(int pin, Options opts = Options{});

    std::optional<float> read_distance_cm();

private:
    std::optional<float> perform_read();

    GpioLine dio_;
    Options options_;
};

class HatUltrasonicSensor {
public:
    HatUltrasonicSensor(GroveHat& hat, uint8_t pin);

    std::optional<float> read_distance_cm();

private:
    GroveHat* hat_;
    uint8_t pin_;
};

}  // namespace lilybot
