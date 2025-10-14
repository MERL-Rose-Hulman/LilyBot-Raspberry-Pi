#include "lilybot/core/kit.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

using lilybot::ActionSpec;
using lilybot::KitDefaults;
using lilybot::LilyBotKit;
using lilybot::RobotOptions;

namespace {

struct CliOptions {
    std::string driver{"drv8830"};
    int bus{1};
    int sonar_pin{5};
    uint8_t drv_left{0x65};
    uint8_t drv_right{0x60};
    uint8_t tb6612_addr{0x14};
    KitDefaults defaults{};
    bool use_grove_hat{false};
};

void print_usage(const char* program) {
    std::cout << "Usage: " << program << " [options]\n"
              << "Options:\n"
              << "  --driver <drv8830|tb6612>   Motor driver type (default: drv8830)\n"
              << "  --bus <id>                  I2C bus number (default: 1)\n"
              << "  --sonar-pin <pin>           GPIO pin for ultrasonic sensor (default: 5)\n"
              << "  --drv-left <addr>           I2C address for left DRV8830 (default: 0x65)\n"
              << "  --drv-right <addr>          I2C address for right DRV8830 (default: 0x60)\n"
              << "  --tb6612-addr <addr>        I2C address for TB6612 driver (default: 0x14)\n"
              << "  --use-grove-hat             Route GPIO/ultrasonic via Grove Base Hat\n"
              << "  --speed <percent>           Default speed percentage (default: 60)\n"
              << "  --duration <seconds>        Default duration seconds (default: 1.2)\n"
              << "  --inner-scale <factor>      Default inner wheel scale (default: 0.4)\n"
              << "  --pause <seconds>           Pause between actions (default: 0.5)\n"
              << "  --help                      Show this help message\n";
}

uint8_t parse_hex(const std::string& value) {
    return static_cast<uint8_t>(std::strtoul(value.c_str(), nullptr, 0));
}

CliOptions parse_args(int argc, char** argv) {
    CliOptions opts;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto require_value = [&](const std::string& flag) -> std::string {
            if (i + 1 >= argc) {
                throw std::invalid_argument("Missing value for " + flag);
            }
            return argv[++i];
        };

        if (arg == "--driver") {
            opts.driver = require_value(arg);
        } else if (arg == "--bus") {
            opts.bus = std::stoi(require_value(arg));
        } else if (arg == "--sonar-pin") {
            opts.sonar_pin = std::stoi(require_value(arg));
        } else if (arg == "--drv-left") {
            opts.drv_left = parse_hex(require_value(arg));
        } else if (arg == "--drv-right") {
            opts.drv_right = parse_hex(require_value(arg));
        } else if (arg == "--tb6612-addr") {
            opts.tb6612_addr = parse_hex(require_value(arg));
        } else if (arg == "--use-grove-hat") {
            opts.use_grove_hat = true;
        } else if (arg == "--speed") {
            opts.defaults.speed = std::stod(require_value(arg));
        } else if (arg == "--duration") {
            opts.defaults.duration = std::stod(require_value(arg));
        } else if (arg == "--inner-scale") {
            opts.defaults.inner_scale = std::stod(require_value(arg));
        } else if (arg == "--pause") {
            opts.defaults.pause = std::stod(require_value(arg));
        } else if (arg == "--help") {
            print_usage(argv[0]);
            std::exit(0);
        } else {
            throw std::invalid_argument("Unknown option: " + arg);
        }
    }
    return opts;
}

void show_header(LilyBotKit& kit) {
    std::cout << "=== LilyBot C++ Intro Demo ===\n";
    auto& display = kit.display();
    if (display.available()) {
        display.set_lines("Hello LilyBot!", "C++ control ready");
        std::this_thread::sleep_for(std::chrono::milliseconds(1500));
        display.set_lines("Ready to move", "Watch the wheels");
    } else {
        std::cout << "[info] LCD not available; console messages only.\n";
    }
}

void demo_motions(LilyBotKit& kit) {
    auto& motors = kit.motors();
    if (!motors.available()) {
        std::cout << "[warn] Motor driver not detected; skipping motion demo.\n";
        return;
    }

    std::cout << "→ Forward\n";
    motors.forward();

    std::cout << "→ Backward\n";
    motors.backward();

    std::cout << "→ Pivot left\n";
    motors.pivot_left();

    std::cout << "→ Pivot right\n";
    motors.pivot_right();

    std::cout << "→ Turn left with inner scaling\n";
    motors.turn_left(-1.0, -1.0, 0.5);

    std::cout << "→ Turn right with inner scaling\n";
    motors.turn_right(-1.0, -1.0, 0.5);

    std::cout << "→ Differential drive (left fwd, right rev)\n";
    motors.drive(60, -60, 1.0);

    std::cout << "→ Stop\n";
    motors.stop();
}

void demo_actions(LilyBotKit& kit) {
    std::vector<ActionSpec> script = {
        {"forward", {70, 1.2}},
        {"pivot_left", {60, 1.0}},
        {"distance", {}},
        {"drive", {50, -50, 0.8}},
        {"stop", {}},
    };
    std::cout << "→ Executing scripted actions\n";
    kit.run_actions(script);
}

}  // namespace

int main(int argc, char** argv) {
    try {
        CliOptions cli = parse_args(argc, argv);
        RobotOptions options;
        options.driver = cli.driver;
        options.bus_id = cli.bus;
        options.sonar_pin = cli.sonar_pin;
        options.drv8830_left_address = cli.drv_left;
        options.drv8830_right_address = cli.drv_right;
        options.tb6612_address = cli.tb6612_addr;
        options.use_grove_hat = cli.use_grove_hat;

        std::cout << "Initialising LilyBot (C++) – ensure power and sensors are connected…\n";
        LilyBotKit kit(options, cli.defaults);

        show_header(kit);

        auto& distance = kit.distance();
        auto& display = kit.display();
        auto start_distance = distance.read_and_display(display.available() ? &display : nullptr);
        if (start_distance.has_value()) {
            std::cout << "[start] Distance = " << start_distance.value() << " cm\n";
        } else {
            std::cout << "[start] Distance unavailable.\n";
        }

        demo_motions(kit);

        auto end_distance = distance.read_and_display(display.available() ? &display : nullptr);
        if (end_distance.has_value()) {
            std::cout << "[end] Distance = " << end_distance.value() << " cm\n";
        } else {
            std::cout << "[end] Distance unavailable.\n";
        }

        demo_actions(kit);

        if (display.available()) {
            display.set_lines("Lesson", "Completed");
        }

        std::cout << "Demo finished – tweak parameters or add new actions!\n";
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << "[error] " << exc.what() << "\n";
        return 1;
    }
}
