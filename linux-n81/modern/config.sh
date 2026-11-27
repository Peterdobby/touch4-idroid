# Applied on top of s5l8930_defconfig: small image, no storage, USB serial.
# Later lines win: Wi-Fi turns modules, networking and the SDIO host back on.
-d MODULES -d NET -d SCSI -d ATA -d MMC -d MTD -d SOUND -d MEDIA_SUPPORT -d SWAP
-d USB -d USB_ETH -e USB_GADGET -e USB_DWC2 -e USB_DWC2_PERIPHERAL -e USB_G_SERIAL
-e PHY_S5L8702_USB2
-d DEBUG_LL -d DEBUG_KERNEL
-d DRM_PANEL_SAMSUNG_LD9040 -d DRM_PANEL_SAMSUNG_S6E63J0X03 -d DRM_PANEL_SAMSUNG_S6E8AA0
-d DRM_SAMSUNG_DSIM -d DRM_NXP_PTN3460 -d DRM_PARADE_PS8622 -d DRM_SII9234 -d DRM_TOSHIBA_TC358764
-e DRM_SIMPLEDRM -e FRAMEBUFFER_CONSOLE -e FONTS -e FONT_TER16x32
-e DEVMEM -d STRICT_DEVMEM -e ARM_APPENDED_DTB -e ARM_ATAG_DTB_COMPAT
--set-str CMDLINE "console=tty0 fbcon=font:TER16x32"
# Touch: userspace driver on SPI1 via /dev/mem, PMU over bit-banged I2C.
-e PINCTRL -e PINCTRL_APPLE_GPIO -e I2C -e I2C_GPIO -e I2C_CHARDEV -e INPUT_EVDEV
-e INPUT_MISC -e INPUT_UINPUT
# Wi-Fi (BCM4329 on SDIO): drivers are modules pushed at run time. No MMC_BLOCK,
# so no card or eMMC storage driver exists.
-e MODULES -e MODULE_UNLOAD -e NET -e INET -e UNIX -e PACKET -d IPV6 -d NETFILTER -d ETHERNET -d CAN -d BT
-e MMC -d MMC_BLOCK -e MMC_SDHCI -m MMC_SDHCI_PLTFM -m MMC_SDHCI_S5L8930
-e WIRELESS -m CFG80211 -d MAC80211 -e NETDEVICES -e WLAN -e WLAN_VENDOR_BROADCOM -m BRCMFMAC -e BRCMFMAC_SDIO
-d BRCMFMAC_USB -d BRCMFMAC_PCIE -d CFG80211_REQUIRE_SIGNED_REGDB -d CFG80211_USE_KERNEL_REGDB_KEYS
# Sound: ALSA core and OSS emulation as modules; the only driver is ours
# (audio/driver, built out of tree).
-m SOUND -m SND -m SND_PCM -e SND_OSSEMUL -m SND_PCM_OSS -m SND_MIXER_OSS
-d SND_DRIVERS -d SND_ARM -d SND_SOC -d SND_USB -d SND_SPI -d SND_PCI -d SOUND_PRIME
-u SND_CTL_FAST_LOOKUP
# Bluetooth (BCM4329 on UART1): classic only, H4 line discipline, as modules.
-m BT -e BT_BREDR -d BT_LE -m BT_RFCOMM -e BT_HIDP -m BT_HCIUART -e BT_HCIUART_H4 -d BT_HCIBTUSB -d BT_HCIUART_BCM
# xz for the kernel and its built-in root: the loader takes at most 12 MiB
-d KERNEL_GZIP -e KERNEL_XZ
