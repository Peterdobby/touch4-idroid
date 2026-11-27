#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "Setting.hpp"
#include "ui.h"

LV_IMG_DECLARE(img_app_setting);

#define FONT        &lv_font_montserrat_30
#define SMALL       &lv_font_montserrat_24
#define ROW_COLOR   lv_color_hex(0x1c1c1c)
#define PRESSED     lv_color_hex(0x404040)
#define GREY        lv_color_hex(0x909090)
#define ROW_HEIGHT  84
#define WIDTH       600

AppSettings::AppSettings():
    ESP_Brookesia_PhoneApp("Settings", &img_app_setting, true)
{
}

static void black(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);
    lv_obj_set_style_text_color(screen, lv_color_white(), 0);
    lv_obj_clear_flag(screen, LV_OBJ_FLAG_SCROLLABLE);
}

static void dark(lv_obj_t *panel)
{
    lv_obj_set_style_bg_color(panel, ROW_COLOR, 0);
    lv_obj_set_style_bg_color(panel, PRESSED, LV_STATE_PRESSED);
    lv_obj_set_style_bg_opa(panel, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(panel, 0, 0);
    lv_obj_set_style_text_color(panel, lv_color_white(), 0);
    lv_obj_clear_flag(panel, LV_OBJ_FLAG_SCROLLABLE);
}

static void place(lv_obj_t *obj, lv_align_t align, int x, int y)
{
    lv_obj_set_align(obj, align);
    lv_obj_set_pos(obj, x, y);
}

// the generated screens are laid out for a wider panel and a light theme
void AppSettings::layout(void)
{
    int top = getVisualArea().y1;

    black(ui_ScreenSettingMain);
    lv_obj_t *title = lv_label_create(ui_ScreenSettingMain);
    lv_label_set_text(title, "Settings");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_40, 0);
    place(title, LV_ALIGN_TOP_MID, 0, top + 24);

    lv_obj_set_size(ui_PanelSettingMainContainer, WIDTH, 100);
    place(ui_PanelSettingMainContainer, LV_ALIGN_TOP_MID, 0, top + 110);
    lv_obj_set_style_bg_opa(ui_PanelSettingMainContainer, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(ui_PanelSettingMainContainer, 0, 0);
    lv_obj_add_flag(ui_PanelSettingMainContainerItem1, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(ui_PanelSettingMainContainerItem3, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(ui_PanelSettingMainContainerItem4, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(ui_PanelSettingMainContainerItem5, LV_OBJ_FLAG_HIDDEN);
    lv_obj_set_size(ui_PanelSettingMainContainerItem2, WIDTH, 100);
    dark(ui_PanelSettingMainContainerItem2);
    place(ui_ImagePanelSettingMainContainer2Blue, LV_ALIGN_LEFT_MID, 8, 0);
    place(ui_LabelPanelSettingMainContainer2Blue, LV_ALIGN_LEFT_MID, 64, 0);
    lv_label_set_text(ui_LabelPanelSettingMainContainer2Blue, "Bluetooth");
    place(ui_ImagePanelSettingMainContainer2Arrow, LV_ALIGN_RIGHT_MID, -8, 0);

    black(ui_ScreenSettingBLE);
    lv_obj_set_size(ui_ButtonScreenSettingBLEReturn, 80, 80);
    place(ui_ButtonScreenSettingBLEReturn, LV_ALIGN_TOP_LEFT, 16, top + 8);
    lv_obj_set_style_bg_color(ui_ButtonScreenSettingBLEReturn, lv_color_black(), 0);
    lv_obj_set_style_bg_color(ui_ButtonScreenSettingBLEReturn, PRESSED, LV_STATE_PRESSED);
    lv_obj_set_style_shadow_width(ui_ButtonScreenSettingBLEReturn, 0, 0);
    lv_obj_set_style_img_recolor_opa(ui_ImageScreenSettingBLEReturn, LV_OPA_TRANSP, 0);
    lv_obj_set_style_img_recolor(ui_ImagePanelSettingMainContainer2Arrow, lv_color_white(), 0);
    lv_obj_set_style_img_recolor_opa(ui_ImagePanelSettingMainContainer2Arrow, LV_OPA_COVER, 0);

    lv_obj_set_size(ui_PanelScreenSettingBLESwitch, WIDTH, 100);
    place(ui_PanelScreenSettingBLESwitch, LV_ALIGN_TOP_MID, 0, top + 104);
    dark(ui_PanelScreenSettingBLESwitch);
    place(ui_ImagePanelScreenSettingBLESwitch, LV_ALIGN_LEFT_MID, 8, 0);
    place(ui_LabelPanelScreenSettingBLESwitch, LV_ALIGN_LEFT_MID, 64, 0);
    lv_obj_set_size(ui_SwitchPanelScreenSettingBLESwitch, 100, 52);
    place(ui_SwitchPanelScreenSettingBLESwitch, LV_ALIGN_RIGHT_MID, -8, 0);
    lv_obj_set_style_bg_color(ui_SwitchPanelScreenSettingBLESwitch, PRESSED, LV_PART_MAIN);
    lv_obj_set_style_bg_color(ui_SwitchPanelScreenSettingBLESwitch, GREY, LV_PART_INDICATOR | LV_STATE_CHECKED);
    lv_obj_add_event_cb(ui_SwitchPanelScreenSettingBLESwitch, onPower, LV_EVENT_VALUE_CHANGED, this);

    _status = lv_label_create(ui_ScreenSettingBLE);
    lv_obj_set_width(_status, WIDTH);
    lv_label_set_long_mode(_status, LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_font(_status, SMALL, 0);
    lv_obj_set_style_text_color(_status, GREY, 0);
    place(_status, LV_ALIGN_TOP_MID, 0, top + 224);

    lv_obj_t *list = ui_PanelScreenSettingBLEList;
    lv_obj_set_size(list, WIDTH, getVisualArea().y2 - top - 280);
    place(list, LV_ALIGN_TOP_MID, 0, top + 268);
    lv_obj_set_style_bg_opa(list, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(list, 0, 0);
    lv_obj_set_style_pad_all(list, 0, 0);
    lv_obj_set_style_pad_row(list, 4, 0);
    lv_obj_set_scroll_dir(list, LV_DIR_VER);

    // small, at the top right: the middle belongs to the list
    lv_obj_set_size(ui_SpinnerScreenSettingBLE, 56, 56);
    place(ui_SpinnerScreenSettingBLE, LV_ALIGN_TOP_RIGHT, -24, top + 20);
    lv_obj_set_style_arc_color(ui_SpinnerScreenSettingBLE, ROW_COLOR, LV_PART_MAIN);
}

bool AppSettings::run(void)
{
    ui_ScreenSettingMain_screen_init();
    ui_ScreenSettingBLE_screen_init();
    layout();
    _box = nullptr;
    _open = true;
    _timer = lv_timer_create(onTimer, 200, this);
    lv_scr_load(ui_ScreenSettingMain);
    if (_command == nullptr) {
        start("");
    }
    show();
    return true;
}

bool AppSettings::back(void)
{
    if (lv_scr_act() == ui_ScreenSettingBLE) {
        lv_scr_load(ui_ScreenSettingMain);
    } else {
        notifyCoreClosed();
    }
    return true;
}

bool AppSettings::close(void)
{
    _open = false;
    lv_timer_del(_timer);
    return true;
}

// Every action is followed by the same report: P power, C connected address,
// D paired device; a search adds N nearby device, a failure F.
void AppSettings::start(const std::string &action)
{
    const char *tool = getenv("BT_AUDIO");
    std::string script = "b='" + std::string(tool ? tool : "bt-audio") + "'; ";

    if (_command != nullptr) {
        return;
    }
    if (action == "scan") {
        script += "$b scan 10 | sed 's/^/N /'; ";
    } else if (!action.empty()) {
        script += "$b " + action + " >/dev/null || echo F; ";
    }
    script += "$b power | sed 's/^/P /'; $b current | sed 's/^/C /'; $b paired | sed 's/^/D /'";
    _command = popen(script.c_str(), "r");
    _action = action;
    _output.clear();
    _message = _command == nullptr ? "Bluetooth tool not available" : "";
    if (_command != nullptr) {
        fcntl(fileno(_command), F_SETFL, O_NONBLOCK);
    }
    show();
}

void AppSettings::poll(void)
{
    char buffer[512];
    ssize_t n;

    if (_command == nullptr) {
        return;
    }
    while ((n = read(fileno(_command), buffer, sizeof(buffer))) > 0) {
        _output.append(buffer, n);
    }
    if (n < 0 && errno == EAGAIN) {
        return;
    }
    pclose(_command);
    _command = nullptr;
    parse();
    show();
}

// addresses go back into a shell command: take nothing else for one
static bool isAddress(const std::string &s)
{
    if (s.size() != 17) {
        return false;
    }
    for (int i = 0; i < 17; i++) {
        if (i % 3 == 2 ? s[i] != ':' : !isxdigit((unsigned char)s[i])) {
            return false;
        }
    }
    return true;
}

void AppSettings::parse(void)
{
    size_t from = 0;

    _paired.clear();
    _connected.clear();
    _powered = false;
    if (_action == "scan") {
        _nearby.clear();
    }
    while (from < _output.size()) {
        size_t end = _output.find('\n', from);
        if (end == std::string::npos) {
            end = _output.size();
        }
        std::string line = _output.substr(from, end - from);
        from = end + 1;
        if (line == "F") {
            _message = _action.compare(0, 8, "connect ") ? "That did not work" :
                       "Could not connect. Is it in pairing mode?";
        } else if (line == "P on") {
            _powered = true;
        } else if (line.size() >= 19 && line.compare(0, 2, "C ") == 0) {
            _connected = line.substr(2, 17);
        } else if (line.size() > 20 && (line[0] == 'D' || line[0] == 'N') && isAddress(line.substr(2, 17))) {
            (line[0] == 'D' ? _paired : _nearby).push_back({ line.substr(2, 17), line.substr(20) });
        }
    }
}

void AppSettings::addHeader(const char *text)
{
    lv_obj_t *label = lv_label_create(ui_PanelScreenSettingBLEList);
    lv_label_set_text(label, text);
    lv_obj_set_style_text_font(label, SMALL, 0);
    lv_obj_set_style_text_color(label, GREY, 0);
    lv_obj_set_style_pad_top(label, 16, 0);
}

static lv_obj_t *row(const char *text)
{
    lv_obj_t *panel = lv_obj_create(ui_PanelScreenSettingBLEList);
    lv_obj_set_size(panel, lv_pct(100), ROW_HEIGHT);
    dark(panel);

    lv_obj_t *label = lv_label_create(panel);
    lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
    lv_obj_set_size(label, 470, lv_font_get_line_height(FONT));
    lv_label_set_text(label, text);
    lv_obj_set_style_text_font(label, FONT, 0);
    lv_obj_align(label, LV_ALIGN_LEFT_MID, 0, 0);
    return panel;
}

// rows carry their place in the list: paired devices first, then nearby ones
void AppSettings::addDevice(const Device &device, bool paired)
{
    lv_obj_t *panel = row(device.name.c_str());
    size_t index = paired ? &device - _paired.data() : _paired.size() + (&device - _nearby.data());

    if (device.address == _connected) {
        lv_obj_t *mark = lv_label_create(panel);
        lv_label_set_text(mark, LV_SYMBOL_OK);
        lv_obj_set_style_text_font(mark, FONT, 0);
        lv_obj_align(mark, LV_ALIGN_RIGHT_MID, 0, 0);
    }
    lv_obj_set_user_data(panel, (void *)index);
    lv_obj_add_event_cb(panel, onDevice, LV_EVENT_CLICKED, this);
}

void AppSettings::show(void)
{
    if (!_open) {
        return;
    }
    bool busy = _command != nullptr;
    std::string status = _message;

    if (busy) {
        status = _action == "scan" ? "Searching..." :
                 _action.compare(0, 8, "connect ") ? "Please wait..." : "Connecting " + _chosen + "...";
        lv_obj_clear_flag(ui_SpinnerScreenSettingBLE, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_state(ui_SwitchPanelScreenSettingBLESwitch, LV_STATE_DISABLED);
    } else {
        lv_obj_add_flag(ui_SpinnerScreenSettingBLE, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_state(ui_SwitchPanelScreenSettingBLESwitch, LV_STATE_DISABLED);
        if (_powered) {
            lv_obj_add_state(ui_SwitchPanelScreenSettingBLESwitch, LV_STATE_CHECKED);
        } else {
            lv_obj_clear_state(ui_SwitchPanelScreenSettingBLESwitch, LV_STATE_CHECKED);
        }
    }
    lv_label_set_text(_status, status.c_str());

    lv_obj_t *list = ui_PanelScreenSettingBLEList;
    lv_obj_clean(list);
    lv_obj_clear_flag(list, LV_OBJ_FLAG_HIDDEN);
    if (!_powered) {
        return;
    }
    if (!_paired.empty()) {
        addHeader("Paired");
        for (const Device &device : _paired) {
            addDevice(device, true);
        }
    }
    addHeader("Nearby");
    for (const Device &device : _nearby) {
        bool known = false;
        for (const Device &other : _paired) {
            known = known || other.address == device.address;
        }
        if (!known) {
            addDevice(device, false);
        }
    }
    if (!busy) {
        lv_obj_add_event_cb(row(LV_SYMBOL_REFRESH "  Search"), onSearch, LV_EVENT_CLICKED, this);
    }
}

static const char *connect_buttons[] = { "Connect", "Forget", "" };
static const char *connected_buttons[] = { "Disconnect", "Forget", "" };

void AppSettings::ask(const Device &device, bool paired)
{
    _chosen = device.name;
    _action = device.address;   // the box's answer acts on this one
    if (!paired) {
        start("connect " + device.address);
        return;
    }
    _box = lv_msgbox_create(ui_ScreenSettingBLE, device.name.c_str(), "",
                            device.address == _connected ? connected_buttons : connect_buttons, true);
    lv_obj_set_width(_box, 520);
    dark(_box);
    lv_obj_set_style_text_font(_box, SMALL, 0);
    lv_obj_t *buttons = lv_msgbox_get_btns(_box);
    lv_obj_set_size(buttons, 480, 80);
    lv_obj_set_style_text_color(buttons, lv_color_black(), LV_PART_ITEMS);
    lv_obj_t *cross = lv_msgbox_get_close_btn(_box);
    lv_obj_set_style_bg_color(cross, PRESSED, 0);
    // the box goes away by its cross too
    lv_obj_add_event_cb(_box, onBoxDeleted, LV_EVENT_DELETE, this);
    lv_obj_center(_box);
    lv_obj_add_event_cb(_box, onChoice, LV_EVENT_VALUE_CHANGED, this);
}

void AppSettings::onChoice(lv_event_t *e)
{
    AppSettings *app = (AppSettings *)lv_event_get_user_data(e);
    const char *choice = lv_msgbox_get_active_btn_text(app->_box);
    std::string verb = choice == nullptr ? "" : !strcmp(choice, "Connect") ? "connect " :
                       !strcmp(choice, "Disconnect") ? "disconnect " : "forget ";
    std::string address = app->_action;

    lv_msgbox_close_async(app->_box);
    if (!verb.empty() && isAddress(address)) {
        app->start(verb + address);
    }
}

void AppSettings::onBoxDeleted(lv_event_t *e)
{
    ((AppSettings *)lv_event_get_user_data(e))->_box = nullptr;
}

void AppSettings::onDevice(lv_event_t *e)
{
    AppSettings *app = (AppSettings *)lv_event_get_user_data(e);
    size_t index = (size_t)lv_obj_get_user_data(lv_event_get_current_target(e));
    bool paired = index < app->_paired.size();

    if (app->_command != nullptr || app->_box != nullptr) {
        return;
    }
    // a copy: starting a command rebuilds the list
    Device device = paired ? app->_paired[index] : app->_nearby[index - app->_paired.size()];
    app->ask(device, paired);
}

void AppSettings::onSearch(lv_event_t *e)
{
    AppSettings *app = (AppSettings *)lv_event_get_user_data(e);

    if (app->_box == nullptr) {
        app->start("scan");
    }
}

void AppSettings::onPower(lv_event_t *e)
{
    AppSettings *app = (AppSettings *)lv_event_get_user_data(e);
    bool on = lv_obj_has_state(lv_event_get_target(e), LV_STATE_CHECKED);

    app->start(on ? "power on" : "power off");
}

void AppSettings::onTimer(lv_timer_t *timer)
{
    ((AppSettings *)timer->user_data)->poll();
}
