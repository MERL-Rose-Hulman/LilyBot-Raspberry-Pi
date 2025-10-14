#pragma once

#include "lilybot/core/robot.hpp"

#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

namespace lilybot {

struct KitDefaults : public ActionDefaults {
    KitDefaults() = default;
    KitDefaults(double speed, double duration, double inner_scale, double pause) {
        this->speed = speed;
        this->duration = duration;
        this->inner_scale = inner_scale;
        this->pause = pause;
    }
};

class KitComponent {
public:
    explicit KitComponent(std::string name);
    virtual ~KitComponent() = default;

    const std::string& name() const noexcept { return name_; }
    virtual bool available() const noexcept { return true; }
    virtual void close() {}

private:
    std::string name_;
};

class MotorComponent : public KitComponent {
public:
    MotorComponent(Robot& robot, KitDefaults defaults);

    bool available() const noexcept override;

    void stop();
    void drive(double left_percent, double right_percent, double duration_seconds = -1.0);
    void forward(double speed = -1.0, double duration = -1.0);
    void backward(double speed = -1.0, double duration = -1.0);
    void pivot_left(double speed = -1.0, double duration = -1.0);
    void pivot_right(double speed = -1.0, double duration = -1.0);
    void turn_left(double speed = -1.0, double duration = -1.0, double inner_scale = -1.0);
    void turn_right(double speed = -1.0, double duration = -1.0, double inner_scale = -1.0);
    void close() override;

private:
    Robot& robot_;
    KitDefaults defaults_;
};

class DisplayComponent : public KitComponent {
public:
    explicit DisplayComponent(Robot& robot);

    bool available() const noexcept override;
    void write(const std::string& text);
    void set_lines(const std::string& line1, const std::string& line2 = "");
    void set_color(const std::string& name);
    void set_color(uint8_t r, uint8_t g, uint8_t b);
    void show_distance(std::optional<double> distance);

private:
    Robot& robot_;
};

class DistanceComponent : public KitComponent {
public:
    explicit DistanceComponent(Robot& robot);

    bool available() const noexcept override;
    std::optional<double> read();
    std::optional<double> read_and_display(DisplayComponent* display = nullptr);

private:
    Robot& robot_;
};

class LilyBotKit {
public:
    LilyBotKit(const RobotOptions& options, KitDefaults defaults = KitDefaults{});
    ~LilyBotKit();

    Robot& robot() { return robot_; }
    MotorComponent& motors() { return *motors_; }
    DisplayComponent& display() { return *display_; }
    DistanceComponent& distance() { return *distance_; }

    void run_actions(const std::vector<ActionSpec>& actions,
                     std::optional<double> default_speed = std::nullopt,
                     std::optional<double> default_duration = std::nullopt,
                     std::optional<double> default_inner_scale = std::nullopt,
                     std::optional<double> pause = std::nullopt);

    void run_prebuilt_demo();

    void close();

private:
    Robot robot_;
    KitDefaults defaults_;
    std::unique_ptr<MotorComponent> motors_;
    std::unique_ptr<DisplayComponent> display_;
    std::unique_ptr<DistanceComponent> distance_;
};

}  // namespace lilybot
