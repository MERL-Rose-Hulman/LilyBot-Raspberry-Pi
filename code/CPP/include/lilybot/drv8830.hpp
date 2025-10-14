#pragma once

#include "lilybot/i2c_bus.hpp"

#include <cstdint>

namespace lilybot {

class DRV8830 {
public:
    static constexpr uint8_t kDefaultAddress = 0x60;

    DRV8830(I2CBus& bus, uint8_t address = kDefaultAddress);

    void set_speed(int speed_percent);
    void stop();
    void standby();
    void brake();

    uint8_t read_fault();
    void clear_fault();

private:
    void write_control(uint8_t magnitude, uint8_t mode);

    I2CBus* bus_;
    uint8_t address_;
};

}  // namespace lilybot
