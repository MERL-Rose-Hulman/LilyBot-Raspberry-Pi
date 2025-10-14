#include "lilybot/i2c_bus.hpp"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <sys/ioctl.h>
#include <unistd.h>

#ifndef __has_include
#define __has_include(x) 0
#endif

#if __has_include(<i2c/smbus.h>)
#include <i2c/smbus.h>
#define LILYBOT_HAS_NATIVE_SMBUS 1
#else
#define LILYBOT_HAS_NATIVE_SMBUS 0
#endif

#if !LILYBOT_HAS_NATIVE_SMBUS
#ifndef I2C_SMBUS_BLOCK_MAX
#define I2C_SMBUS_BLOCK_MAX 32
#endif

namespace {

int i2c_smbus_access(int fd,
                     char read_write,
                     uint8_t command,
                     int size,
                     union i2c_smbus_data* data) {
    struct i2c_smbus_ioctl_data args {};
    args.read_write = read_write;
    args.command = command;
    args.size = size;
    args.data = data;
    return ioctl(fd, I2C_SMBUS, &args);
}

int i2c_smbus_write_byte(int fd, uint8_t value) {
    return i2c_smbus_access(fd, I2C_SMBUS_WRITE, value, I2C_SMBUS_BYTE, nullptr);
}

int i2c_smbus_write_byte_data(int fd, uint8_t command, uint8_t value) {
    union i2c_smbus_data data {};
    data.byte = value;
    return i2c_smbus_access(fd, I2C_SMBUS_WRITE, command, I2C_SMBUS_BYTE_DATA, &data);
}

int i2c_smbus_write_word_data(int fd, uint8_t command, uint16_t value) {
    union i2c_smbus_data data {};
    data.word = value;
    return i2c_smbus_access(fd, I2C_SMBUS_WRITE, command, I2C_SMBUS_WORD_DATA, &data);
}

int i2c_smbus_write_i2c_block_data(int fd,
                                   uint8_t command,
                                   uint8_t length,
                                   const uint8_t* values) {
    union i2c_smbus_data data {};
    if (length > I2C_SMBUS_BLOCK_MAX) {
        length = I2C_SMBUS_BLOCK_MAX;
    }
    data.block[0] = length;
    for (uint8_t i = 0; i < length; ++i) {
        data.block[i + 1] = values ? values[i] : 0;
    }
    return i2c_smbus_access(fd, I2C_SMBUS_WRITE, command, I2C_SMBUS_I2C_BLOCK_DATA, &data);
}

int i2c_smbus_read_byte(int fd) {
    union i2c_smbus_data data {};
    if (i2c_smbus_access(fd, I2C_SMBUS_READ, 0, I2C_SMBUS_BYTE, &data) < 0) {
        return -1;
    }
    return data.byte & 0xFF;
}

int i2c_smbus_read_byte_data(int fd, uint8_t command) {
    union i2c_smbus_data data {};
    if (i2c_smbus_access(fd, I2C_SMBUS_READ, command, I2C_SMBUS_BYTE_DATA, &data) < 0) {
        return -1;
    }
    return data.byte & 0xFF;
}

int i2c_smbus_read_word_data(int fd, uint8_t command) {
    union i2c_smbus_data data {};
    if (i2c_smbus_access(fd, I2C_SMBUS_READ, command, I2C_SMBUS_WORD_DATA, &data) < 0) {
        return -1;
    }
    return data.word & 0xFFFF;
}

}  // namespace
#endif  // !LILYBOT_HAS_NATIVE_SMBUS
#include <stdexcept>
#include <string>

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
