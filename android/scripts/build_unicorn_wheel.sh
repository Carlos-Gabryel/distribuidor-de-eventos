#!/usr/bin/env bash
# Compila libunicorn.so 2.1.4 (arm64-v8a, android-24) e monta o wheel android_24_arm64_v8a.
# Uso: build_unicorn_wheel.sh <diretório-de-saída>   (precisa de ANDROID_NDK_LATEST_HOME ou ANDROID_HOME)
set -euxo pipefail
OUT="$(mkdir -p "$1" && cd "$1" && pwd)"
NDK="${ANDROID_NDK_LATEST_HOME:-$(ls -d "$ANDROID_HOME"/ndk/* | sort -V | tail -1)}"
echo "NDK=$NDK"
W="$(mktemp -d)"; cd "$W"
pip download unicorn==2.1.4 --no-binary :all: --no-deps -q
tar xzf unicorn-2.1.4.tar.gz
cd unicorn-2.1.4
cmake -S src -B build-android -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-24 \
  -DUNICORN_ARCH="arm;aarch64" -DUNICORN_BUILD_TESTS=OFF \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-android -j"$(nproc)"
SO="$(find build-android -name 'libunicorn.so' | head -1)"
test -n "$SO"
mkdir -p "$W/pkg/unicorn/lib"
cp -r unicorn/* "$W/pkg/unicorn/"
cp -L "$SO" "$W/pkg/unicorn/lib/libunicorn.so"
"${NDK}"/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip --strip-unneeded "$W/pkg/unicorn/lib/libunicorn.so" || true
D="$W/pkg/unicorn-2.1.4.dist-info"; mkdir -p "$D"
grep -v '^Requires-Dist' PKG-INFO > "$D/METADATA"
printf 'Wheel-Version: 1.0\nGenerator: distrib\nRoot-Is-Purelib: false\nTag: py3-none-android_24_arm64_v8a\n' > "$D/WHEEL"
pip install -q wheel
wheel pack "$W/pkg" -d "$OUT"
ls -la "$OUT"
