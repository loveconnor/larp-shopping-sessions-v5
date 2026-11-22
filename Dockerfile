# Shopping Sessions: one Rust binary with no crate dependencies.
# The scorers build this natively on linux/amd64; on an Apple-silicon Mac the
# builder stage cross-compiles, so `docker buildx build --platform linux/amd64`
# stays fast there too.
FROM --platform=$BUILDPLATFORM rust:1.90-slim-bookworm AS builder
ARG BUILDARCH
ARG TARGETARCH
WORKDIR /src
ENV CARGO_PROFILE_RELEASE_STRIP=none
RUN case "$TARGETARCH" in \
      amd64) target=x86_64-unknown-linux-gnu; linker=x86_64-linux-gnu-gcc; cross=gcc-x86-64-linux-gnu ;; \
      arm64) target=aarch64-unknown-linux-gnu; linker=aarch64-linux-gnu-gcc; cross=gcc-aarch64-linux-gnu ;; \
      *) exit 1 ;; \
    esac && \
    if [ "$BUILDARCH" != "$TARGETARCH" ]; then \
        apt-get update && apt-get install -y --no-install-recommends "$cross" "libc6-dev-$TARGETARCH-cross"; \
    fi && \
    rustup target add "$target" && printf '%s\n%s\n' "$target" "$linker" > /target-info
COPY native/ ./
# Build the ranked v3/v4 sources first. Only the final wide build applies the
# changes measured on byte-compression-capable AMD hosts.
RUN target="$(head -n 1 /target-info)" && linker="$(tail -n 1 /target-info)" && \
    if [ "$BUILDARCH" = "$TARGETARCH" ]; then linker=cc; fi && \
    mkdir -p /app && \
    if [ "$TARGETARCH" = amd64 ]; then \
        apt-get update && apt-get install -y --no-install-recommends patch && \
        for level in base v3 v4 wide; do \
            cpu=x86-64-$level; profile=v5; features=; \
            case "$level" in base) cpu=x86-64 ;; v4) profile=v4 ;; wide) patch -p2 < platform/wide.patch || exit 1; cpu=x86-64-v4; features="-C target-feature=+avx512vbmi2"; profile=wide ;; esac; \
            RUSTFLAGS="-C link-arg=-Wl,--emit-relocs -C linker=$linker -C target-cpu=$cpu $features -Cprofile-use=/src/profile/$profile.profdata" \
              cargo build --locked --release --target "$target" || exit 1; \
            cp "target/$target/release/shopping-sessions" "/app/shopping-sessions.$level" || exit 1; \
        done && "$linker" -O2 platform/select-engine.c -o /app/shopping-sessions; \
    else \
        RUSTFLAGS="-C link-arg=-Wl,--emit-relocs -C linker=$linker -C target-cpu=generic" cargo build --locked --release --target "$target" && \
        cp "target/$target/release/shopping-sessions" /app/shopping-sessions; \
    fi

FROM --platform=$BUILDPLATFORM debian:trixie-slim AS optimized
ARG TARGETARCH
COPY --from=builder /app /app
COPY native/profile/edges/ /profiles/
RUN if [ "$TARGETARCH" = amd64 ]; then \
        apt-get update && apt-get install -y --no-install-recommends bolt-19 && \
        for level in v3 v4 wide; do \
            gzip -dc "/profiles/$level.fdata.gz" > /tmp/edges && \
            llvm-bolt-19 "/app/shopping-sessions.$level" -o /tmp/optimized \
                -data=/tmp/edges -reorder-blocks=ext-tsp -reorder-functions=hfsort+ \
                -split-functions -split-all-cold -split-eh -dyno-stats && \
            mv /tmp/optimized "/app/shopping-sessions.$level" || exit 1; \
        done; \
    fi

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends libjemalloc2 && rm -rf /var/lib/apt/lists/*
ENV LD_PRELOAD=libjemalloc.so.2
ENV MALLOC_CONF=background_thread:false,dirty_decay_ms:-1,muzzy_decay_ms:-1,thp:always,metadata_thp:auto
COPY --from=optimized /app /app
CMD ["/app/shopping-sessions"]
