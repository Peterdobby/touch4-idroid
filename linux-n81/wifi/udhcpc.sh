#!/bin/sh
case "$1" in
deconfig) ifconfig $interface 0.0.0.0 up ;;
bound|renew)
	ifconfig $interface $ip netmask ${subnet:-255.255.255.0}
	for r in $router; do route add default gw $r dev $interface; break; done
	: > /etc/resolv.conf
	for d in $dns; do echo "nameserver $d" >> /etc/resolv.conf; done ;;
esac
