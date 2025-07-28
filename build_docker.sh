#!/bin/bash

# Build script for VASP Docker image
set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"vasp-scaling-analysis"}
LOCATION=${LOCATION:-"us-central1"}
REPO_NAME=${REPO_NAME:-"vasp-repo"}
IMAGE_NAME=${IMAGE_NAME:-"vasp-pymatgen"}
TAG=${TAG:-"latest"}
BUILD_ARGS=${BUILD_ARGS:-""}
CLEANUP=${CLEANUP:-"false"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to validate Docker
validate_docker() {
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi
    
    print_status "Docker validation passed"
}

# Function to validate GCP authentication
validate_gcp() {
    if [[ "$PROJECT_ID" != "vasp-scaling-analysis" ]]; then
        if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
            print_warning "GCP authentication not found. Run 'gcloud auth login' first."
            return 1
        fi
        
        if ! gcloud config get-value project 2>/dev/null | grep -q "$PROJECT_ID"; then
            print_warning "Current GCP project doesn't match PROJECT_ID. Run 'gcloud config set project $PROJECT_ID'"
            return 1
        fi
        
        print_status "GCP validation passed"
        return 0
    fi
    return 1
}

# Function to cleanup old images
cleanup_images() {
    if [[ "$CLEANUP" == "true" ]]; then
        print_warning "Cleaning up old images..."
        docker images "${IMAGE_NAME}:*" --format "table {{.Repository}}:{{.Tag}}" | grep -v "REPOSITORY" | xargs -r docker rmi || true
    fi
}

print_header "VASP Docker Image Builder"

# Validate environment
print_status "Validating environment..."
validate_docker

# Check if required files exist
print_status "Checking required files..."
required_files=("requirements.txt" "makefile.include.cpu" "makefile.include.gpu" "Dockerfile")
for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        print_error "Required file '$file' not found"
        exit 1
    fi
    print_status "✓ Found $file"
done

# Check for VASP source
print_status "Checking VASP source..."
vasp_files=(vasp.*.zip)
if [[ ! -f "${vasp_files[0]}" ]]; then
    print_error "VASP source file (vasp.*.zip) not found"
    print_warning "Please place your VASP source archive in the current directory"
    exit 1
fi
print_status "✓ Found VASP source: ${vasp_files[0]}"

# Show build configuration
print_status "Build configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Location: $LOCATION"
echo "  Repository: $REPO_NAME"
echo "  Image: $IMAGE_NAME:$TAG"
echo "  Build args: $BUILD_ARGS"

# Cleanup if requested
cleanup_images

# Build the Docker image
print_header "Building Docker Image"
print_status "Starting Docker build..."

if docker build $BUILD_ARGS -t "${IMAGE_NAME}:${TAG}" .; then
    print_status "Docker build completed successfully!"
    
    # Validate GCP and tag for Artifact Registry
    if validate_gcp; then
        print_status "Tagging for GCP Artifact Registry..."
        gcp_image="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${TAG}"
        docker tag "${IMAGE_NAME}:${TAG}" "$gcp_image"
        print_status "Image tagged as: $gcp_image"
        
        print_warning "To push to GCP Artifact Registry, run:"
        echo "docker push $gcp_image"
        
        # Ask if user wants to push now
        read -p "Push to GCP Artifact Registry now? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Pushing to GCP Artifact Registry..."
            if docker push "$gcp_image"; then
                print_status "Successfully pushed to GCP Artifact Registry!"
            else
                print_error "Failed to push to GCP Artifact Registry"
                exit 1
            fi
        fi
    else
        print_warning "GCP validation failed. Image built locally only."
        print_warning "To enable GCP integration:"
        echo "  1. Run: gcloud auth login"
        echo "  2. Run: gcloud config set project $PROJECT_ID"
        echo "  3. Re-run this script"
    fi
    
    # Show image info
    print_status "Image details:"
    docker images "${IMAGE_NAME}:${TAG}"
    
    print_header "Build Complete!"
    print_status "Your VASP Docker image is ready!"
    
else
    print_error "Docker build failed!"
    exit 1
fi 