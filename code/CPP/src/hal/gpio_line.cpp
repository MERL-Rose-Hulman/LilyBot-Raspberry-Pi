#include "lilybot/hal/gpio_line.hpp"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

namespace lilybot {

namespace {

[[noreturn]] void throw_errno(const std::string& context) {
    throw GpioError(context + ": " + std::strerror(errno));
}

bool path_exists(const std::string& path) {
    struct stat st;
    return ::stat(path.c_str(), &st) == 0;
}

}  // namespace

GpioLine::GpioLine(int pin, bool active_low)
    : pin_(pin),
      value_fd_(-1),
      active_low_(active_low),
      exported_(false) {
    export_pin();
    const std::string gpio_path = "/sys/class/gpio/gpio" + std::to_string(pin_);
    if (active_low_) {
        write_file(gpio_path + "/active_low", "1");
    }
    value_fd_ = ::open((gpio_path + "/value").c_str(), O_RDWR);
    if (value_fd_ < 0) {
        throw_errno("Failed to open GPIO value for pin " + std::to_string(pin_));
    }
}

GpioLine::GpioLine(GpioLine&& other) noexcept
    : pin_(other.pin_),
      value_fd_(other.value_fd_),
      active_low_(other.active_low_),
      exported_(other.exported_) {
    other.value_fd_ = -1;
    other.exported_ = false;
}

GpioLine& GpioLine::operator=(GpioLine&& other) noexcept {
    if (this != &other) {
        if (value_fd_ >= 0) {
            ::close(value_fd_);
        }
        if (exported_) {
            unexport_pin();
        }
        pin_ = other.pin_;
        value_fd_ = other.value_fd_;
        active_low_ = other.active_low_;
        exported_ = other.exported_;
        other.value_fd_ = -1;
        other.exported_ = false;
    }
    return *this;
}

GpioLine::~GpioLine() {
    if (value_fd_ >= 0) {
        ::close(value_fd_);
    }
    if (exported_) {
        try {
            unexport_pin();
        } catch (...) {
            // Destructors should not throw.
        }
    }
}

void GpioLine::ensure_open() {
    if (value_fd_ < 0) {
        throw GpioError("GPIO value file is not open");
    }
}

void GpioLine::export_pin() {
    const std::string gpio_path = "/sys/class/gpio/gpio" + std::to_string(pin_);
    if (!path_exists(gpio_path)) {
        write_file("/sys/class/gpio/export", std::to_string(pin_));
    }
    exported_ = true;
}

void GpioLine::unexport_pin() {
    write_file("/sys/class/gpio/unexport", std::to_string(pin_));
    exported_ = false;
}

void GpioLine::write_file(const std::string& path, const std::string& value) {
    int fd = ::open(path.c_str(), O_WRONLY);
    if (fd < 0) {
        throw_errno("Failed to open " + path);
    }
    ssize_t written = ::write(fd, value.c_str(), value.size());
    int saved_errno = errno;
    ::close(fd);
    if (written < 0 || static_cast<size_t>(written) != value.size()) {
        errno = saved_errno;
        throw_errno("Failed to write to " + path);
    }
}

void GpioLine::set_direction(Direction dir) {
    const std::string gpio_path = "/sys/class/gpio/gpio" + std::to_string(pin_);
    const std::string dir_str = (dir == Direction::Out) ? "out" : "in";
    write_file(gpio_path + "/direction", dir_str);
}

void GpioLine::write(bool value) {
    ensure_open();
    const bool out = active_low_ ? !value : value;
    const char ch = out ? '1' : '0';
    if (::lseek(value_fd_, 0, SEEK_SET) < 0) {
        throw_errno("Failed to seek GPIO value for pin " + std::to_string(pin_));
    }
    if (::write(value_fd_, &ch, 1) != 1) {
        throw_errno("Failed to write GPIO value for pin " + std::to_string(pin_));
    }
}

bool GpioLine::read() {
    ensure_open();
    if (::lseek(value_fd_, 0, SEEK_SET) < 0) {
        throw_errno("Failed to seek GPIO value for pin " + std::to_string(pin_));
    }
    char ch = 0;
    if (::read(value_fd_, &ch, 1) != 1) {
        throw_errno("Failed to read GPIO value for pin " + std::to_string(pin_));
    }
    bool raw = (ch != '0');
    return active_low_ ? !raw : raw;
}

}  // namespace lilybot
