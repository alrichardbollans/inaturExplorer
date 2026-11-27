FROM python:3.12-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# --- System packages (Python side) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        git-lfs \
        ffmpeg \
        libsm6 \
        libxext6 \
        cmake \
        rsync \
        libgl1 \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

# --- R 4.5 from Posit (Debian 12 build) plus system libs for R packages ---
ARG R_VERSION=4.5.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl build-essential gfortran pkg-config \
        fonts-dejavu-core libcairo2-dev libcurl4-openssl-dev \
        libfontconfig1-dev libfreetype6-dev libfribidi-dev \
        libharfbuzz-dev libicu-dev libpng-dev libssl-dev libxml2-dev \
        libuv1-dev libtiff-dev libjpeg-dev libwebp-dev \
    && curl -fsSL \
        "https://cdn.posit.co/r/debian-12/pkgs/r-${R_VERSION}_1_$(dpkg --print-architecture).deb" \
        -o /tmp/r.deb \
    && apt-get install -y --no-install-recommends /tmp/r.deb \
    && rm -rf /tmp/r.deb /var/lib/apt/lists/*

ENV PATH="/opt/R/${R_VERSION}/bin:${PATH}"

# Posit Package Manager serves precompiled Debian 12 binaries (x86_64), which
# is much faster than compiling from source. Pin a dated snapshot instead of
# "latest" if you want fully reproducible builds, e.g. .../bookworm/2026-11-20

RUN Rscript --vanilla -e 'options(repos = c(CRAN = "https://packagemanager.posit.co/cran/__linux__/bookworm/latest")); \
    install.packages(c("BiocManager", "remotes", "ape", "dplyr", "ggplot2", "jsonlite", "phytools"))'

RUN Rscript --vanilla -e 'options(repos = c(CRAN = "https://packagemanager.posit.co/cran/__linux__/bookworm/latest")); \
    BiocManager::install("ggtree", version = "3.22", ask = FALSE, update = FALSE); \
    stopifnot(requireNamespace("ggtree", quietly = TRUE))'

RUN Rscript --vanilla -e ' \
    remotes::install_github("alrichardbollans/rPDtips", upgrade = "never"); \
    library(rPDtips); \
    print(packageDescription("rPDtips")[c("Version","RemoteSha","RemoteRef")]); \
    cat("EXPORTS:\n"); print(getNamespaceExports("rPDtips")); \
    cat("ALL OBJECTS:\n"); print(ls(asNamespace("rPDtips")))'

# --- Python app ---
WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

RUN pip install --no-cache-dir --no-build-isolation git+https://github.com/alrichardbollans/wcvpy.git
RUN pip install --no-cache-dir --no-build-isolation git+https://github.com/alrichardbollans/phytochempy.git

COPY . .

# Render sets PORT (default 10000); fall back to 7860 elsewhere
EXPOSE 7860

CMD ["sh", "-c", "shiny run app.py --host 0.0.0.0 --port ${PORT:-7860}"]