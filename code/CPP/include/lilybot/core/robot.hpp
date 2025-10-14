#pragma once

#include "lilybot/drivers/drv8830.hpp"
#include "lilybot/hal/i2c_bus.hpp"
#include "lilybot/peripherals/lcd.hpp"
#include "lilybot/drivers/tb6612.hpp"
#include "lilybot/peripherals/ultrasonic.hpp"

#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace lilybot {

struct ActionDefaults {
    double speed{60.0};
    double duration{1.2};
    double inner_scale{0.4};
    double pause{0.5};
};

struct ActionSpec {
    std::string name;
    std::vector<double> params;
};

class MotionSystem {
public:
    MotionSystem() = default;
    explicit MotionSystem(std::unique_ptr<TB6612Controller> tb6612);
    MotionSystem(std::unique_ptr<DRV8830> left, std::unique_ptr<DRV8830> right);

    bool available() const noexcept;
    void drive(double left_percent, double right_percent);
    void stop();
    void timed_drive(double left_percent, double right_percent, double duration_seconds);
    void forward(double speed_percent, double duration_seconds);
    void backward(double speed_percent, double duration_seconds);
    void pivot_left(double speed_percent, double duration_seconds);
    void pivot_right(double speed_percent, double duration_seconds);
    void turn_left(double speed_percent, double duration_seconds, double inner_scale);
    void turn_right(double speed_percent, double duration_seconds, double inner_scale);
    void close();

private:
    std::unique_ptr<TB6612Controller> tb6612_;
    std::unique_ptr<DRV8830> drv_left_;
    std::unique_ptr<DRV8830> drv_right_;
};

class DisplaySystem {
public:
    DisplaySystem() = default;
    explicit DisplaySystem(std::unique_ptr<GroveRGBLCD> lcd);

    bool available() const noexcept { return static_cast<bool>(lcd_); }
    void write(const std::string& text);
    void set_lines(const std::string& line1, const std::string& line2 = "");
    void set_color(const std::string& name);
    void set_color(uint8_t r, uint8_t g, uint8_t b);
    void show_distance(std::optional<double> distance_cm, const std::string& status = "Distance");
    void close();

private:
    std::unique_ptr<GroveRGBLCD> lcd_;
};

class DistanceSensor {
public:
    DistanceSensor() = default;
    explicit DistanceSensor(std::unique_ptr<UltrasonicSensor> sensor);

    bool available() const noexcept { return static_cast<bool>(sensor_); }
    std::optional<double> read();

private:
    std::unique_ptr<UltrasonicSensor> sensor_;
};

struct RobotOptions {
    std::string driver{"tb6612"};
    int bus_id{1};
    int sonar_pin{-1};
    uint8_t tb6612_address{0x14};
    uint8_t drv8830_left_address{0x60};
    uint8_t drv8830_right_address{0x61};
};

class Robot {
public:
    explicit Robot(const RobotOptions& options);
    ~Robot();

    MotionSystem& motion() { return motion_; }
    DisplaySystem& display() { return display_; }
    DistanceSensor& distance() { return distance_; }

    bool motors_present() const noexcept { return motion_.available(); }
    bool display_present() const noexcept { return display_.available(); }
    bool distance_present() const noexcept { return distance_.available(); }

    void close();

private:
    I2CBus bus_;
    MotionSystem motion_;
    DisplaySystem display_;
    DistanceSensor distance_;
};

class ActionRunner {
public:
    explicit ActionRunner(Robot& robot, ActionDefaults defaults = ActionDefaults{});

    void run(const std::vector<ActionSpec>& actions,
             std::optional<double> default_speed = std::nullopt,
             std::optional<double> default_duration = std::nullopt,
             std::optional<double> default_inner_scale = std::nullopt,
             std::optional<double> pause = std::nullopt);

    static const std::vector<std::string>& available_actions();

private:
    void perform_motion(const std::string& name,
                        const std::vector<double>& params,
                        const ActionDefaults& defaults);

    Robot& robot_;
    ActionDefaults defaults_;
};

}  // namespace lilybot
