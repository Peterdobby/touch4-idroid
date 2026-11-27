FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends squashfs-tools python3 curl ca-certificates binutils file libegl1 libgl1 libegl-mesa0 libgl1-mesa-dri libusb-1.0-0
