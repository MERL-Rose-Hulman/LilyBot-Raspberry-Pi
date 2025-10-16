#pragma once

#include <cstddef>
#include <cstdint>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace lilybot {

class I2CError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class I2CBus {
public:
    explicit I2CBus(int bus_id, bool non_blocking = false);
    I2CBus(const I2CBus&) = delete;
    I2CBus& operator=(const I2CBus&) = delete;
    I2CBus(I2CBus&&) noexcept;
    I2CBus& operator=(I2CBus&&) noexcept;
    ~I2CBus();

    int fd() const noexcept { return fd_; }
    int bus_id() const noexcept { return bus_id_; }

    void write_byte(uint8_t address, uint8_t value);
    void write_byte_data(uint8_t address, uint8_t reg, uint8_t value);
    void write_word_data(uint8_t address, uint8_t reg, uint16_t value);
    void write_block_data(uint8_t address, uint8_t reg, const uint8_t* data, size_t length);

    uint8_t read_byte(uint8_t address);
    uint8_t read_byte_data(uint8_t address, uint8_t reg);
    uint16_t read_word_data(uint8_t address, uint8_t reg);
    void read_block_data(uint8_t address, uint8_t reg, uint8_t* buffer, size_t length);

private:
    void transfer(uint8_t address,
                  std::vector<uint8_t>& tx_buffer,
                  std::vector<uint8_t>& rx_buffer);

    int bus_id_;
    int fd_;
    bool non_blocking_;
    std::mutex mutex_;
};

}  // namespace lilybot
