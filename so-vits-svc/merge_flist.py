
import os

def merge_filelists():
    # File paths
    train_luo = r'F:\Python_project\ai_singsong\so-vits-svc\filelists\train_luo.txt'
    val_luo = r'F:\Python_project\ai_singsong\so-vits-svc\filelists\val_luo.txt'
    train_baofujie = r'F:\Python_project\ai_singsong\so-vits-svc\filelists\baofujie_train.txt'
    val_baofujie = r'F:\Python_project\ai_singsong\so-vits-svc\filelists\baofujie_val.txt'
    
    out_train = r'F:\Python_project\ai_singsong\so-vits-svc\filelists\train.txt'
    out_val = r'F:\Python_project\ai_singsong\so-vits-svc\filelists\val.txt'
    
    # Merge train
    lines = []
    if os.path.exists(train_luo):
        with open(train_luo, 'r', encoding='utf-8') as f:
            lines.extend(f.readlines())
    
    if os.path.exists(train_baofujie):
        with open(train_baofujie, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.endswith('|baofujie'):
                    lines.append(f"{line}|baofujie\n")
                elif line:
                    lines.append(f"{line}\n")
                    
    with open(out_train, 'w', encoding='utf-8') as f:
        f.writelines(lines)
        
    # Merge val
    lines = []
    if os.path.exists(val_luo):
        with open(val_luo, 'r', encoding='utf-8') as f:
            lines.extend(f.readlines())
            
    if os.path.exists(val_baofujie):
        with open(val_baofujie, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.endswith('|baofujie'):
                    lines.append(f"{line}|baofujie\n")
                elif line:
                    lines.append(f"{line}\n")
                    
    with open(out_val, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"Merged filelists created: {out_train}, {out_val}")

if __name__ == '__main__':
    merge_filelists()
