#include "lilybot/i2c_bus.hpp"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <i2c/smbus.h>
#include <stdexcept>
#include <string>
#include <sys/ioctl.h>
#include <unistd.h>

namespace lilybot {

namespace {

[[noreturn]] void throw_errno(const std::string& context) {
    throw I2CError(context + ": " + std::strerror(errno));
}

}  // namespace

I2CBus::I2CBus(int bus_id, bool non_blocking)
    : bus_id_(bus_id),
      fd_(-1),
      non_blocking_(non_blocking) {
    const std::string path = "/dev/i2c-" + std::to_string(bus_id);
    int flags = O_RDWR;
    if (non_blocking_) {
        flags |= O_NONBLOCK;
    }
    fd_ = ::open(path.c_str(), flags);
    if (fd_ < 0) {
        throw_errno("Failed to open " + path);
    }
}

I2CBus::I2CBus(I2CBus&& other) noexcept
    : bus_id_(other.bus_id_),
      fd_(other.fd_),
      non_blocking_(other.non_blocking_) {
    other.fd_ = -1;
}

I2CBus& I2CBus::operator=(I2CBus&& other) noexcept {
    if (this != &other) {
        if (fd_ >= 0) {
            ::close(fd_);
        }
        bus_id_ = other.bus_id_;
        fd_ = other.fd_;
        non_blocking_ = other.non_blocking_;
        other.fd_ = -1;
    }
    return *this;
}

I2CBus::~I2CBus() {
    if (fd_ >= 0) {
        ::close(fd_);
    }
}

void I2CBus::select_device(uint8_t address) {
    if (fd_ < 0) {
        throw I2CError("I2C bus not open");
    }
    if (ioctl(fd_, I2C_SLAVE, address) < 0) {
        throw_errno("Failed to select I2C address 0x" + std::to_string(address));
    }
}

void I2CBus::write_byte(uint8_t address, uint8_t value) {
    std::lock_guard<std::mutex> lock(mutex_);
    select_device(address);
    if (i2c_smbus_write_byte(fd_, value) < 0) {
        throw_errno("i2c_smbus_write_byte failed");
    }
}

void I2CBus::write_byte_data(uint8_t address, uint8_t reg, uint8_t value) {
    std::lock_guard<std::mutex> lock(mutex_);
    select_device(address);
    if (i2c_smbus_write_byte_data(fd_, reg, value) < 0) {
        throw_errno("i2c_smbus_write_byte_data failed");
    }
}

void I2CBus::write_word_data(uint8_t address, uint8_t reg, uint16_t value) {
    std::lock_guard<std::mutex> lock(mutex_);
    select_device(address);
    if (i2c_smbus_write_word_data(fd_, reg, value) < 0) {
        throw_errno("i2c_smbus_write_word_data failed");
    }
}

void I2CBus::write_block_data(uint8_t address, uint8_t reg, const uint8_t* data, size_t length) {
    std::lock_guard<std::mutex> lock(mutex_);
    select_device(address);
    if (length > I2C_SMBUS_BLOCK_MAX) {
        throw I2CError("I2C block write length exceeds SMBus limit");
    }
    if (i2c_smbus_write_i2c_block_data(fd_, reg, static_cast<uint8_t>(length), data) < 0) {
        throw_errno("i2c_smbus_write_i2c_block_data failed");
    }
}

uint8_t I2CBus::read_byte(uint8_t address) {
    std::lock_guard<std::mutex> lock(mutex_);
    select_device(address);
    int ret = i2c_smbus_read_byte(fd_);
    if (ret < 0) {
        throw_errno("i2c_smbus_read_byte failed");
    }
    return static_cast<uint8_t>(ret);
}

uint8_t I2CBus::read_byte_data(uint8_t address, uint8_t reg) {
    std::lock_guard<std::mutex> lock(mutex_);
    select_device(address);
    int ret = i2c_smbus_read_byte_data(fd_, reg);
    if (ret < 0) {
        throw_errno("i2c_smbus_read_byte_data failed");
    }
    return static_cast<uint8_t>(ret);
}

uint16_t I2CBus::read_word_data(uint8_t address, uint8_t reg) {
    std::lock_guard<std::mutex> lock(mutex_);
    select_device(address);
    int ret = i2c_smbus_read_word_data(fd_, reg);
    if (ret < 0) {
        throw_errno("i2c_smbus_read_word_data failed");
    }
    return static_cast<uint16_t>(ret);
}

}  // namespace lilybot
