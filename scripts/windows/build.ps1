# Build development image on Windows (replaces scripts/build bash script)
# Verifies the locked base image manifest digest before building.

. (Join-Path $PSScriptRoot 'Common.ps1')

Test-EnvFile
Assert-DockerRunning

$baseImage = 'netboxcommunity/netbox:v4.7.0-5.1.1'

$lockedManifests = @{
    'amd64' = 'sha256:fa7ffa268c39fb258bed80bd256360a525f1a129ee4ee06298f10d6708578eba'
    'arm64' = 'sha256:801563a44551e2b05fc6985fc378068a0a4cd1087947bc0ecea073dd0928a3c6'
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

$matched = $false
foreach ($line in $repoDigests) {
    if ($line -and $line.Contains("@$locked")) { $matched = $true; break }
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
