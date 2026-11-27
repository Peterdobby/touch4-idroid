#!/bin/sh
# What iOS 6.1.6 sets on this BCM4329 once associated (values read from its
# AppleBCMWLAN driver under qemu-ios): power saving, beacon and roaming.
W=n81-wifi
for v in "bcn_timeout 8" "bcn_to_dly 1" "pm2_refresh_badiv 1" "pm2_md_sleep_ext 1" \
	 "assoc_listen 15" "bcn_li_bcn 1" "pm2_radio_shutoff_dly 10" "pm2_bcn_sleep_ret 120" \
	 "pm2_sleep_ret 60" "scan_passive_time 110" "assoc_retry_max 5" \
	 "fullroamperiod 60" "roamperiod 10" "roam_nfscan 3" "txfail_roamthresh 0" \
	 "cmd 55 -75 3" "cmd 57 20 3" "cmd 86 2"; do
	$W set $v >/dev/null 2>&1 || echo "refused: $v"
done
