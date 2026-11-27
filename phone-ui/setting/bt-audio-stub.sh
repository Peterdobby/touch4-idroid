#!/bin/sh
# Stands in for the platform's bt-audio in the PC preview:
# BT_AUDIO="sh $PWD/phone-ui/setting/bt-audio-stub.sh"
case $1 in
power) [ -n "${2:-}" ] || echo on ;;
current) echo 00:11:22:33:44:55 ;;
paired) echo '00:11:22:33:44:55 WH-CH720N'; echo '66:77:88:99:AA:BB A phone with a very long name that has to be cut' ;;
scan) sleep 2; echo '00:11:22:33:44:55 WH-CH720N'; echo 'CC:DD:EE:FF:00:11 Speaker' ;;
connect) sleep 2; exit 1 ;;
esac
