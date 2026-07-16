import os
import glob

dataset_dir = "dataset/44k/rongrong"
if not os.path.exists(dataset_dir):
    print(f"Directory {dataset_dir} does not exist.")
    exit(1)

files = glob.glob(os.path.join(dataset_dir, "*.wav"))
files.sort()

print(f"Found {len(files)} wav files.")

# Delete existing feature files
for ext in ["*.spec.pt", "*.f0.npy", "*.soft.pt", "*.vol.npy"]:
    for f in glob.glob(os.path.join(dataset_dir, ext)):
        try:
            os.remove(f)
        except Exception as e:
            print(f"Error removing {f}: {e}")
print("Deleted existing feature files.")

# Rename wav files
for i, old_path in enumerate(files):
    new_name = f"rongrong_{i}.wav"
    new_path = os.path.join(dataset_dir, new_name)
    try:
        os.rename(old_path, new_path)
        # print(f"Renamed {old_path} -> {new_path}")
    except Exception as e:
        print(f"Error renaming {old_path}: {e}")

print("Done renaming.")
