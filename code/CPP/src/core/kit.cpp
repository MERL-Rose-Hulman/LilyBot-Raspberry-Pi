#include "lilybot/core/kit.hpp"

#include <chrono>
#include <iostream>
#include <thread>

namespace lilybot {

KitComponent::KitComponent(std::string name)
    : name_(std::move(name)) {}

MotorComponent::MotorComponent(Robot& robot, KitDefaults defaults)
    : KitComponent("motors"),
      robot_(robot),
      defaults_(defaults) {}

bool MotorComponent::available() const noexcept {
    return robot_.motors_present();
}

void MotorComponent::stop() {
    if (!available()) {
        return;
    }
    robot_.motion().stop();
}

void MotorComponent::drive(double left_percent, double right_percent, double duration_seconds) {
    if (!available()) {
        throw std::runtime_error("Motor driver not available or not detected.");
    }
    if (duration_seconds < 0.0) {
        duration_seconds = defaults_.duration;
    }
    robot_.motion().drive(left_percent, right_percent);
    if (duration_seconds > 0.0) {
        std::this_thread::sleep_for(std::chrono::duration<double>(duration_seconds));
        robot_.motion().stop();
    }
}

void MotorComponent::forward(double speed, double duration) {
    if (!available()) {
        throw std::runtime_error("Motor driver not available or not detected.");
    }
    if (speed < 0.0) speed = defaults_.speed;
    if (duration < 0.0) duration = defaults_.duration;
    robot_.motion().forward(speed, duration);
}

void MotorComponent::backward(double speed, double duration) {
    if (!available()) {
        throw std::runtime_error("Motor driver not available or not detected.");
    }
    if (speed < 0.0) speed = defaults_.speed;
    if (duration < 0.0) duration = defaults_.duration;
    robot_.motion().backward(speed, duration);
}

void MotorComponent::pivot_left(double speed, double duration) {
    if (!available()) {
        throw std::runtime_error("Motor driver not available or not detected.");
    }
    if (speed < 0.0) speed = defaults_.speed;
    if (duration < 0.0) duration = defaults_.duration;
    robot_.motion().pivot_left(speed, duration);
}

void MotorComponent::pivot_right(double speed, double duration) {
    if (!available()) {
        throw std::runtime_error("Motor driver not available or not detected.");
    }
    if (speed < 0.0) speed = defaults_.speed;
    if (duration < 0.0) duration = defaults_.duration;
    robot_.motion().pivot_right(speed, duration);
}

void MotorComponent::turn_left(double speed, double duration, double inner_scale) {
    if (!available()) {
        throw std::runtime_error("Motor driver not available or not detected.");
    }
    if (speed < 0.0) speed = defaults_.speed;
    if (duration < 0.0) duration = defaults_.duration;
    if (inner_scale < 0.0) inner_scale = defaults_.inner_scale;
    robot_.motion().turn_left(speed, duration, inner_scale);
}

void MotorComponent::turn_right(double speed, double duration, double inner_scale) {
    if (!available()) {
        throw std::runtime_error("Motor driver not available or not detected.");
    }
    if (speed < 0.0) speed = defaults_.speed;
    if (duration < 0.0) duration = defaults_.duration;
    if (inner_scale < 0.0) inner_scale = defaults_.inner_scale;
    robot_.motion().turn_right(speed, duration, inner_scale);
}

void MotorComponent::close() {
    stop();
}

DisplayComponent::DisplayComponent(Robot& robot)
    : KitComponent("display"),
      robot_(robot) {}

bool DisplayComponent::available() const noexcept {
    return robot_.display_present();
}

void DisplayComponent::write(const std::string& text) {
    if (!available()) return;
    robot_.display().write(text);
}

void DisplayComponent::set_lines(const std::string& line1, const std::string& line2) {
    if (!available()) return;
    robot_.display().set_lines(line1, line2);
}

void DisplayComponent::set_color(const std::string& name) {
    if (!available()) return;
    robot_.display().set_color(name);
}

void DisplayComponent::set_color(uint8_t r, uint8_t g, uint8_t b) {
    if (!available()) return;
    robot_.display().set_color(r, g, b);
}

void DisplayComponent::show_distance(std::optional<double> distance) {
    if (!available()) return;
    robot_.display().show_distance(distance, "Distance");
}

DistanceComponent::DistanceComponent(Robot& robot)
    : KitComponent("distance"),
      robot_(robot) {}

bool DistanceComponent::available() const noexcept {
    return robot_.distance_present();
}

std::optional<double> DistanceComponent::read() {
    if (!available()) {
        return std::nullopt;
    }
    return robot_.distance().read();
}

std::optional<double> DistanceComponent::read_and_display(DisplayComponent* display) {
    auto distance = read();
    if (display && display->available()) {
        display->show_distance(distance);
    }
    return distance;
}

LilyBotKit::LilyBotKit(const RobotOptions& options, KitDefaults defaults)
    : robot_(options),
      defaults_(defaults),
      motors_(std::make_unique<MotorComponent>(robot_, defaults_)),
      display_(std::make_unique<DisplayComponent>(robot_)),
      distance_(std::make_unique<DistanceComponent>(robot_)) {}

LilyBotKit::~LilyBotKit() {
    try {
        close();
    } catch (...) {
    }
}

void LilyBotKit::run_actions(const std::vector<ActionSpec>& actions,
                             std::optional<double> default_speed,
                             std::optional<double> default_duration,
                             std::optional<double> default_inner_scale,
                             std::optional<double> pause) {
    ActionRunner runner(robot_, defaults_);
    runner.run(actions, default_speed, default_duration, default_inner_scale, pause);
}

void LilyBotKit::run_prebuilt_demo() {
    std::vector<ActionSpec> demo = {
        {"forward", {defaults_.speed, defaults_.duration}},
        {"backward", {defaults_.speed, defaults_.duration}},
        {"pivot_left", {defaults_.speed, defaults_.duration}},
        {"pivot_right", {defaults_.speed, defaults_.duration}},
        {"turn_left", {defaults_.speed, defaults_.duration, defaults_.inner_scale}},
        {"turn_right", {defaults_.speed, defaults_.duration, defaults_.inner_scale}},
    };
    run_actions(demo);
}

void LilyBotKit::close() {
    if (distance_) {
        distance_->close();
    }
    if (display_) {
        display_->close();
    }
    if (motors_) {
        motors_->close();
    }
    robot_.close();
}

}  // namespace lilybot
