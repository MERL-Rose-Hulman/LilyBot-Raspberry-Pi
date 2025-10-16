#include "lilybot/hal/grove_hat.hpp"

#include <chrono>
#include <cerrno>
#include <cstring>
#include <iostream>
#include <thread>

namespace lilybot {

namespace {
constexpr uint8_t CMD_DIGITAL_READ = 0x01;
constexpr uint8_t CMD_DIGITAL_WRITE = 0x02;
constexpr uint8_t CMD_PIN_MODE = 0x05;
constexpr uint8_t CMD_ULTRASONIC_READ = 0x07;
}  // namespace

GroveHat::GroveHat(I2CBus& bus, uint8_t address)
    : bus_(&bus),
      address_(address) {}

void GroveHat::sleep_short() const {
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
}

void GroveHat::write_command(const std::array<uint8_t, 4>& cmd) {
    std::lock_guard<std::mutex> lock(mutex_);
    bus_->write_block_data(address_, 0x01, cmd.data(), cmd.size());
}

void GroveHat::read_bytes(uint8_t reg, uint8_t* buffer, size_t length) {
    std::lock_guard<std::mutex> lock(mutex_);
    bus_->read_block_data(address_, reg, buffer, length);
}

void GroveHat::set_pin_mode(uint8_t pin, PinMode mode) {
    write_command({CMD_PIN_MODE, pin, static_cast<uint8_t>(mode), 0});
    sleep_short();
}

void GroveHat::digital_write(uint8_t pin, bool value) {
    write_command({CMD_DIGITAL_WRITE, pin, static_cast<uint8_t>(value ? 1 : 0), 0});
    sleep_short();
}

bool GroveHat::digital_read(uint8_t pin) {
    write_command({CMD_DIGITAL_READ, pin, 0, 0});
    sleep_short();
    uint8_t buffer[1] = {0};
    read_bytes(buffer, 1);
    return buffer[0] != 0;
}

uint16_t GroveHat::ultrasonic_read(uint8_t pin) {
    write_command({CMD_ULTRASONIC_READ, pin, 0, 0});
    std::this_thread::sleep_for(std::chrono::milliseconds(80));
    std::array<uint8_t, 32> buffer{};
    read_bytes(0x02, buffer.data(), buffer.size());
    std::cerr << "[grove_hat] ultrasonic raw: "
              << static_cast<int>(buffer[0]) << " "
              << static_cast<int>(buffer[1]) << " "
              << static_cast<int>(buffer[2]) << " "
              << static_cast<int>(buffer[3]) << "\n";
    return static_cast<uint16_t>((buffer[0] << 8) | buffer[1]);
}

}  // namespace lilybot
