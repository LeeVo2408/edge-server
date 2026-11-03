# FPV demo: push this laptop's webcam to the edge server over Tailscale.
#
# Usage (PowerShell):
#   .\start-webcam.ps1                       # lists cameras, asks which one
#   .\start-webcam.ps1 -Camera "Integrated Camera"
#   .\start-webcam.ps1 -Edge 100.x.y.z       # if MagicDNS name doesn't resolve
#
# Needs ffmpeg on PATH (winget install Gyan.FFmpeg) and Tailscale connected.
# Press Ctrl+C to stop.

param(
    [string]$Camera = "",
    [string]$Edge = "stev-edgeserver",
    [int]$BitrateK = 2500
)

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Error "ffmpeg not found. Install it with: winget install Gyan.FFmpeg  (then open a new terminal)"
    exit 1
}

if (-not $Camera) {
    Write-Host "Video devices on this laptop:" -ForegroundColor Cyan
    $list = & ffmpeg -hide_banner -list_devices true -f dshow -i dummy 2>&1 | Out-String
    $cams = [regex]::Matches($list, '"([^"]+)" \(video\)') | ForEach-Object { $_.Groups[1].Value }
    if (-not $cams) { Write-Host $list; Write-Error "No cameras found."; exit 1 }
    for ($i = 0; $i -lt $cams.Count; $i++) { Write-Host "  [$i] $($cams[$i])" }
    $pick = Read-Host "Camera number (Enter for 0)"
    if (-not $pick) { $pick = 0 }
    $Camera = $cams[[int]$pick]
}

Write-Host "Checking the edge server is reachable over Tailscale..." -ForegroundColor Cyan
& tailscale ping -c 1 $Edge
if ($LASTEXITCODE -ne 0) { Write-Warning "tailscale ping failed - check Tailscale is connected on both machines." }

$url = "rtsp://${Edge}:8554/live"
Write-Host "Streaming '$Camera' -> $url  (Ctrl+C to stop)" -ForegroundColor Green

# WebRTC-friendly H.264: baseline profile, no B-frames, keyframe every second.
# -an: the vROC panel is video-only; audio goes over the RoIP path instead.
& ffmpeg -hide_banner -loglevel warning `
    -f dshow -rtbufsize 100M -i "video=$Camera" `
    -vf "scale=1280:-2,fps=30" `
    -an `
    -c:v libx264 -preset ultrafast -tune zerolatency `
    -profile:v baseline -bf 0 -pix_fmt yuv420p -g 30 `
    -b:v "${BitrateK}k" -maxrate "${BitrateK}k" -bufsize "$($BitrateK / 2)k" `
    -f rtsp -rtsp_transport tcp $url
