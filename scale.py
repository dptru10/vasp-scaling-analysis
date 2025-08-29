import os
import time
from google.cloud import batch_v1
from google.cloud import storage
from pymatgen.core import Structure
from pymatgen.io.vasp.sets import MPRelaxSet
from pymatgen.io.vasp.outputs import Outcar
from pymatgen.io.vasp.inputs import Kpoints
import matplotlib.pyplot as plt

# GCP Project and configs
PROJECT_ID = 'vasp-scaling-analysis'  # GCP project ID
LOCATION = 'us-east1'  # GCP region for Batch jobs
BUCKET_NAME = 'vasp-scaling-outputs'  # GCS bucket for outputs
BATCH_CLIENT = batch_v1.BatchServiceClient()
STORAGE_CLIENT = storage.Client()

def validate_config():
    """Validate that required configuration is set."""
    if PROJECT_ID == 'vasp-scaling-analysis':
        print("Using default project ID: vasp-scaling-analysis")
    if BUCKET_NAME == 'vasp-scaling-outputs':
        print("Using default bucket name: vasp-scaling-outputs")
    
    # Check if POSCAR exists
    if not os.path.exists("POSCAR"):
        raise FileNotFoundError("POSCAR file not found. Please ensure POSCAR is in the current directory.")

def load_structure():
    """Load the structure from POSCAR with error handling."""
    try:
        structure = Structure.from_file("POSCAR")
        print(f"Successfully loaded structure with {len(structure)} atoms")
        return structure
    except Exception as e:
        raise Exception(f"Failed to load structure from POSCAR: {e}")

# Load the structure from POSCAR
structure = load_structure()

# Configurations for line plot
k_configs = {
    '2x2x6': {'kpts': (2, 2, 6), 'nk': 16},
    '3x3x9': {'kpts': (3, 3, 9), 'nk': 72},
    '4x4x12': {'kpts': (4, 4, 12), 'nk': 100},
}
nodes_list = [1, 2]  # Start with very small test to verify quotas
devices = ['CPU']  # Focus on CPU jobs since GPU quota is exhausted

# Configurations for bar plot
materials = {'MySystem': structure}
functionals = ['PBE', 'HSE06']
node_for_bar = 1

# Assume these settings
vasp_cpu_cmd = '/usr/local/vasp/bin/vasp_std'
vasp_gpu_cmd = '/usr/local/vasp/bin/vasp_gpu'
gpus_per_node = 4
cpus_per_node = 40
container_image = 'us-central1-docker.pkg.dev/vasp-scaling-analysis/vasp-repo/vasp-pymatgen:latest'  # Docker image

# Function to create input files in a directory
def create_inputs(dir_name, structure, kpts=None, functional='PBE'):
    os.makedirs(dir_name, exist_ok=True)
    
    # Create k-points settings
    if kpts:
        # Convert tuple to density if needed
        if isinstance(kpts, tuple):
            # Estimate density from k-points tuple
            density = kpts[0] * kpts[1] * kpts[2] * 100  # Rough estimate
            user_kpoints_settings = {'grid_density': density}
        else:
            user_kpoints_settings = {'grid_density': kpts}
    else:
        user_kpoints_settings = {'grid_density': 1000}
    
    vis = MPRelaxSet(structure, user_kpoints_settings=user_kpoints_settings)
    
    if functional == 'HSE06':
        vis.incar.update({
            'LHFCALC': True,
            'HFSCREEN': 0.2,
            'AEXX': 0.25,
            'AGGAX': 0.75,
            'AGGAC': 0.75,
            'ALDAC': 0.75,
            'ALGO': 'All'
        })
    vis.incar.update({'NSW': 50, 'IBRION': 2, 'ISIF': 3})
    vis.write_input(dir_name)

