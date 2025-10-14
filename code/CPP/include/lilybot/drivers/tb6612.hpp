#pragma once

#include "lilybot/hal/i2c_bus.hpp"

#include <cstdint>

namespace lilybot {

class TB6612Controller {
public:
    enum class Channel { A, B };

    static constexpr uint8_t kDefaultAddress = 0x14;

    explicit TB6612Controller(I2CBus& bus, uint8_t address = kDefaultAddress);

    void run(Channel channel, int speed);       // speed: -255..255
    void stop(Channel channel);
    void stop_all();

private:
    void apply();

    I2CBus* bus_;
    uint8_t address_;
    int speed_a_;
    int speed_b_;
};

}  // namespace lilybot
