#include "lilybot/core/robot.hpp"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <cmath>
#include <iostream>
#include <thread>

namespace lilybot {

namespace {

double clamp_percent(double value) {
    if (value < -100.0) {
        return -100.0;
    }
    if (value > 100.0) {
        return 100.0;
    }
    return value;
}

std::string to_lower(const std::string& input) {
    std::string result = input;
    std::transform(result.begin(), result.end(), result.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return result;
}

const std::vector<std::string>& action_names() {
    static const std::vector<std::string> names = {
        "forward",
        "backward",
        "pivot_left",
        "pivot_right",
        "turn_left",
        "turn_right",
        "drive",
        "stop",
        "distance",
    };
    return names;
}

}  // namespace

// ---------------------------------------------------------------------------
// MotionSystem

MotionSystem::MotionSystem(std::unique_ptr<TB6612Controller> tb6612)
    : tb6612_(std::move(tb6612)) {}

MotionSystem::MotionSystem(std::unique_ptr<DRV8830> left, std::unique_ptr<DRV8830> right)
    : drv_left_(std::move(left)),
      drv_right_(std::move(right)) {}

bool MotionSystem::available() const noexcept {
    return static_cast<bool>(tb6612_) || (drv_left_ && drv_right_);
}

void MotionSystem::drive(double left_percent, double right_percent) {
    if (!available()) {
        return;
    }
    left_percent = clamp_percent(left_percent);
    right_percent = clamp_percent(right_percent);

    if (tb6612_) {
        const int left_val = static_cast<int>(std::round(left_percent * 255.0 / 100.0));
        const int right_val = static_cast<int>(std::round(right_percent * 255.0 / 100.0));
        tb6612_->run(TB6612Controller::Channel::A, left_val);
        tb6612_->run(TB6612Controller::Channel::B, right_val);
    } else if (drv_left_ && drv_right_) {
        const int left_val = static_cast<int>(std::round(left_percent));
        const int right_val = static_cast<int>(std::round(right_percent));
        drv_left_->set_speed(left_val);
        drv_right_->set_speed(right_val);
    }
}

void MotionSystem::stop() {
    if (!available()) {
        return;
    }
    if (tb6612_) {
        tb6612_->stop_all();
    } else {
        drv_left_->stop();
        drv_right_->stop();
    }
}

void MotionSystem::timed_drive(double left_percent, double right_percent, double duration_seconds) {
    drive(left_percent, right_percent);
    if (duration_seconds > 0.0) {
        std::this_thread::sleep_for(std::chrono::duration<double>(duration_seconds));
        stop();
    }
}

void MotionSystem::forward(double speed_percent, double duration_seconds) {
    timed_drive(speed_percent, speed_percent, duration_seconds);
}

void MotionSystem::backward(double speed_percent, double duration_seconds) {
    timed_drive(-speed_percent, -speed_percent, duration_seconds);
}

void MotionSystem::pivot_left(double speed_percent, double duration_seconds) {
    timed_drive(-speed_percent, speed_percent, duration_seconds);
}

void MotionSystem::pivot_right(double speed_percent, double duration_seconds) {
    timed_drive(speed_percent, -speed_percent, duration_seconds);
}

void MotionSystem::turn_left(double speed_percent, double duration_seconds, double inner_scale) {
    timed_drive(speed_percent * inner_scale, speed_percent, duration_seconds);
}

void MotionSystem::turn_right(double speed_percent, double duration_seconds, double inner_scale) {
    timed_drive(speed_percent, speed_percent * inner_scale, duration_seconds);
}

void MotionSystem::close() {
    try {
        stop();
    } catch (...) {
        // Swallow exceptions during shutdown.
    }
}

// ---------------------------------------------------------------------------
// DisplaySystem

DisplaySystem::DisplaySystem(std::unique_ptr<GroveRGBLCD> lcd)
    : lcd_(std::move(lcd)) {}

void DisplaySystem::write(const std::string& text) {
    if (!lcd_) {
        return;
    }
    lcd_->write(text);
}

void DisplaySystem::set_lines(const std::string& line1, const std::string& line2) {
    if (!lcd_) {
        return;
    }
    lcd_->clear();
    lcd_->print_line(line1, 0);
    if (!line2.empty() && lcd_->rows() > 1) {
        lcd_->print_line(line2, 1);
    }
}

void DisplaySystem::set_color(const std::string& name) {
    if (!lcd_) {
        return;
    }
    lcd_->set_color(name);
}

void DisplaySystem::set_color(uint8_t r, uint8_t g, uint8_t b) {
    if (!lcd_) {
        return;
    }
    lcd_->set_color(r, g, b);
}

void DisplaySystem::show_distance(std::optional<double> distance_cm, const std::string& status) {
    if (!lcd_) {
        return;
    }
    std::string line1;
    if (distance_cm.has_value()) {
        line1 = "Dist: " + std::to_string(static_cast<double>(std::round(distance_cm.value() * 10.0) / 10.0)) + " cm";
    } else {
        line1 = "Dist: ----";
    }
    lcd_->clear();
    lcd_->print_line(line1, 0);
    if (!status.empty() && lcd_->rows() > 1) {
        lcd_->print_line(status.substr(0, lcd_->columns()), 1);
    }
}

void DisplaySystem::close() {
    lcd_.reset();
}

// ---------------------------------------------------------------------------
// DistanceSensor

DistanceSensor::DistanceSensor(std::unique_ptr<UltrasonicSensor> sensor)
    : sensor_(std::move(sensor)) {}

DistanceSensor::DistanceSensor(std::unique_ptr<HatUltrasonicSensor> sensor)
    : hat_sensor_(std::move(sensor)) {}

std::optional<double> DistanceSensor::read() {
    if (sensor_) {
        auto reading = sensor_->read_distance_cm();
        if (!reading.has_value()) {
            return std::nullopt;
        }
        return static_cast<double>(reading.value());
    }
    if (hat_sensor_) {
        auto reading = hat_sensor_->read_distance_cm();
        if (!reading.has_value()) {
            return std::nullopt;
        }
        return static_cast<double>(reading.value());
    }
    return std::nullopt;
}

// ---------------------------------------------------------------------------
// Robot

Robot::Robot(const RobotOptions& options)
    : bus_(options.bus_id),
      motion_(),
      display_(),
      distance_() {
    if (options.use_grove_hat) {
        try {
            grove_hat_ = std::make_unique<GroveHat>(bus_);
        } catch (const std::exception& exc) {
            std::cerr << "[warn] Grove Base Hat init failed (" << exc.what() << "); falling back to sysfs GPIO\n";
        }
    }
    // Display ----------------------------------------------------------------
    std::unique_ptr<GroveRGBLCD> lcd;
    try {
        lcd = std::make_unique<GroveRGBLCD>(bus_);
    } catch (const std::exception& exc) {
        std::cerr << "[warn] LCD init failed (" << exc.what() << "); continuing without LCD\n";
    }
    display_ = DisplaySystem(std::move(lcd));

    // Distance sensor --------------------------------------------------------
    bool distance_assigned = false;
    if (options.sonar_pin >= 0) {
        if (grove_hat_) {
            try {
                auto hat_sensor = std::make_unique<HatUltrasonicSensor>(*grove_hat_, static_cast<uint8_t>(options.sonar_pin));
                distance_ = DistanceSensor(std::move(hat_sensor));
                distance_assigned = true;
            } catch (const std::exception& exc) {
                std::cerr << "[warn] Ultrasonic init via Grove Hat failed (" << exc.what() << "); distance disabled\n";
            }
        }
        if (!distance_assigned) {
            try {
                auto sensor = std::make_unique<UltrasonicSensor>(options.sonar_pin);
                distance_ = DistanceSensor(std::move(sensor));
                distance_assigned = true;
            } catch (const std::exception& exc) {
                std::cerr << "[warn] Ultrasonic init failed (" << exc.what() << "); distance disabled\n";
            }
        }
    } else {
        std::cerr << "[warn] sonar_pin not provided; distance sensor disabled\n";
    }

    // Motors -----------------------------------------------------------------
    if (to_lower(options.driver) == "tb6612") {
        try {
            auto controller = std::make_unique<TB6612Controller>(bus_, options.tb6612_address);
            motion_ = MotionSystem(std::move(controller));
        } catch (const std::exception& exc) {
            std::cerr << "[warn] TB6612 controller unavailable (" << exc.what()
                      << "); motors disabled\n";
            motion_ = MotionSystem();
        }
    } else if (to_lower(options.driver) == "drv8830") {
        try {
            auto left = std::make_unique<DRV8830>(bus_, options.drv8830_left_address);
            auto right = std::make_unique<DRV8830>(bus_, options.drv8830_right_address);
            motion_ = MotionSystem(std::move(left), std::move(right));
        } catch (const std::exception& exc) {
            std::cerr << "[warn] DRV8830 drivers unavailable (" << exc.what()
                      << "); motors disabled\n";
            motion_ = MotionSystem();
        }
    } else {
        throw std::invalid_argument("Unsupported driver: " + options.driver);
    }
}

Robot::~Robot() {
    try {
        close();
    } catch (...) {
        // destructor should not throw
    }
}

void Robot::close() {
    motion_.close();
    display_.close();
}

// ---------------------------------------------------------------------------
// ActionRunner

ActionRunner::ActionRunner(Robot& robot, ActionDefaults defaults)
    : robot_(robot),
      defaults_(defaults) {}

void ActionRunner::run(const std::vector<ActionSpec>& actions,
                       std::optional<double> default_speed,
                       std::optional<double> default_duration,
                       std::optional<double> default_inner_scale,
                       std::optional<double> pause) {
    if (actions.empty()) {
        return;
    }

    ActionDefaults effective = defaults_;
    if (default_speed.has_value()) {
        effective.speed = default_speed.value();
    }
    if (default_duration.has_value()) {
        effective.duration = default_duration.value();
    }
    if (default_inner_scale.has_value()) {
        effective.inner_scale = default_inner_scale.value();
    }
    if (pause.has_value()) {
        effective.pause = pause.value();
    }

    if (!robot_.motors_present()) {
        std::cerr << "[warn] Motors not available; movement actions will be skipped\n";
    }

    for (const auto& action : actions) {
        const std::string name = to_lower(action.name);
        if (std::find(action_names().begin(), action_names().end(), name) == action_names().end()) {
            throw std::invalid_argument("Unsupported action '" + action.name + "'");
        }

        if (name == "distance") {
            auto distance = robot_.distance().read();
            robot_.display().show_distance(distance, "Distance");
            if (distance.has_value()) {
                std::cout << "[distance] " << distance.value() << " cm\n";
            } else {
                std::cout << "[distance] ----\n";
            }
        } else {
            std::string label = action.name;
            auto distance = robot_.distance().read();
            robot_.display().show_distance(distance, label);
            if (distance.has_value()) {
                std::cout << "[" << name << "] distance=" << distance.value() << " cm\n";
            } else {
                std::cout << "[" << name << "] distance=----\n";
            }
            perform_motion(name, action.params, effective);
        }

        if (effective.pause > 0.0) {
            std::this_thread::sleep_for(std::chrono::duration<double>(effective.pause));
        }
    }
}

const std::vector<std::string>& ActionRunner::available_actions() {
    return action_names();
}

void ActionRunner::perform_motion(const std::string& name,
                                  const std::vector<double>& params,
                                  const ActionDefaults& defaults) {
    auto& motion = robot_.motion();
    if (!motion.available()) {
        return;
    }

    auto param = [&](size_t index, double fallback) -> double {
        return (index < params.size()) ? params[index] : fallback;
    };

    if (name == "forward") {
        double speed = param(0, defaults.speed);
        double duration = param(1, defaults.duration);
        std::cout << "[forward] speed=" << speed << "% duration=" << duration << "s\n";
        motion.forward(speed, duration);
    } else if (name == "backward") {
        double speed = param(0, defaults.speed);
        double duration = param(1, defaults.duration);
        std::cout << "[backward] speed=" << speed << "% duration=" << duration << "s\n";
        motion.backward(speed, duration);
    } else if (name == "pivot_left") {
        double speed = param(0, defaults.speed);
        double duration = param(1, defaults.duration);
        std::cout << "[pivot_left] speed=" << speed << "% duration=" << duration << "s\n";
        motion.pivot_left(speed, duration);
    } else if (name == "pivot_right") {
        double speed = param(0, defaults.speed);
        double duration = param(1, defaults.duration);
        std::cout << "[pivot_right] speed=" << speed << "% duration=" << duration << "s\n";
        motion.pivot_right(speed, duration);
    } else if (name == "turn_left") {
        double speed = param(0, defaults.speed);
        double duration = param(1, defaults.duration);
        double inner = param(2, defaults.inner_scale);
        std::cout << "[turn_left] speed=" << speed << "% duration=" << duration << "s inner=" << inner << "\n";
        motion.turn_left(speed, duration, inner);
    } else if (name == "turn_right") {
        double speed = param(0, defaults.speed);
        double duration = param(1, defaults.duration);
        double inner = param(2, defaults.inner_scale);
        std::cout << "[turn_right] speed=" << speed << "% duration=" << duration << "s inner=" << inner << "\n";
        motion.turn_right(speed, duration, inner);
    } else if (name == "drive") {
        double left = param(0, defaults.speed);
        double right = param(1, defaults.speed);
        double duration = param(2, defaults.duration);
        std::cout << "[drive] left=" << left << "% right=" << right << "% duration=" << duration << "s\n";
        motion.timed_drive(left, right, duration);
    } else if (name == "stop") {
        std::cout << "[stop]\n";
        motion.stop();
    } else {
        throw std::invalid_argument("Unhandled action '" + name + "'");
    }
}

}  // namespace lilybot
