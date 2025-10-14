#pragma once

#include "lilybot/hal/i2c_bus.hpp"

#include <array>
#include <cstdint>
#include <mutex>
#include <stdexcept>

namespace lilybot {

class GroveHatError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class GroveHat {
public:
    enum class PinMode : uint8_t {
        Input = 0,
        Output = 1,
    };

    explicit GroveHat(I2CBus& bus, uint8_t address = 0x04);

    void set_pin_mode(uint8_t pin, PinMode mode);
    void digital_write(uint8_t pin, bool value);
    bool digital_read(uint8_t pin);
    uint16_t ultrasonic_read(uint8_t pin);

private:
    void write_command(const std::array<uint8_t, 4>& cmd);
    void read_bytes(uint8_t* buffer, size_t length);
    void sleep_short() const;

    I2CBus* bus_;
    uint8_t address_;
    std::mutex mutex_;
};

}  // namespace lilybot
