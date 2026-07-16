import os
import shutil
import glob

# Configuration
target_models = ['rongrong', 'meimei', 'binbin', 'lingling', 'baofujie']
dataset_root = "dataset/44k"
logs_root = "logs"

print("Starting cleanup for retraining with ONNX encoder...")

for model in target_models:
    print(f"\nProcessing model: {model}")
    
    # 1. Clean up Dataset Features
    dataset_dir = os.path.join(dataset_root, model)
    if os.path.exists(dataset_dir):
        # Files to remove: .soft.pt is critical (content features). 
        # Removing others ensures consistency.
        extensions = ['*.soft.pt', '*.f0.npy', '*.spec.pt', '*.vol.npy', '*.mel.npy']
        files_to_remove = []
        for ext in extensions:
            files_to_remove.extend(glob.glob(os.path.join(dataset_dir, "**", ext), recursive=True))
        
        if files_to_remove:
            print(f"  Deleting {len(files_to_remove)} feature files in {dataset_dir}...")
            for f in files_to_remove:
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"    Error deleting {f}: {e}")
        else:
            print(f"  No feature files found to delete in {dataset_dir}.")
    else:
        print(f"  Dataset directory not found: {dataset_dir}")

    # 2. Clean up Logs
    log_dir = os.path.join(logs_root, model)
    if os.path.exists(log_dir):
        print(f"  Deleting log directory: {log_dir}...")
        try:
            shutil.rmtree(log_dir)
        except Exception as e:
            print(f"    Error deleting log directory {log_dir}: {e}")
    else:
        print(f"  Log directory not found: {log_dir}")

print("\nCleanup complete.")
print("\n" + "="*50)
print("NEXT STEPS: Execute the following commands in order")
print("="*50)

print("\n1. Preprocess the data (Generate new features with ONNX encoder):")
for model in target_models:
    print(f"python preprocess_hubert_f0.py --config_path configs/{model}.json")

print("\n2. Start Training:")
for model in target_models:
    print(f"python train.py -c configs/{model}.json -m {model}")
