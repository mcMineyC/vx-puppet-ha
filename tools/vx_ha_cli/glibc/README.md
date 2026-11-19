Minimal glibc runtime embedded into vx_ha_cli so lightpanda (glibc-linked,
needs GLIBC_2.35) can run inside Home Assistant's Alpine/musl container.

Source: Debian bookworm `libc6_2.36-9+deb12u14_{amd64,arm64}.deb`
(deb.debian.org/debian/pool/main/g/glibc/). glibc is LGPL-2.1+; source at
https://sources.debian.org/src/glibc/2.36-9+deb12u14/
