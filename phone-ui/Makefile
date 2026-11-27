# ESP-Brookesia phone UI (Apache-2.0) on Linux, with LVGL 8.4.
# make                 PC preview (build/phone/phone --shot DIR [X,Y ...])
# make TARGET=device   static armv7 binary for the iPod
T := third_party
CROSS := arm-linux-gnueabi-
SYSROOT ?= ../linux-n81/work/hosttools/armel/usr/arm-linux-gnueabi
ifeq ($(TARGET),device)
OUT := build/phone-device
CC := $(CROSS)gcc
# C++ compiler and library unpacked next to the platform's tools (./fetch-cxx.sh)
CXXROOT ?= ../linux-n81/work/hosttools/cxx/root
CXXINC := $(CXXROOT)/usr/arm-linux-gnueabi/include/c++/15
CXX := $(CROSS)gcc -B$(CXXROOT)/usr/libexec/gcc-cross/arm-linux-gnueabi/15/
ARCH := -march=armv7-a -B$(SYSROOT)/lib/
LINK = $(CC)
LIBS := $(CXXROOT)/usr/lib/gcc-cross/arm-linux-gnueabi/15/libstdc++.a -lm
CFLAGS += -DDEVICE $(ARCH) -isystem $(SYSROOT)/include
CXXFLAGS += -DDEVICE $(ARCH) -nostdinc++ -isystem $(CXXINC) -isystem $(CXXINC)/arm-linux-gnueabi \
	-isystem $(CXXINC)/backward -isystem $(SYSROOT)/include
LDFLAGS := -static $(ARCH) -L$(SYSROOT)/lib -s
else
OUT := build/phone
LINK = $(CXX)
LIBS := -lm
endif
INC := -I. -Icompat -I$(T) -I$(T)/lvgl8 -I$(T)/esp-brookesia -I$(T)/esp-brookesia/src \
	-I$(T)/brookesia-apps/calculator \
	-I$(T)/brookesia-apps/music_player -Imusic \
	-I$(T)/brookesia-apps/setting/ui -Isetting
SETTING := $(T)/brookesia-apps/setting
MUSIC := $(T)/brookesia-apps/music_player
FLAGS := -O2 -ffunction-sections -fdata-sections -DLV_CONF_INCLUDE_SIMPLE -DLV_LVGL_H_INCLUDE_SIMPLE $(INC)
# of the Settings example only two screens and the app icon are built
SETTING_OBJ := $(addprefix $(OUT)/obj/brookesia-apps/setting/,ui/screens/ui_ScreenSettingMain.o \
	ui/screens/ui_ScreenSettingBLE.o assets/img_app_setting.o) \
	$(OUT)/obj/setting/setting_ui.o $(OUT)/obj/setting/icons.o $(OUT)/obj/setting/Setting.o
CSRC := $(shell find $(T)/lvgl8/src $(T)/esp-brookesia/src $(T)/brookesia-apps/calculator $(MUSIC) -name '*.c')
CXXSRC := $(shell find $(T)/esp-brookesia/src $(T)/brookesia-apps/calculator $(MUSIC) -name '*.cpp') main.cpp
OBJ := $(SETTING_OBJ) $(OUT)/obj/music/n81_player.o $(CSRC:$(T)/%.c=$(OUT)/obj/%.o) $(patsubst %.cpp,$(OUT)/obj/%.o,$(CXXSRC:$(T)/%=%))

all: $(OUT)/phone

$(OUT)/phone: $(OBJ)
	$(LINK) $(LDFLAGS) -Wl,--gc-sections -o $@ $(OBJ) $(LIBS)
$(OUT)/obj/%.o: $(T)/%.c lv_conf.h
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(FLAGS) -I$(T)/lvgl8/src -c -o $@ $<
$(OUT)/obj/%.o: $(T)/%.cpp lv_conf.h
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -std=gnu++17 $(FLAGS) -c -o $@ $<
$(OUT)/obj/main.o: main.cpp setting/Setting.hpp lv_conf.h
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -std=gnu++17 $(FLAGS) -c -o $@ $<
$(OUT)/obj/music/n81_player.o: music/n81_player.c music/n81_player.h
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(FLAGS) -D_GNU_SOURCE -c -o $@ $<
$(OUT)/obj/setting/setting_ui.o: setting/setting_ui.c lv_conf.h
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(FLAGS) -c -o $@ $<
$(OUT)/obj/setting/icons.c: setting/icons.py
	@mkdir -p $(dir $@)
	python3 setting/icons.py $(SETTING)/ui/images $@
$(OUT)/obj/setting/icons.o: $(OUT)/obj/setting/icons.c lv_conf.h
	$(CC) $(CFLAGS) $(FLAGS) -I$(T)/lvgl8 -c -o $@ $<
$(OUT)/obj/setting/Setting.o: setting/Setting.cpp setting/Setting.hpp lv_conf.h
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -std=gnu++17 $(FLAGS) -c -o $@ $<
