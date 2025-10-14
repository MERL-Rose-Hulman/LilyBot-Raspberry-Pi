#pragma once

#include "lilybot/hal/i2c_bus.hpp"

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace lilybot {

class GroveRGBLCD {
public:
    static constexpr uint8_t kTextAddress = 0x3E;
    static constexpr uint8_t kDefaultPwmAddress = 0x30;

    GroveRGBLCD(I2CBus& bus,
                uint8_t text_addr = kTextAddress,
                bool text_only = false,
                std::optional<uint8_t> forced_rgb_addr = std::nullopt);

    void clear();
    void home();
    void set_cursor(uint8_t col, uint8_t row);
    void print_line(const std::string& text, uint8_t row);
    void write(const std::string& text);
    void set_color(uint8_t r, uint8_t g, uint8_t b);
    void set_color(const std::string& name);

    bool backlight_available() const noexcept { return backlight_type_ != Backlight::None; }
    uint8_t columns() const noexcept { return cols_; }
    uint8_t rows() const noexcept { return rows_; }

private:
    enum class Backlight { None, PCA9633, SGM31323 };

    void init_text();
    void detect_backlight(std::optional<uint8_t> forced_rgb_addr);
    void set_color_pca(uint8_t r, uint8_t g, uint8_t b);
    void set_color_sgm(uint8_t r, uint8_t g, uint8_t b);

    I2CBus* bus_;
    uint8_t text_addr_;
    Backlight backlight_type_;
    uint8_t backlight_addr_;
    uint8_t cols_;
    uint8_t rows_;
};

}  // namespace lilybot