# Function to submit a Batch job for a run
def submit_batch_job(dir_name, vasp_cmd, nodes, device):
    ntasks = nodes * gpus_per_node if device == 'GPU' else nodes * cpus_per_node
    
    # Machine type and compute resources - using smaller types to work within quotas
    if device == 'GPU':
        machine_type = 'a2-highgpu-1g'  # 1 A100 GPU, 12 vCPUs, 85GB RAM
        compute_resource = batch_v1.ComputeResource()
        compute_resource.cpu_milli = 12000  # 12 vCPUs
        compute_resource.memory_mib = 87040  # 85GB
    else:
        machine_type = 'n2-standard-4'  # 4 vCPUs, 16GB RAM - much smaller
        compute_resource = batch_v1.ComputeResource()
        compute_resource.cpu_milli = 4000   # 4 vCPUs
        compute_resource.memory_mib = 16384  # 16GB

    job = batch_v1.Job()
    job.name = f'projects/{PROJECT_ID}/locations/{LOCATION}/jobs/{dir_name}'

    task_group = batch_v1.TaskGroup()
    task_spec = batch_v1.TaskSpec()

    runnable = batch_v1.Runnable()
    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = container_image
    runnable.container.commands = [
        'python3', '-c',
        f"""
import os
from custodian.vasp.jobs import VaspJob
from custodian.vasp.handlers import VaspErrorHandler
from custodian.custodian import Custodian
from pymatgen.io.vasp.outputs import Outcar
from google.cloud import storage

os.chdir('{dir_name}')
job = VaspJob('{vasp_cmd}'.split(), final=True, suffix='')
c = Custodian([VaspErrorHandler()], [job], max_errors=10)
c.run()

# Parse time
outcar = Outcar('OUTCAR')
elapsed_time = outcar.run_stats['Total CPU time used (sec)'] / 3600
with open('elapsed_time.txt', 'w') as f:
    f.write(str(elapsed_time))

# Upload to GCS
storage.Client().bucket('{BUCKET_NAME}').blob('{dir_name}/elapsed_time.txt').upload_from_filename('elapsed_time.txt')
"""
    ]

    task_spec.runnables.append(runnable)
    task_spec.max_retry_count = 3

    task_spec.compute_resource = compute_resource

    task_group.task_spec = task_spec
    task_group.task_count = 1  # One task per job; scale via ntasks for MPI if needed

    allocation_policy = batch_v1.AllocationPolicy()
    instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
    instance_policy.machine_type = machine_type
    if device == 'GPU':
        accel = batch_v1.AllocationPolicy.Accelerator()
        accel.type = 'nvidia-tesla-a100'  # Adjust for your GPU
        accel.count = 1  # a2-highgpu-1g only supports 1 GPU
        instance_policy.accelerators.append(accel)
    allocation_policy.instances.append(batch_v1.AllocationPolicy.InstancePolicyOrTemplate(policy=instance_policy))

    job.allocation_policy = allocation_policy
    job.task_groups.append(task_group)

    request = batch_v1.CreateJobRequest(parent=f'projects/{PROJECT_ID}/locations/{LOCATION}', job=job)
    created_job = BATCH_CLIENT.create_job(request)
    print(f'Submitted job: {created_job.name}')
    return created_job.name



