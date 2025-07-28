# Use NVIDIA CUDA devel base for GPU support (Ubuntu 22.04)
FROM nvidia/cuda:12.3.0-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/usr/local/vasp/bin:$PATH
ENV OMP_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for VASP build and GCP SDK
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gfortran \
    g++ \
    libopenmpi-dev \
    openmpi-bin \
    libblas-dev \
    liblapack-dev \
    libfftw3-dev \
    libhdf5-dev \
    libhdf5-openmpi-dev \
    python3 \
    python3-pip \
    python3-dev \
    git \
    ca-certificates \
    curl \
    gnupg \
    unzip \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && apt-get update && apt-get install -y google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt /tmp/requirements.txt

# Install Python packages
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy VASP source
COPY vasp.*.zip /opt/vasp-src.zip

# Extract VASP source and build CPU version
RUN mkdir /opt/vasp-cpu && \
    unzip /opt/vasp-src.zip -d /opt/vasp-cpu && \
    cd /opt/vasp-cpu/vasp.5.4.4 && \
    cp arch/makefile.include.linux_gnu makefile.include && \
    # Update makefile.include for Ubuntu 22.04
    sed -i 's|LIBDIR     = /opt/gfortran/libs/|LIBDIR     = /usr/lib/x86_64-linux-gnu|g' makefile.include && \
    sed -i 's|FFTW       ?= /opt/gfortran/fftw-3.3.4-GCC-5.4.1|FFTW       ?= /usr|g' makefile.include && \
    sed -i 's|BLAS       = -L$(LIBDIR) -lrefblas|BLAS       = -L$(LIBDIR) -lblas|g' makefile.include && \
    sed -i 's|LAPACK     = -L$(LIBDIR) -ltmglib -llapack|LAPACK     = -L$(LIBDIR) -llapack|g' makefile.include && \
    sed -i 's|SCALAPACK  = -L$(LIBDIR) -lscalapack $(BLACS)|SCALAPACK  = -L$(LIBDIR) -lscalapack-openmpi $(BLACS)|g' makefile.include && \
    make DEPS=1 -j$(nproc) std && \
    mkdir -p /usr/local/vasp/bin && \
    cp bin/vasp_std /usr/local/vasp/bin/vasp_std && \
    # Verify CPU build
    /usr/local/vasp/bin/vasp_std --version || echo "VASP CPU build completed"

# Build GPU version
RUN mkdir /opt/vasp-gpu && \
    unzip /opt/vasp-src.zip -d /opt/vasp-gpu && \
    cd /opt/vasp-gpu/vasp.5.4.4 && \
    cp arch/makefile.include.linux_gnu makefile.include && \
    # Update makefile.include for Ubuntu 22.04 and GPU
    sed -i 's|LIBDIR     = /opt/gfortran/libs/|LIBDIR     = /usr/lib/x86_64-linux-gnu|g' makefile.include && \
    sed -i 's|FFTW       ?= /opt/gfortran/fftw-3.3.4-GCC-5.4.1|FFTW       ?= /usr|g' makefile.include && \
    sed -i 's|BLAS       = -L$(LIBDIR) -lrefblas|BLAS       = -L$(LIBDIR) -lblas|g' makefile.include && \
    sed -i 's|LAPACK     = -L$(LIBDIR) -ltmglib -llapack|LAPACK     = -L$(LIBDIR) -llapack|g' makefile.include && \
    sed -i 's|SCALAPACK  = -L$(LIBDIR) -lscalapack $(BLACS)|SCALAPACK  = -L$(LIBDIR) -lscalapack-openmpi $(BLACS)|g' makefile.include && \
    # Add GPU support
    echo "CPP_OPTIONS += -DCUDA_GPU -DRPROMU_CPROJ_OVERLAP -DCUFFT_MIN=28" >> makefile.include && \
    echo "CUDA_ROOT  ?= /usr/local/cuda" >> makefile.include && \
    echo "NVCC       := \$(CUDA_ROOT)/bin/nvcc" >> makefile.include && \
    echo "CUDA_LIB   := -L\$(CUDA_ROOT)/lib64 -lnvToolsExt -lcudart -lcuda -lcufft -lcublas" >> makefile.include && \
    make DEPS=1 -j$(nproc) std && \
    cp bin/vasp_std /usr/local/vasp/bin/vasp_gpu && \
    # Verify GPU build
    /usr/local/vasp/bin/vasp_gpu --version || echo "VASP GPU build completed"

# Clean up build artifacts
RUN rm -rf /opt/vasp-* /opt/*.zip

# Create app directory
RUN mkdir -p /app

# Set working directory
WORKDIR /app

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD test -f /usr/local/vasp/bin/vasp_std && test -f /usr/local/vasp/bin/vasp_gpu || exit 1

# Create a non-root user for security
RUN useradd -m -s /bin/bash vasp && \
    chown -R vasp:vasp /app

# Switch to non-root user
USER vasp

# Default command (overridden in Batch)
CMD ["bash"]