#!/bin/sh
# The armel C++ compiler and libstdc++, unpacked without installing anything,
# next to the platform's tools in linux-n81/work (needs apt on the host).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
dir=${1:-$here/../linux-n81/work/hosttools/cxx}
mkdir -p "$dir/debs" "$dir/root"
cd "$dir/debs"
apt-get download g++-15-arm-linux-gnueabi libstdc++-15-dev-armel-cross libstdc++6-armel-cross
for d in *.deb; do dpkg-deb -x "$d" ../root; done
