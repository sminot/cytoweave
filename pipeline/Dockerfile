# cytoweave and Chromium, for "cytoweave run" in a pipeline. Build from the repository root:
#   docker build -f pipeline/Dockerfile -t cytoweave-run .

# The binary is cross-compiled on the build machine, so an amd64 image builds quickly on arm64.
FROM --platform=$BUILDPLATFORM golang:1.24-bookworm AS build
ARG TARGETARCH
WORKDIR /src
COPY go.mod ./
COPY *.go ./
COPY web ./web
RUN CGO_ENABLED=0 GOARCH=$TARGETARCH go build -trimpath -ldflags "-s -w" -o /cytoweave .

FROM debian:bookworm-slim
# procps: Nextflow reads task metrics with ps. Fonts: the figures' text is drawn by Chromium.
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium fonts-dejavu-core fonts-liberation procps ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /cytoweave /usr/local/bin/cytoweave
# Chromium's sandbox needs privileges a container does not grant (and refuses to run as root
# without --no-sandbox); the container is the sandbox. Docker's /dev/shm is 64 MB, too small for
# large samples, so shared memory goes to /tmp.
RUN printf '#!/bin/sh\nexec /usr/bin/chromium --no-sandbox --disable-dev-shm-usage "$@"\n' > /usr/local/bin/chromium-container \
    && chmod +x /usr/local/bin/chromium-container
ENV CHROME=/usr/local/bin/chromium-container
