ARG BUILD_ARCH
FROM ghcr.io/home-assistant/${BUILD_ARCH}-base:latest

ENV LANG C.UTF-8
ENV PYTHONUNBUFFERED=1
WORKDIR /opt/moonlight-voice

# Install Python if not already available in the base image, and ensure ffmpeg is present for conversions.
RUN \
    if ! command -v python3 >/dev/null 2>&1; then \
        echo \"Python not present, installing...\" && \
        apk add --no-cache python3; \
    fi && \
    apk add --no-cache ffmpeg

COPY moonlight_voice /opt/moonlight-voice/moonlight_voice
COPY run.sh /opt/moonlight-voice/run.sh
COPY rootfs /

RUN chmod +x /opt/moonlight-voice/run.sh /etc/services.d/moonlight-voice/run

EXPOSE 8031
