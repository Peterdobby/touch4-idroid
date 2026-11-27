// Settings, with the screens of Espressif's phone example (Apache-2.0) and the
// platform's bt-audio behind them. Only Bluetooth is offered so far.
#pragma once

#include <stdio.h>
#include <string>
#include <vector>
#include "esp_brookesia.hpp"

class AppSettings: public ESP_Brookesia_PhoneApp {
public:
    AppSettings();

    bool run(void) override;
    bool back(void) override;
    bool close(void) override;

private:
    struct Device {
        std::string address, name;
    };

    void layout(void);
    void start(const std::string &action);
    void poll(void);
    void parse(void);
    void show(void);
    void addHeader(const char *text);
    void addDevice(const Device &device, bool paired);
    void ask(const Device &device, bool paired);

    static void onTimer(lv_timer_t *timer);
    static void onDevice(lv_event_t *e);
    static void onSearch(lv_event_t *e);
    static void onPower(lv_event_t *e);
    static void onChoice(lv_event_t *e);
    static void onBoxDeleted(lv_event_t *e);

    // a running bt-audio command; it outlives the app if closed meanwhile
    FILE *_command = nullptr;
    std::string _output, _action, _message, _connected, _chosen;
    std::vector<Device> _paired, _nearby;
    bool _powered = false, _open = false;
    lv_timer_t *_timer = nullptr;
    lv_obj_t *_status = nullptr, *_box = nullptr;
};
