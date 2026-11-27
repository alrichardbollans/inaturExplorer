FROM docker.io/library/python:3.10@sha256:0a886c151ca7a5deffce7ec5c8b519e75cf238274232119d9d791dc22b0d0fd3
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

ARG R_VERSION=4.5.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential gfortran pkg-config \
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

RUN Rscript --vanilla -e 'options(repos = c(CRAN = "https://cloud.r-project.org")); \
    install.packages(c("BiocManager", "remotes", "ape", "dplyr", "ggplot2", "jsonlite", "phytools"))'

RUN Rscript --vanilla -e 'options(repos = c(CRAN = "https://cloud.r-project.org")); \
    BiocManager::install("ggtree", version = "3.22", ask = FALSE, update = FALSE); \
    stopifnot(requireNamespace("ggtree", quietly = TRUE))'

RUN Rscript --vanilla -e ' \
    remotes::install_github("alrichardbollans/rPDtips", upgrade = "never"); \
    library(rPDtips); \
    print(packageDescription("rPDtips")[c("Version","RemoteSha","RemoteRef")]); \
    cat("EXPORTS:\n"); print(getNamespaceExports("rPDtips")); \
    cat("ALL OBJECTS:\n"); print(ls(asNamespace("rPDtips")))'

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

RUN pip install --no-cache-dir --no-build-isolation git+https://github.com/alrichardbollans/wcvpy.git
RUN pip install --no-cache-dir --no-build-isolation git+https://github.com/alrichardbollans/phytochempy.git

COPY . .

EXPOSE 7860

CMD ["sh", "-c", "shiny run app.py --host 0.0.0.0 --port ${PORT:-7860}"]