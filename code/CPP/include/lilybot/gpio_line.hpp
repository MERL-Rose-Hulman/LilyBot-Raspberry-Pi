#pragma once

#include <string>
#include <stdexcept>

namespace lilybot {

class GpioError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class GpioLine {
public:
    enum class Direction { In, Out };

    explicit GpioLine(int pin, bool active_low = false);
    GpioLine(const GpioLine&) = delete;
    GpioLine& operator=(const GpioLine&) = delete;
    GpioLine(GpioLine&& other) noexcept;
    GpioLine& operator=(GpioLine&& other) noexcept;
    ~GpioLine();

    void set_direction(Direction dir);
    void write(bool value);
    bool read();

    int pin() const noexcept { return pin_; }

private:
    void ensure_open();
    void export_pin();
    void unexport_pin();
    void write_file(const std::string& path, const std::string& value);

    int pin_;
    int value_fd_;
    bool active_low_;
    bool exported_;
};

}  // namespace lilybot
