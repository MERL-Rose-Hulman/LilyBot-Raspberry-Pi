#include "lilybot/tb6612.hpp"

#include <algorithm>
#include <array>
#include <cmath>

namespace lilybot {

namespace {
constexpr uint8_t REG_SPEED = 0x82;
constexpr uint8_t REG_DIRECTION = 0xAA;

int clamp_speed(int value) {
    return std::clamp(value, -255, 255);
}

}  // namespace

TB6612Controller::TB6612Controller(I2CBus& bus, uint8_t address)
    : bus_(&bus),
      address_(address),
      speed_a_(0),
      speed_b_(0) {}

void TB6612Controller::apply() {
    const std::array<uint8_t, 2> speeds = {
        static_cast<uint8_t>(std::abs(speed_a_)),
        static_cast<uint8_t>(std::abs(speed_b_))
    };
    bus_->write_block_data(address_, REG_SPEED, speeds.data(), speeds.size());

    uint8_t dir = 0x00;
    if (speed_a_ > 0) {
        dir |= 0x01;
    } else if (speed_a_ < 0) {
        dir |= 0x02;
    }
    if (speed_b_ > 0) {
        dir |= 0x04;
    } else if (speed_b_ < 0) {
        dir |= 0x08;
    }
    bus_->write_byte_data(address_, REG_DIRECTION, dir);
}

void TB6612Controller::run(Channel channel, int speed) {
    speed = clamp_speed(speed);
    if (channel == Channel::A) {
        speed_a_ = speed;
    } else {
        speed_b_ = speed;
    }
    apply();
}

void TB6612Controller::stop(Channel channel) {
    if (channel == Channel::A) {
        speed_a_ = 0;
    } else {
        speed_b_ = 0;
    }
    apply();
}

void TB6612Controller::stop_all() {
    speed_a_ = 0;
    speed_b_ = 0;
    apply();
}

}  // namespace lilybot
