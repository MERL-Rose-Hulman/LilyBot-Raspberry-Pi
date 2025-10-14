#include "lilybot/drv8830.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace lilybot {

namespace {
constexpr uint8_t CONTROL_REG = 0x00;
constexpr uint8_t FAULT_REG = 0x01;

constexpr uint8_t MODE_STANDBY = 0x00;
constexpr uint8_t MODE_FORWARD = 0x01;
constexpr uint8_t MODE_REVERSE = 0x02;
constexpr uint8_t MODE_BRAKE = 0x03;

int clamp(int value, int lo, int hi) {
    return std::clamp(value, lo, hi);
}
}  // namespace

DRV8830::DRV8830(I2CBus& bus, uint8_t address)
    : bus_(&bus),
      address_(address) {}

void DRV8830::write_control(uint8_t magnitude, uint8_t mode) {
    magnitude = static_cast<uint8_t>(clamp(magnitude, 0, 63));
    mode &= 0x03;
    const uint8_t value = static_cast<uint8_t>((magnitude << 2) | mode);
    bus_->write_byte_data(address_, CONTROL_REG, value);
}

void DRV8830::set_speed(int speed_percent) {
    speed_percent = clamp(speed_percent, -100, 100);
    if (speed_percent == 0) {
        standby();
        return;
    }
    const uint8_t magnitude = static_cast<uint8_t>(
        std::max(1, static_cast<int>(std::round(std::abs(speed_percent) * 63.0 / 100.0))));
    const uint8_t mode = speed_percent > 0 ? MODE_FORWARD : MODE_REVERSE;
    write_control(magnitude, mode);
}

void DRV8830::stop() {
    standby();
}

void DRV8830::standby() {
    write_control(0, MODE_STANDBY);
}

void DRV8830::brake() {
    write_control(0, MODE_BRAKE);
}

uint8_t DRV8830::read_fault() {
    return bus_->read_byte_data(address_, FAULT_REG);
}

void DRV8830::clear_fault() {
    write_control(0, MODE_STANDBY);
}

}  // namespace lilybot
