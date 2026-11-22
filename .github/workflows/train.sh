set -euo pipefail
cpu=x86-64-v3
level=v3
flags=()
cargo_features=()
previous=v5
if grep -qw avx512bw /proc/cpuinfo; then
    cpu=x86-64-v4
    if grep -qw avx512_vbmi2 /proc/cpuinfo; then
        level=wide
        flags=(-C target-feature=+avx512vbmi2)
    else
        level=n4
        cargo_features=(--features narrow-v4)
    fi
    previous=$level
fi
merger="$(rustc --print sysroot)/lib/rustlib/x86_64-unknown-linux-gnu/bin/llvm-profdata"
printf '%s\n' "$level" > /study/engines/level
for label in base aligned bins links; do
    cd "/study/sources/$label/native"
    if [ "$level" = wide ]; then patch -s -p2 < platform/wide.patch; fi
    export CARGO_TARGET_DIR="/tmp/target-$label"
    dir="/tmp/counters-$label"
    mkdir "$dir"
    common="-C linker=cc -C target-cpu=$cpu ${flags[*]}"
    RUSTFLAGS="$common -Cprofile-generate=$dir" cargo build --locked --release "${cargo_features[@]}" --target x86_64-unknown-linux-gnu
    engine="$CARGO_TARGET_DIR/x86_64-unknown-linux-gnu/release/shopping-sessions"
    NCPU=8 LD_PRELOAD=libjemalloc.so.2 MALLOC_CONF=narenas:2,background_thread:false,dirty_decay_ms:-1,muzzy_decay_ms:-1,thp:always,metadata_thp:auto DATA_DIR=/study/train OUTPUT_DIR="/tmp/out-$label" "$engine"
    "$merger" merge --sparse "$dir"/*.profraw -o "/study/profiles/$label-$level.profdata"
    for trained in original matched; do
        profile="$PWD/profile/$previous.profdata"
        if [ "$trained" = matched ]; then profile="/study/profiles/$label-$level.profdata"; fi
        RUSTFLAGS="$common -Cprofile-use=$profile" cargo build --locked --release "${cargo_features[@]}" --target x86_64-unknown-linux-gnu
        cp "$engine" "/study/engines/$label-$trained"
    done
done