def main():
    """Main execution function with error handling."""
    try:
        # Validate configuration
        validate_config()
        
        # Main execution: Create inputs and submit jobs
        job_names = []

        print("Starting VASP scaling analysis...")
        print(f"Project ID: {PROJECT_ID}")
        print(f"Location: {LOCATION}")
        print(f"Bucket: {BUCKET_NAME}")

        # Line plot runs
        print("\nSubmitting line plot jobs...")
        for k_name, k_data in k_configs.items():
            for device in devices:
                for nodes in nodes_list:
                    dir_name = f'run_line_{device}_{k_name}_{nodes}'
                    create_inputs(dir_name, structure, k_data['kpts'])
                    vasp_cmd = vasp_gpu_cmd if device == 'GPU' else vasp_cpu_cmd
                    job_name = submit_batch_job(dir_name, vasp_cmd, nodes, device)
                    job_names.append((dir_name, job_name))

        # Bar plot runs
        print("\nSubmitting bar plot jobs...")
        for functional in functionals:
            dir_name = f'run_bar_{functional}_MySystem'
            create_inputs(dir_name, materials['MySystem'], functional=functional)
            vasp_cmd = vasp_gpu_cmd  # GPU for bar
            job_name = submit_batch_job(dir_name, vasp_cmd, node_for_bar, 'GPU')
            job_names.append((dir_name, job_name))

        print(f"\nSubmitted {len(job_names)} jobs. Waiting for completion...")

        # Wait for all jobs to complete (polling)
        while job_names:
            for i, (dir_name, job_name) in enumerate(job_names[:]):
                job = BATCH_CLIENT.get_job(name=job_name)
                if job.status.state == batch_v1.JobStatus.State.SUCCEEDED:
                    print(f'Job {dir_name} completed.')
                    job_names.pop(i)
                elif job.status.state == batch_v1.JobStatus.State.FAILED:
                    print(f'Job {dir_name} failed.')
                    job_names.pop(i)
            if job_names:
                print(f"Still waiting for {len(job_names)} jobs...")
                time.sleep(60)  # Poll every minute

        print("\nAll jobs completed. Collecting results...")

        # Collect data from GCS
        times_line = {device: {k: [] for k in k_configs} for device in devices}
        for device in devices:
            for k_name in k_configs:
                for nodes in nodes_list:
                    dir_name = f'run_line_{device}_{k_name}_{nodes}'
                    try:
                        blob = STORAGE_CLIENT.bucket(BUCKET_NAME).blob(f'{dir_name}/elapsed_time.txt')
                        if blob.exists():
                            t = float(blob.download_as_text())
                            times_line[device][k_name].append(t)
                        else:
                            print(f"Warning: No elapsed_time.txt found for {dir_name}")
                            times_line[device][k_name].append(None)
                    except Exception as e:
                        print(f"Error reading data for {dir_name}: {e}")
                        times_line[device][k_name].append(None)

        times_bar = {}
        for functional in functionals:
            dir_name = f'run_bar_{functional}_MySystem'
            try:
                blob = STORAGE_CLIENT.bucket(BUCKET_NAME).blob(f'{dir_name}/elapsed_time.txt')
                if blob.exists():
                    times_bar[functional] = float(blob.download_as_text())
                else:
                    print(f"Warning: No elapsed_time.txt found for {dir_name}")
                    times_bar[functional] = None
            except Exception as e:
                print(f"Error reading data for {dir_name}: {e}")
                times_bar[functional] = None

        # Generate plots
        print("\nGenerating plots...")
        
        # Line plot (figure_a.png) - Scaling behavior with nodes
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c']  # Blue, Orange, Green
        markers = ['o', 's', '^']

        for i, (k_name, k_data) in enumerate(k_configs.items()):
            for j, device in enumerate(devices):
                times = times_line[device][k_name]
                # Filter out None values
                valid_indices = [idx for idx, t in enumerate(times) if t is not None]
                if valid_indices:
                    valid_times = [times[idx] for idx in valid_indices]
                    valid_nodes = [nodes_list[idx] for idx in valid_indices]
                    label = f'{device} - {k_name}'
                    ax.plot(valid_nodes, valid_times, 
                            marker=markers[i], 
                            color=colors[i], 
                            linestyle='-' if device == 'CPU' else '--',
                            linewidth=2, 
                            markersize=8,
                            label=label)

        ax.set_xlabel('Number of Nodes', fontsize=12)
        ax.set_ylabel('Time (hours)', fontsize=12)
        ax.set_title('VASP Scaling Performance', fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.set_xscale('log')
        ax.set_yscale('log')
        plt.tight_layout()
        plt.savefig('figure_a.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Bar plot (figure_b.png) - Functional comparison
        fig, ax = plt.subplots(figsize=(8, 6))
        functionals_list = []
        times_list = []

        for functional, elapsed_time in times_bar.items():
            if elapsed_time is not None:
                functionals_list.append(functional)
                times_list.append(elapsed_time)

        if functionals_list:  # Only plot if we have valid data
            bars = ax.bar(functionals_list, times_list, 
                          color=['#1f77b4', '#ff7f0e'], 
                          alpha=0.7, 
                          edgecolor='black', 
                          linewidth=1)

            # Add value labels on top of bars
            for bar, elapsed_time in zip(bars, times_list):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                        f'{elapsed_time:.2f}h', ha='center', va='bottom', fontweight='bold')

            ax.set_xlabel('Functional', fontsize=12)
            ax.set_ylabel('Time (hours)', fontsize=12)
            ax.set_title('VASP Performance: PBE vs HSE06', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            plt.tight_layout()
            plt.savefig('figure_b.png', dpi=300, bbox_inches='tight')
            plt.close()
        else:
            print("Warning: No valid data available for bar plot")

        print("Plots saved as figure_a.png and figure_b.png")
        print("\nVASP scaling analysis completed successfully!")
        
    except Exception as e:
        print(f"Error in main execution: {e}")
        raise

if __name__ == "__main__":
    main()