param([ValidateSet('Save', 'Read')][string]$Action = 'Read')

$keyFile = Join-Path (Split-Path -Parent $PSScriptRoot) '.lipsync-api-key.dpapi'
Add-Type -AssemblyName System.Security
if ($Action -eq 'Save') {
    $plainKey = $env:LIPSYNC_API_KEY
    if (-not $plainKey) {
        $secureKey = Read-Host 'Lipsync API key' -AsSecureString
        $plainKey = [System.Net.NetworkCredential]::new('', $secureKey).Password
    }
    if (-not $plainKey) { throw 'API key is empty' }
    $bytes = [Text.Encoding]::UTF8.GetBytes($plainKey)
    $encrypted = [Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Protect($bytes, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser))
    [IO.File]::WriteAllText($keyFile, $encrypted, [Text.Encoding]::ASCII)
    Write-Output 'Encrypted API key saved.'
    return
}
if ($env:LIPSYNC_API_KEY) {
    Write-Output $env:LIPSYNC_API_KEY
    return
}
if (-not (Test-Path -LiteralPath $keyFile -PathType Leaf)) {
    throw 'Encrypted API key file is missing. Run api-key.ps1 -Action Save.'
}
$encrypted = [Convert]::FromBase64String([IO.File]::ReadAllText($keyFile, [Text.Encoding]::ASCII))
$plainKey = [Text.Encoding]::UTF8.GetString([Security.Cryptography.ProtectedData]::Unprotect($encrypted, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser))
if (-not $plainKey) { throw 'Encrypted API key is empty' }
Write-Output $plainKey
