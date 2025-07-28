# VASP Scaling Analysis with Google Cloud Batch

This script performs automated VASP (Vienna Ab initio Simulation Package) scaling analysis using Google Cloud Batch. It creates input files, submits jobs, monitors their completion, and generates performance plots.

## Features

- **Automated VASP Input Generation**: Uses pymatgen to create VASP input files with different k-point configurations and functionals
- **Google Cloud Batch Integration**: Submits jobs to GCP Batch service with proper resource allocation
- **Multi-device Support**: Supports both CPU and GPU runs
- **Performance Monitoring**: Tracks job completion and collects timing data
- **Automated Plotting**: Generates scaling plots and functional comparison charts
- **Error Handling**: Robust error handling for job failures and data collection

## Prerequisites

1. **Google Cloud Project**: You need a GCP project with Batch API enabled
2. **Google Cloud Storage**: A GCS bucket for storing job outputs
3. **Docker Image**: A container image with VASP and pymatgen installed
4. **POSCAR File**: A VASP POSCAR file in the current directory
5. **Python Dependencies**:
   ```
   google-cloud-batch
   google-cloud-storage
   pymatgen
   matplotlib
   custodian
   ```

## Configuration

The script is pre-configured for the `vasp-scaling-analysis` project. The configuration is already set up:

```python
PROJECT_ID = 'vasp-scaling-analysis'  # GCP project ID
LOCATION = 'us-central1'  # GCP region for Batch jobs
BUCKET_NAME = 'vasp-scaling-outputs'  # GCS bucket for outputs
container_image = 'us-central1-docker.pkg.dev/vasp-scaling-analysis/vasp-repo/vasp-pymatgen:latest'
```

## Usage

1. **Prepare your environment**:
   ```bash
   # Install dependencies
   pip install google-cloud-batch google-cloud-storage pymatgen matplotlib custodian
   
   # Set up authentication
   gcloud auth application-default login
   ```

2. **Place your POSCAR file** in the current directory (a sample POSCAR is already included)

3. **Verify GCP setup** (project, bucket, and repository are already created)

4. **Run the analysis**:
   ```bash
   python scale.py
   ```

## What the Script Does

### 1. Input Generation
- Creates VASP input files for different k-point configurations:
  - 2x2x6 (16 k-points)
  - 3x3x9 (72 k-points) 
  - 4x4x12 (100 k-points)
- Supports both PBE and HSE06 functionals
- Generates inputs for both CPU and GPU runs

### 2. Job Submission
- Submits Batch jobs for scaling analysis (1-32 nodes)
- Uses different machine types for CPU vs GPU runs
- Configures proper resource allocation (CPU, memory, accelerators)

### 3. Job Monitoring
- Polls job status every minute
- Handles job failures gracefully
- Provides progress updates

### 4. Data Collection
- Downloads timing data from GCS
- Handles missing data gracefully
- Organizes data for plotting

### 5. Plot Generation
- **figure_a.png**: Scaling performance plot showing time vs nodes for different k-point configurations
- **figure_b.png**: Functional comparison bar chart (PBE vs HSE06)

## Output Files

- `figure_a.png`: Line plot showing VASP scaling performance across different node counts and k-point configurations
- `figure_b.png`: Bar chart comparing PBE vs HSE06 functional performance

## Configuration Options

### K-point Configurations
```python
k_configs = {
    '2x2x6': {'kpts': (2, 2, 6), 'nk': 16},
    '3x3x9': {'kpts': (3, 3, 9), 'nk': 72},
    '4x4x12': {'kpts': (4, 4, 12), 'nk': 100},
}
```

### Node Scaling
```python
nodes_list = [1, 4, 8, 12, 16, 20, 24, 28, 32]
```

### Device Types
```python
devices = ['CPU', 'GPU']
```

### Functionals
```python
functionals = ['PBE', 'HSE06']
```

## Error Handling

The script includes comprehensive error handling for:
- Missing POSCAR file
- Invalid GCP configuration
- Job submission failures
- Missing output data
- Plot generation with incomplete data

## Cost Considerations

- **CPU Jobs**: Use n2-standard-4 instances
- **GPU Jobs**: Use a2-highgpu-1g instances with NVIDIA A100 GPUs
- Monitor your GCP billing to avoid unexpected charges
- Consider running smaller test cases first

## Troubleshooting

### Common Issues

1. **Authentication Error**: Run `gcloud auth application-default login`
2. **Missing POSCAR**: Ensure POSCAR file is in the current directory
3. **Job Failures**: Check GCP Batch console for detailed error messages
4. **Missing Data**: Verify GCS bucket permissions and file paths

### Debug Mode

Add debug prints by modifying the script:
```python
print(f"Debug: Processing {dir_name}")
```

## License

This code is provided as-is for educational and research purposes. Please ensure compliance with VASP licensing terms and Google Cloud usage policies. 