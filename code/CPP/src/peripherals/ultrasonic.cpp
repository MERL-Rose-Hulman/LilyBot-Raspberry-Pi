#include "lilybot/peripherals/ultrasonic.hpp"

#include <chrono>
#include <thread>

namespace lilybot {

namespace {
using clock = std::chrono::steady_clock;

constexpr std::chrono::microseconds kLoopSleep{5};

void sleep_us(unsigned microseconds) {
    std::this_thread::sleep_for(std::chrono::microseconds(microseconds));
}

inline void tiny_pause() {
    std::this_thread::sleep_for(kLoopSleep);
}

}  // namespace

UltrasonicSensor::UltrasonicSensor(int pin, Options opts)
    : dio_(pin),
      options_(opts) {
    dio_.set_direction(GpioLine::Direction::Out);
    dio_.write(false);
}

std::optional<float> UltrasonicSensor::read_distance_cm() {
    for (unsigned i = 0; i < options_.retries; ++i) {
        auto result = perform_read();
        if (result.has_value()) {
            return result;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return std::nullopt;
}

std::optional<float> UltrasonicSensor::perform_read() {
    dio_.set_direction(GpioLine::Direction::Out);
    dio_.write(false);
    sleep_us(2);
    dio_.write(true);
    sleep_us(10);
    dio_.write(false);
    // Allow sensor hardware settle before switching to input mode.
    sleep_us(200);

    dio_.set_direction(GpioLine::Direction::In);
    tiny_pause();

    const auto start_wait = clock::now();
    while (!dio_.read()) {
        if (clock::now() - start_wait > options_.timeout_wait_high) {
            return std::nullopt;
        }
        tiny_pause();
    }

    const auto start_pulse = clock::now();
    while (dio_.read()) {
        if (clock::now() - start_pulse > options_.timeout_wait_low) {
            return std::nullopt;
        }
        tiny_pause();
    }
    const auto end_pulse = clock::now();

    const auto pulse_duration = std::chrono::duration_cast<std::chrono::microseconds>(end_pulse - start_pulse);
    const double duration_us = static_cast<double>(pulse_duration.count());
    if (duration_us <= 0.0 || duration_us > 40000.0) {
        return std::nullopt;
    }

    const double distance_cm = duration_us / 58.0;  // speed of sound round trip
    return static_cast<float>(distance_cm);
}

HatUltrasonicSensor::HatUltrasonicSensor(GroveHat& hat, uint8_t pin)
    : hat_(&hat),
      pin_(pin) {
    hat_->set_pin_mode(pin_, GroveHat::PinMode::Input);
}

std::optional<float> HatUltrasonicSensor::read_distance_cm() {
    if (hat_ == nullptr) {
        return std::nullopt;
    }
    const uint16_t raw = hat_->ultrasonic_read(pin_);
    if (raw == 0) {
        return std::nullopt;
    }
    return static_cast<float>(raw);
}

}  // namespace lilybot
