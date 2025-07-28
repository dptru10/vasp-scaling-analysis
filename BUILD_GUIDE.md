# VASP Docker Build Guide

This guide explains how to use the improved `build_docker.sh` script to build and deploy VASP Docker images.

## Prerequisites

1. **Docker**: Must be installed and running
2. **VASP License**: You need a valid VASP license to use the compiled binaries
3. **GCP Setup**: For cloud deployment (optional)

## Quick Start

### Basic Build (Local Only)
```bash
./build_docker.sh
```

### Build with GCP Integration
```bash
# Set your project ID
export PROJECT_ID=vasp-scaling-analysis
./build_docker.sh
```

### Build with Custom Options
```bash
# Custom tag
TAG=v1.0.0 ./build_docker.sh

# With cleanup
CLEANUP=true ./build_docker.sh

# With build arguments
BUILD_ARGS="--build-arg CUDA_VERSION=12.3" ./build_docker.sh
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_ID` | `vasp-scaling-analysis` | GCP Project ID |
| `LOCATION` | `us-central1` | GCP Region |
| `REPO_NAME` | `vasp-repo` | Artifact Registry repository |
| `IMAGE_NAME` | `vasp-pymatgen` | Docker image name |
| `TAG` | `latest` | Docker image tag |
| `BUILD_ARGS` | `""` | Additional Docker build arguments |
| `CLEANUP` | `false` | Clean up old images before building |

## File Requirements

The script checks for these files:
- ✅ `requirements.txt` - Python dependencies
- ✅ `makefile.include.cpu` - CPU build configuration
- ✅ `makefile.include.gpu` - GPU build configuration
- ✅ `Dockerfile` - Docker build instructions
- ✅ `vasp.*.zip` - VASP source code

## Build Process

1. **Validation**: Checks Docker, files, and GCP authentication
2. **Build**: Compiles VASP CPU and GPU versions
3. **Tagging**: Tags for GCP Artifact Registry (if authenticated)
4. **Push**: Optionally pushes to GCP (interactive)

## Troubleshooting

### Docker Issues
```bash
# Check Docker installation
docker --version

# Check Docker daemon
docker info

# Start Docker (macOS)
open -a Docker
```

### GCP Authentication Issues
```bash
# Login to GCP
gcloud auth login

# Set project
gcloud config set project vasp-scaling-analysis

# Verify authentication
gcloud auth list
```

### Build Failures
```bash
# Check build logs
docker build --progress=plain -t vasp-pymatgen:latest .

# Clean build cache
docker system prune -a

# Check available disk space
df -h
```

### VASP Compilation Issues
- Ensure VASP source is valid
- Check makefile configurations
- Verify system dependencies in Dockerfile

## Advanced Usage

### Multi-Architecture Build
```bash
BUILD_ARGS="--platform linux/amd64,linux/arm64" ./build_docker.sh
```

### Build with Cache
```bash
BUILD_ARGS="--build-arg BUILDKIT_INLINE_CACHE=1" ./build_docker.sh
```

### Debug Build
```bash
BUILD_ARGS="--build-arg DEBUG=true" ./build_docker.sh
```

## Security Considerations

1. **VASP License**: Ensure you have proper licensing
2. **GCP Permissions**: Verify Artifact Registry permissions
3. **Image Security**: Regularly update base images
4. **Credential Management**: Use service accounts for production

## Cost Optimization

1. **Local Testing**: Build locally before pushing to GCP
2. **Image Size**: Monitor image size and optimize layers
3. **Caching**: Use build cache to speed up rebuilds
4. **Cleanup**: Use `CLEANUP=true` to remove old images

## Integration with scale.py

After building the image, update `scale.py`:
```python
container_image = 'us-central1-docker.pkg.dev/vasp-scaling-analysis/vasp-repo/vasp-pymatgen:latest'
```

## Support

For issues with:
- **Docker**: Check Docker documentation
- **GCP**: Check Google Cloud documentation
- **VASP**: Contact VASP support
- **Script**: Check this guide and error messages 