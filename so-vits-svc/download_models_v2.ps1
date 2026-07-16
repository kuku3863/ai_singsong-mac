
$ErrorActionPreference = "Continue"

# Define directories
$pretrainDir = "f:\Python_project\ai_singsong\so-vits-svc\pretrain"
$logs44kDir = "f:\Python_project\ai_singsong\so-vits-svc\logs\44k"

if (!(Test-Path $pretrainDir)) { New-Item -ItemType Directory -Path $pretrainDir }
if (!(Test-Path $logs44kDir)) { New-Item -ItemType Directory -Path $logs44kDir }

# Model URLs
$models = @(
    @{
        Url = "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt"
        Path = Join-Path $pretrainDir "checkpoint_best_legacy_500.pt"
        Name = "ContentVec (checkpoint_best_legacy_500.pt)"
    },
    @{
        Url = "https://huggingface.co/innnky/sovits4/resolve/main/G_0.pth"
        Path = Join-Path $logs44kDir "G_0.pth"
        Name = "G_0.pth"
    },
    @{
        Url = "https://huggingface.co/innnky/sovits4/resolve/main/D_0.pth"
        Path = Join-Path $logs44kDir "D_0.pth"
        Name = "D_0.pth"
    }
)

foreach ($model in $models) {
    Write-Host "Starting download of $($model.Name)..."
    try {
        # Try BITS first (more robust)
        Start-BitsTransfer -Source $model.Url -Destination $model.Path -ErrorAction Stop
        Write-Host "Successfully downloaded $($model.Name) via BITS."
    } catch {
        Write-Host "BITS transfer failed for $($model.Name). Trying Invoke-WebRequest..."
        try {
            Invoke-WebRequest -Uri $model.Url -OutFile $model.Path -TimeoutSec 600
            Write-Host "Successfully downloaded $($model.Name) via Invoke-WebRequest."
        } catch {
            Write-Host "Failed to download $($model.Name). Error: $($_.Exception.Message)"
            Write-Host "Please download manually from: $($model.Url) and place at $($model.Path)"
        }
    }
}
