#include "lilybot/hal/i2c_bus.hpp"

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <string>
#include <sys/ioctl.h>
#include <unistd.h>
#include <vector>

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

void I2CBus::transfer(uint8_t address,
                      std::vector<uint8_t>& tx_buffer,
                      std::vector<uint8_t>& rx_buffer) {
    if (fd_ < 0) {
        throw I2CError("I2C bus not open");
    }
    if (tx_buffer.empty() && rx_buffer.empty()) {
        return;
    }
    if (tx_buffer.size() > std::numeric_limits<__u16>::max() ||
        rx_buffer.size() > std::numeric_limits<__u16>::max()) {
        throw I2CError("I2C transfer length exceeds kernel limit");
    }

    std::array<i2c_msg, 2> messages{};
    std::size_t msg_count = 0;

    if (!tx_buffer.empty()) {
        messages[msg_count].addr = static_cast<__u16>(address);
        messages[msg_count].flags = 0;
        messages[msg_count].len = static_cast<__u16>(tx_buffer.size());
        messages[msg_count].buf = tx_buffer.data();
        ++msg_count;
    }
    if (!rx_buffer.empty()) {
        messages[msg_count].addr = static_cast<__u16>(address);
        messages[msg_count].flags = I2C_M_RD;
        messages[msg_count].len = static_cast<__u16>(rx_buffer.size());
        messages[msg_count].buf = rx_buffer.data();
        ++msg_count;
    }

    i2c_rdwr_ioctl_data ioctl_data{};
    ioctl_data.msgs = messages.data();
    ioctl_data.nmsgs = static_cast<__u32>(msg_count);

    if (ioctl(fd_, I2C_RDWR, &ioctl_data) < 0) {
        throw_errno("I2C_RDWR ioctl failed");
    }
}

void I2CBus::write_byte(uint8_t address, uint8_t value) {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<uint8_t> tx = {value};
    std::vector<uint8_t> rx;
    transfer(address, tx, rx);
}

void I2CBus::write_byte_data(uint8_t address, uint8_t reg, uint8_t value) {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<uint8_t> tx = {reg, value};
    std::vector<uint8_t> rx;
    transfer(address, tx, rx);
}

void I2CBus::write_word_data(uint8_t address, uint8_t reg, uint16_t value) {
    std::lock_guard<std::mutex> lock(mutex_);
    // Word writes expect little-endian payload, matching SMBus semantics.
    std::vector<uint8_t> tx = {
        reg,
        static_cast<uint8_t>(value & 0xFF),
        static_cast<uint8_t>((value >> 8) & 0xFF)
    };
    std::vector<uint8_t> rx;
    transfer(address, tx, rx);
}

void I2CBus::write_block_data(uint8_t address,
                              uint8_t reg,
                              const uint8_t* data,
                              size_t length) {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<uint8_t> tx;
    tx.reserve(length + 1);
    tx.push_back(reg);
    if (length > 0) {
        if (data == nullptr) {
            throw I2CError("Null data pointer for I2C block write");
        }
        tx.insert(tx.end(), data, data + length);
    }
    std::vector<uint8_t> rx;
    transfer(address, tx, rx);
}

uint8_t I2CBus::read_byte(uint8_t address) {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<uint8_t> tx;
    std::vector<uint8_t> rx(1, 0);
    transfer(address, tx, rx);
    return rx[0];
}

uint8_t I2CBus::read_byte_data(uint8_t address, uint8_t reg) {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<uint8_t> tx = {reg};
    std::vector<uint8_t> rx(1, 0);
    transfer(address, tx, rx);
    return rx[0];
}

uint16_t I2CBus::read_word_data(uint8_t address, uint8_t reg) {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<uint8_t> tx = {reg};
    std::vector<uint8_t> rx(2, 0);
    transfer(address, tx, rx);
    return static_cast<uint16_t>(rx[0]) |
           (static_cast<uint16_t>(rx[1]) << 8);
}

void I2CBus::read_block_data(uint8_t address,
                             uint8_t reg,
                             uint8_t* buffer,
                             size_t length) {
    if (length == 0) {
        return;
    }
    if (buffer == nullptr) {
        throw I2CError("Null buffer for I2C block read");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<uint8_t> tx = {reg};
    std::vector<uint8_t> rx(length, 0);
    transfer(address, tx, rx);
    std::copy(rx.begin(), rx.end(), buffer);
}

}  // namespace lilybot
