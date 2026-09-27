# Initialize .env file for development on Windows (replaces scripts/init-env bash script)
# Generates random secrets using .NET RandomNumberGenerator instead of openssl.

. (Join-Path $PSScriptRoot 'Common.ps1')

$target = Get-EnvFile
if (Test-Path $target) {
    Write-Error "Refusing to overwrite existing $target"
    exit 1
}

$dbPassword = New-RandomHex 24
$redisPassword = New-RandomHex 24
$redisCachePassword = New-RandomHex 24
$secretKey = New-RandomHex 48
$apiTokenPepper = New-RandomHex 48

$content = @"
NETBOX_HTTP_PORT=8000
ALLOWED_HOSTS=localhost 127.0.0.1
DB_NAME=netbox
DB_USER=netbox
DB_PASSWORD=$dbPassword
REDIS_PASSWORD=$redisPassword
REDIS_CACHE_PASSWORD=$redisCachePassword
SECRET_KEY=$secretKey
API_TOKEN_PEPPER_1=$apiTokenPepper
SKIP_SUPERUSER=true
CENSUS_REPORTING_ENABLED=false
RELEASE_CHECK_URL=
"@

Set-Content -Path $target -Value $content -Encoding ascii -NoNewline
# Ensure Unix-style line endings (compose env_file parser is fine with CRLF too, but LF is safer)
$content = $content -replace "`r`n", "`n"
[System.IO.File]::WriteAllText($target, $content)

Write-Host "Created $target with random secrets."
