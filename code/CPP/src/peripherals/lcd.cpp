#include "lilybot/peripherals/lcd.hpp"

#include "lilybot/hal/i2c_bus.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <chrono>
#include <map>
#include <thread>

namespace lilybot {

namespace {

constexpr uint8_t LCD_CMD = 0x80;
constexpr uint8_t LCD_DATA = 0x40;

constexpr uint8_t CMD_CLEAR_DISPLAY = 0x01;
constexpr uint8_t CMD_RETURN_HOME = 0x02;
constexpr uint8_t CMD_ENTRY_MODE_SET = 0x04;
constexpr uint8_t CMD_DISPLAY_CONTROL = 0x08;
constexpr uint8_t CMD_FUNCTION_SET = 0x20;
constexpr uint8_t CMD_SET_DDRAM_ADDR = 0x80;

constexpr uint8_t ENTRY_LEFT = 0x02;
constexpr uint8_t DISPLAY_ON = 0x04;
constexpr uint8_t CURSOR_OFF = 0x00;
constexpr uint8_t BLINK_OFF = 0x00;
constexpr uint8_t FUNC_2LINE = 0x08;
constexpr uint8_t FUNC_5x8 = 0x00;

constexpr std::array<uint8_t, 4> ROW_OFFSETS = {0x00, 0x40, 0x14, 0x54};

constexpr std::array<uint8_t, 8> PCA_ADDRS = {0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67};
constexpr uint8_t PCA_MODE1 = 0x00;
constexpr uint8_t PCA_MODE2 = 0x01;
constexpr uint8_t PCA_LEDOUT = 0x08;
constexpr uint8_t PCA_BLUE = 0x02;
constexpr uint8_t PCA_GREEN = 0x03;
constexpr uint8_t PCA_RED = 0x04;

constexpr uint8_t SGM_ADDR = 0x30;
constexpr uint8_t SGM_REG0 = 0x00;
constexpr uint8_t SGM_REG4 = 0x04;
constexpr uint8_t SGM_REG6 = 0x06;
constexpr uint8_t SGM_REG7 = 0x07;
constexpr uint8_t SGM_REG8 = 0x08;

template <typename T>
T clamp_byte(T value) {
    return std::clamp<T>(value, 0, 255);
}

bool equals_ignore_case(const std::string& lhs, const std::string& rhs) {
    if (lhs.size() != rhs.size()) {
        return false;
    }
    for (size_t i = 0; i < lhs.size(); ++i) {
        if (std::tolower(static_cast<unsigned char>(lhs[i])) !=
            std::tolower(static_cast<unsigned char>(rhs[i]))) {
            return false;
        }
    }
    return true;
}

}  // namespace

GroveRGBLCD::GroveRGBLCD(I2CBus& bus,
                         uint8_t text_addr,
                         bool text_only,
                         std::optional<uint8_t> forced_rgb_addr)
    : bus_(&bus),
      text_addr_(text_addr),
      backlight_type_(Backlight::None),
      backlight_addr_(0),
      cols_(16),
      rows_(2) {
    init_text();
    if (!text_only) {
        detect_backlight(forced_rgb_addr);
        if (backlight_available()) {
            set_color(255, 255, 255);
        }
    }
}

void GroveRGBLCD::init_text() {
    bus_->write_byte_data(text_addr_, LCD_CMD, CMD_FUNCTION_SET | FUNC_2LINE | FUNC_5x8);
    bus_->write_byte_data(text_addr_, LCD_CMD, CMD_DISPLAY_CONTROL | DISPLAY_ON | CURSOR_OFF | BLINK_OFF);
    clear();
    bus_->write_byte_data(text_addr_, LCD_CMD, CMD_ENTRY_MODE_SET | ENTRY_LEFT);
    std::this_thread::sleep_for(std::chrono::milliseconds(2));
}

void GroveRGBLCD::detect_backlight(std::optional<uint8_t> forced_rgb_addr) {
    auto probe = [&](uint8_t addr, uint8_t reg) -> bool {
        try {
            (void)bus_->read_byte_data(addr, reg);
            return true;
        } catch (const I2CError&) {
            return false;
        }
    };

    if (forced_rgb_addr.has_value()) {
        const uint8_t addr = forced_rgb_addr.value();
        if (probe(addr, SGM_REG0)) {
            backlight_type_ = Backlight::SGM31323;
            backlight_addr_ = addr;
            bus_->write_byte_data(addr, SGM_REG4, 0x3F);
            return;
        }
        if (probe(addr, PCA_MODE1)) {
            backlight_type_ = Backlight::PCA9633;
            backlight_addr_ = addr;
            bus_->write_byte_data(addr, PCA_MODE1, 0x00);
            bus_->write_byte_data(addr, PCA_MODE2, 0x20);
            bus_->write_byte_data(addr, PCA_LEDOUT, 0xAA);
            return;
        }
        backlight_type_ = Backlight::None;
        return;
    }

    if (probe(SGM_ADDR, SGM_REG0)) {
        backlight_type_ = Backlight::SGM31323;
        backlight_addr_ = SGM_ADDR;
        bus_->write_byte_data(SGM_ADDR, SGM_REG4, 0x3F);
        return;
    }

    for (uint8_t addr : PCA_ADDRS) {
        if (probe(addr, PCA_MODE1)) {
            try {
                bus_->write_byte_data(addr, PCA_MODE1, 0x00);
                bus_->write_byte_data(addr, PCA_MODE2, 0x20);
                bus_->write_byte_data(addr, PCA_LEDOUT, 0xAA);
                backlight_type_ = Backlight::PCA9633;
                backlight_addr_ = addr;
                return;
            } catch (const I2CError&) {
                continue;
            }
        }
    }

    backlight_type_ = Backlight::None;
}

void GroveRGBLCD::clear() {
    bus_->write_byte_data(text_addr_, LCD_CMD, CMD_CLEAR_DISPLAY);
    std::this_thread::sleep_for(std::chrono::milliseconds(2));
}

void GroveRGBLCD::home() {
    bus_->write_byte_data(text_addr_, LCD_CMD, CMD_RETURN_HOME);
    std::this_thread::sleep_for(std::chrono::milliseconds(2));
}

void GroveRGBLCD::set_cursor(uint8_t col, uint8_t row) {
    if (row >= rows_) {
        row = rows_ - 1;
    }
    const uint8_t addr = static_cast<uint8_t>(col + ROW_OFFSETS[row]);
    bus_->write_byte_data(text_addr_, LCD_CMD, CMD_SET_DDRAM_ADDR | addr);
}

void GroveRGBLCD::write(const std::string& text) {
    for (char ch : text) {
        bus_->write_byte_data(text_addr_, LCD_DATA, static_cast<uint8_t>(ch));
    }
}

void GroveRGBLCD::print_line(const std::string& text, uint8_t row) {
    set_cursor(0, row);
    std::string padded = text;
    if (padded.size() < cols_) {
        padded.append(cols_ - padded.size(), ' ');
    } else if (padded.size() > cols_) {
        padded = padded.substr(0, cols_);
    }
    write(padded);
}

void GroveRGBLCD::set_color(uint8_t r, uint8_t g, uint8_t b) {
    if (!backlight_available()) {
        return;
    }
    switch (backlight_type_) {
        case Backlight::PCA9633:
            set_color_pca(r, g, b);
            break;
        case Backlight::SGM31323:
            set_color_sgm(r, g, b);
            break;
        case Backlight::None:
        default:
            break;
    }
}

void GroveRGBLCD::set_color(const std::string& name) {
    static const std::map<std::string, std::array<uint8_t, 3>> colors = {
        {"red", {255, 0, 0}},
        {"green", {0, 255, 0}},
        {"blue", {0, 0, 255}},
        {"white", {255, 255, 255}},
        {"yellow", {255, 255, 0}},
        {"cyan", {0, 255, 255}},
        {"magenta", {255, 0, 255}},
        {"purple", {128, 0, 128}},
        {"orange", {255, 140, 0}},
        {"pink", {255, 105, 180}},
        {"off", {0, 0, 0}}
    };
    for (const auto& [key, rgb] : colors) {
        if (equals_ignore_case(name, key)) {
            set_color(rgb[0], rgb[1], rgb[2]);
            return;
        }
    }
    // Default fallback: treat as off when unknown
    set_color(0, 0, 0);
}

void GroveRGBLCD::set_color_pca(uint8_t r, uint8_t g, uint8_t b) {
    r = clamp_byte(r);
    g = clamp_byte(g);
    b = clamp_byte(b);
    bus_->write_byte_data(backlight_addr_, PCA_RED, r);
    bus_->write_byte_data(backlight_addr_, PCA_GREEN, g);
    bus_->write_byte_data(backlight_addr_, PCA_BLUE, b);
}

void GroveRGBLCD::set_color_sgm(uint8_t r, uint8_t g, uint8_t b) {
    r = clamp_byte(r);
    g = clamp_byte(g);
    b = clamp_byte(b);
    bus_->write_byte_data(backlight_addr_, SGM_REG6, r);
    bus_->write_byte_data(backlight_addr_, SGM_REG7, g);
    bus_->write_byte_data(backlight_addr_, SGM_REG8, b);
}

}  // namespace lilybot
