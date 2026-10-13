# Build development image on Windows (replaces scripts/build bash script)
# Verifies the locked base image manifest digest before building.

. (Join-Path $PSScriptRoot 'Common.ps1')

Test-EnvFile
Assert-DockerRunning

$baseImage = 'docker.io/netboxcommunity/netbox:v4.7.2-5.1.1@sha256:3cf9d3bd77aa186233b84d0ea1cf1755581d5e5678fa7d86ec3be62f79d0c643'

$lockedManifests = @{
    'amd64' = 'sha256:4cd4c0349c8c947d8a3214f6b71e6d42243e39f5a1a32fba2eff4d2b895cfbdc'
    'arm64' = 'sha256:37c8a88a4010dcec69215e136bab2ee117e7ea90d37840dc06d564705955d623'
}

try {
    $arch = docker image inspect $baseImage --format '{{.Architecture}}' 2>$null
} catch { $arch = $null }

if (-not $arch -or -not $lockedManifests.ContainsKey($arch)) {
    Write-Error "Unsupported or missing local base image architecture: $arch`nPull the verified base image first: docker pull $baseImage"
    exit 1
}

$locked = $lockedManifests[$arch]
$repoDigests = docker image inspect $baseImage --format '{{join .RepoDigests "\n"}}' 2>$null

$lockedIndex = 'sha256:3cf9d3bd77aa186233b84d0ea1cf1755581d5e5678fa7d86ec3be62f79d0c643'
$matched = $false
foreach ($line in $repoDigests) {
    if ($line -and ($line.EndsWith("@$locked") -or $line.EndsWith("@$lockedIndex"))) { $matched = $true; break }
}

if (-not $matched) {
    Write-Error "Local $baseImage does not match locked $arch manifest $locked`nPull or load the verified base image before building."
    exit 1
}

Write-Host "Base image verified ($arch): $baseImage"
Push-Location (Get-RepoRoot)
try {
    $env:NETBOX_BASE_IMAGE = $baseImage
    docker compose --env-file (Get-EnvFile) -f (Get-DevComposeFile) build netbox
} finally {
    Pop-Location
}
