/* What the generated ui.c would define, for the two screens in use (main menu
 * and Bluetooth). ui.c itself builds all seven and insists on 16-bit colour. */
#include "ui.h"

lv_obj_t *ui_ScreenSettingMain, *ui_PanelSettingMainContainer;
#define ITEM(n, icon, label) \
	lv_obj_t *ui_PanelSettingMainContainerItem##n, *ui_ImagePanelSettingMainContainer##n##icon, \
		 *ui_ImagePanelSettingMainContainer##n##Arrow, *ui_LabelPanelSettingMainContainer##n##label;
ITEM(1, WiFi, WiFi)
ITEM(2, Blue, Blue)
ITEM(3, Volume, Volume)
ITEM(4, Light, Light)
ITEM(5, About, About)

lv_obj_t *ui_ScreenSettingBLE, *ui_PanelScreenSettingBLESwitch, *ui_ImagePanelScreenSettingBLESwitch,
	 *ui_LabelPanelScreenSettingBLESwitch, *ui_SwitchPanelScreenSettingBLESwitch,
	 *ui_PanelScreenSettingBLEList, *ui_SpinnerScreenSettingBLE, *ui_ButtonScreenSettingBLEReturn,
	 *ui_ImageScreenSettingBLEReturn;

static void go(lv_event_t *e, lv_obj_t *screen)
{
	if (lv_event_get_code(e) == LV_EVENT_CLICKED)
		lv_scr_load(screen);
}

/* only the Bluetooth item is shown: the others lead nowhere */
void ui_event_PanelSettingMainContainerItem1(lv_event_t *e) { (void)e; }
void ui_event_PanelSettingMainContainerItem2(lv_event_t *e) { go(e, ui_ScreenSettingBLE); }
void ui_event_PanelSettingMainContainerItem3(lv_event_t *e) { (void)e; }
void ui_event_PanelSettingMainContainerItem4(lv_event_t *e) { (void)e; }
void ui_event_PanelSettingMainContainerItem5(lv_event_t *e) { (void)e; }
void ui_event_ButtonScreenSettingBLEReturn(lv_event_t *e) { go(e, ui_ScreenSettingMain); }
