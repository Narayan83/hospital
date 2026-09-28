# Looks for HMS-Update.zip (or update.zip) in the updates folder (version is inside the zip).
# Copy ONE file to server D:\HMS\updates - server + clients auto-update on restart.
param([string]$InstallRoot = "")

$ErrorActionPreference = "Continue"
$root = if ($InstallRoot) { (Resolve-Path $InstallRoot).Path } else { Split-Path $PSScriptRoot -Parent }
$config = Join-Path $root "config\hms.env"
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir "update.log"
$checkSummaryFile = Join-Path $logDir "update-check.txt"
$localVersionFile = Join-Path $root "config\VERSION"
$updateFileNames = @("HMS-Update.zip", "update.zip")

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-UpdateLog([string]$Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$stamp] $Message" | Out-File $logFile -Append -Encoding utf8
}

function Write-CheckSummary([string[]]$Lines) {
    # Overwritten each Start HMS - easy file to paste when debugging updates.
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $body = @("HMS update check @ $stamp", "Install root: $root", "") + $Lines
    $body | Set-Content -Path $checkSummaryFile -Encoding utf8
}

function Read-EnvValues([string]$Path) {
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    foreach ($line in Get-Content $Path -Encoding utf8) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { continue }
        $key, $value = $line -split "=", 2
        $values[$key.Trim()] = $value.Trim()
    }
    return $values
}

function Get-InstalledVersion {
    if (-not (Test-Path $localVersionFile)) { return "0.0.0" }
    return (Get-Content $localVersionFile -Raw).Trim()
}

function Compare-Versions([string]$Left, [string]$Right) {
    # Cast each side first. Do NOT write [System.Version]$Left.CompareTo(...) —
    # PowerShell parses that as String.CompareTo(Version), which throws and falls
    # back to string compare ("1.0.10" < "1.0.9") and silently skips real updates.
    try {
        $leftVer = [System.Version]$Left
        $rightVer = [System.Version]$Right
        return $leftVer.CompareTo($rightVer)
    }
    catch {
        return [string]::Compare($Left, $Right, [StringComparison]::OrdinalIgnoreCase)
    }
}

function Get-HostFromBaseUrl([string]$BaseUrl) {
    if (-not $BaseUrl) { return $null }
    if ($BaseUrl -match 'https?://([^/:]+)') {
        $h = $Matches[1].Trim()
        if ($h -and $h -notmatch '^(127\.0\.0\.1|localhost)$') { return $h }
    }
    return $null
}

function Get-ApiBaseUrl([hashtable]$EnvValues) {
    $baseUrl = ($EnvValues["BASE_URL"] -as [string])
    if (-not $baseUrl) { return $null }
    $baseUrl = $baseUrl.Trim().TrimEnd('/')
    if ($baseUrl -notmatch '^https?://') { return $null }
    return $baseUrl
}

function Get-HttpUpdateInfo([string]$BaseUrl) {
    $uri = "$BaseUrl/update/info"
    try {
        return Invoke-RestMethod -Uri $uri -TimeoutSec 15 -ErrorAction Stop
    }
    catch {
        Write-UpdateLog "Update API not reachable ($uri): $_"
        return $null
    }
}

function Save-HttpUpdateZip([string]$BaseUrl, [string]$Destination) {
    $partial = "$Destination.part"
    Remove-Item $partial -Force -ErrorAction SilentlyContinue
    $prevProgress = $ProgressPreference
    # Invoke-WebRequest is roughly 10x slower on multi-MB files with the progress bar on.
    $ProgressPreference = "SilentlyContinue"
    try {
        Invoke-WebRequest -Uri "$BaseUrl/update/download" -OutFile $partial `
            -TimeoutSec 900 -UseBasicParsing -ErrorAction Stop
        Move-Item $partial $Destination -Force -ErrorAction Stop
    }
    finally {
        $ProgressPreference = $prevProgress
        Remove-Item $partial -Force -ErrorAction SilentlyContinue
    }
}

function Test-IsLocalUpdatePath([string]$Path) {
    if (-not $Path) { return $true }
    if ($Path -match '^\\\\') { return $false }
    # Relative or drive path under this install (or default D:\HMS\updates template).
    $norm = $Path.TrimEnd('\')
    $localDefault = (Join-Path $root "updates").TrimEnd('\')
    if ([string]::Equals($norm, $localDefault, [StringComparison]::OrdinalIgnoreCase)) { return $true }
    if ($norm -match '^[A-Za-z]:\\HMS\\updates$') { return $true }
    if ($Path -match '^\./|^\../|^updates$') { return $true }
    return $false
}

function Resolve-UpdateRoot([hashtable]$EnvValues) {
    $path = $EnvValues["UPDATE_PATH"]
    if (-not $path) {
        return Join-Path $root "updates"
    }
    if ($path -match "^\./|^\../") {
        $joined = Join-Path $root $path
        if (Test-Path $joined) {
            return (Resolve-Path $joined).Path
        }
        return [System.IO.Path]::GetFullPath($joined)
    }
    return $path
}

function Get-UpdateSearchRoots([hashtable]$EnvValues, [bool]$IsServerPc) {
    $roots = [System.Collections.Generic.List[string]]::new()
    $primary = Resolve-UpdateRoot $EnvValues
    if ($primary) { $roots.Add($primary) }

    # Clients often still have template UPDATE_PATH=D:\HMS\updates (local empty).
    # Also look at \\<BASE_URL host>\HMSUpdates where the server zip is shared.
    if (-not $IsServerPc) {
        $serverHost = Get-HostFromBaseUrl ($EnvValues["BASE_URL"] -as [string])
        if ($serverHost) {
            $unc = "\\$serverHost\HMSUpdates"
            if (-not ($roots | Where-Object { [string]::Equals($_, $unc, [StringComparison]::OrdinalIgnoreCase) })) {
                $roots.Add($unc)
            }
        }
    }
    return @($roots)
}

function Test-PathQuick([string]$Path, [int]$TimeoutSec = 15) {
    if (-not $Path) { return $false }
    # Local paths are cheap; UNC can hang for 30s+ when the host/share is down.
    if ($Path -notmatch '^\\\\') {
        return Test-Path -LiteralPath $Path
    }
    # Start-Job alone costs ~1s, and a first SMB connection on a slow PC can take
    # several more, so keep this well above the time the probe itself needs.
    $job = Start-Job -ScriptBlock {
        param($p)
        Test-Path -LiteralPath $p
    } -ArgumentList $Path
    try {
        if (Wait-Job $job -Timeout $TimeoutSec) {
            return [bool](Receive-Job $job)
        }
        Write-UpdateLog "Timed out after ${TimeoutSec}s checking: $Path"
        return $false
    }
    finally {
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -Force -ErrorAction SilentlyContinue
    }
}

function Resolve-UpdateZipPath([string[]]$UpdateRoots) {
    foreach ($updateRoot in $UpdateRoots) {
        if (-not $updateRoot) { continue }
        foreach ($name in $updateFileNames) {
            $candidate = Join-Path $updateRoot $name
            # Caller already verified the folder is reachable; zip check is local-speed on UNC once share is up.
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }
    }
    return $null
}

function Test-IsServerPc([hashtable]$EnvValues) {
    $role = ($EnvValues["HMS_ROLE"] -as [string]).Trim().ToLower()
    if ($role -eq "client") { return $false }
    if ($role -eq "server") { return $true }
    $baseUrl = $EnvValues["BASE_URL"]
    if ($baseUrl) {
        return $baseUrl -match "127\.0\.0\.1|localhost"
    }
    $dbUrl = $EnvValues["DATABASE_URL"]
    return $dbUrl -match "@(127\.0\.0\.1|localhost):"
}

function Get-FileSha256([string]$Path) {
    return (Get-FileHash -Path $Path -Algorithm SHA256).Hash
}

function Resolve-HttpUpdateZip {
    # Downloads the server's package into this PC's own updates folder and returns
    # its path, so the rest of the script treats it like any other local zip.
    param(
        [string]$BaseUrl,
        [string]$LocalUpdatesDir,
        [System.Collections.Generic.List[string]]$Summary
    )

    $info = Get-HttpUpdateInfo $BaseUrl
    if (-not $info) {
        $Summary.Add("Server update API: not reachable at $BaseUrl/update/info")
        return $null
    }
    if (-not $info.available) {
        $reason = if ($info.reason) { $info.reason } else { "none" }
        Write-UpdateLog "Server update API reports no package: $reason"
        $Summary.Add("Server update API: no package on server ($reason)")
        return $null
    }

    $sizeMb = [math]::Round($info.size / 1MB, 2)
    Write-UpdateLog "Server update API: version=$($info.version) size=$($info.size) sha256=$($info.sha256)"
    $Summary.Add("Server update API: version $($info.version) ($sizeMb MB)")

    if (-not (Test-Path $LocalUpdatesDir)) {
        New-Item -ItemType Directory -Force -Path $LocalUpdatesDir | Out-Null
    }
    $target = Join-Path $LocalUpdatesDir "HMS-Update.zip"

    # Re-downloading 20 MB on every launch is wasteful; the hash tells us if we already have it.
    if ((Test-Path -LiteralPath $target) -and $info.sha256 -and
        (Get-Item $target).Length -eq $info.size -and
        (Get-FileSha256 $target) -eq $info.sha256) {
        Write-UpdateLog "Already downloaded this package - reusing $target"
        $Summary.Add("Download: skipped (this exact zip is already here)")
        return $target
    }

    Write-Host "Downloading update $($info.version) from server ($sizeMb MB)..." -ForegroundColor Cyan
    Write-UpdateLog "Downloading $BaseUrl/update/download -> $target"
    try {
        Save-HttpUpdateZip $BaseUrl $target
    }
    catch {
        Write-UpdateLog "Download failed: $_"
        $Summary.Add("Download: FAILED - $_")
        return $null
    }

    if ($info.sha256) {
        $actual = Get-FileSha256 $target
        if ($actual -ne $info.sha256) {
            Write-UpdateLog "Downloaded zip is corrupt (expected $($info.sha256), got $actual)"
            $Summary.Add("Download: FAILED - hash mismatch, discarded")
            Remove-Item $target -Force -ErrorAction SilentlyContinue
            return $null
        }
    }

    Write-UpdateLog "Download complete and verified: $target"
    $Summary.Add("Download: OK -> $target")
    return $target
}

function Get-VersionFromZip([string]$ZipPath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = $null
    try {
        $zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        $entry = $zip.Entries | Where-Object {
            $_.FullName -replace '\\', '/' -eq 'config/VERSION'
        } | Select-Object -First 1
        if (-not $entry) { return $null }
        $stream = $entry.Open()
        try {
            $reader = New-Object System.IO.StreamReader($stream)
            return $reader.ReadToEnd().Trim()
        }
        finally {
            $reader.Dispose()
            $stream.Dispose()
        }
    }
    finally {
        if ($zip) { $zip.Dispose() }
    }
}

function Get-ZipEntrySha256([string]$ZipPath, [string]$EntryPath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $normalized = $EntryPath -replace '\\', '/'
    $zip = $null
    $temp = Join-Path $env:TEMP ("hms-hash-" + [guid]::NewGuid().ToString("n"))
    try {
        $zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        $entry = $zip.Entries | Where-Object {
            ($_.FullName -replace '\\', '/') -eq $normalized
        } | Select-Object -First 1
        if (-not $entry) { return $null }
        $stream = $entry.Open()
        try {
            $fs = [System.IO.File]::Open($temp, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
            try {
                $stream.CopyTo($fs)
            }
            finally {
                $fs.Dispose()
            }
        }
        finally {
            $stream.Dispose()
        }
        return Get-FileSha256 $temp
    }
    finally {
        if ($zip) { $zip.Dispose() }
        Remove-Item $temp -Force -ErrorAction SilentlyContinue
    }
}

function Test-CriticalFilesMatchZip([string]$ZipPath, [bool]$IsServerPc) {
    $checks = @(
        @{ Zip = "desktop/HMS Desktop.exe"; Local = (Join-Path $root "desktop\HMS Desktop.exe") }
    )
    if ($IsServerPc) {
        $checks += @{ Zip = "backend/HMS Backend.exe"; Local = (Join-Path $root "backend\HMS Backend.exe") }
    }
    foreach ($check in $checks) {
        if (-not (Test-Path $check.Local)) {
            Write-UpdateLog "Heal check: missing $($check.Local)"
            return $false
        }
        $zipHash = Get-ZipEntrySha256 $ZipPath $check.Zip
        if (-not $zipHash) {
            # Legacy zip layout without onedir paths - skip heal for that entry.
            continue
        }
        $localHash = Get-FileSha256 $check.Local
        if ($localHash -ne $zipHash) {
            Write-UpdateLog "Heal check: hash mismatch for $($check.Zip) (installed=$localHash zip=$zipHash)"
            return $false
        }
    }
    return $true
}

function Assert-FilesMatch([string]$Source, [string]$Destination, [string]$Label) {
    if (-not (Test-Path $Source)) { return }
    if (-not (Test-Path $Destination)) {
        throw "$Label missing after copy: $Destination"
    }
    $srcLen = (Get-Item $Source).Length
    $dstLen = (Get-Item $Destination).Length
    if ($srcLen -ne $dstLen) {
        throw "$Label size mismatch after copy (src=$srcLen dst=$dstLen) - update incomplete."
    }
    $srcHash = Get-FileSha256 $Source
    $dstHash = Get-FileSha256 $Destination
    if ($srcHash -ne $dstHash) {
        throw "$Label hash mismatch after copy - update incomplete (file locked or antivirus restored old file?)."
    }
}

function Stop-HmsProcesses {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    for ($i = 0; $i -lt 3; $i++) {
        taskkill /F /IM "HMS Backend.exe" /T 2>$null | Out-Null
        taskkill /F /IM "HMS Desktop.exe" /T 2>$null | Out-Null
        Get-Process -Name "HMS Backend","HMS Desktop" -ErrorAction SilentlyContinue |
            Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        $still = @(Get-Process -Name "HMS Backend","HMS Desktop" -ErrorAction SilentlyContinue)
        if ($still.Count -eq 0) { break }
        Write-UpdateLog "Still running after kill attempt $($i + 1): $($still.Name -join ', ')"
    }
    $ErrorActionPreference = $prev
}

function Copy-IfExists([string]$Source, [string]$Destination) {
    if (-not (Test-Path $Source)) { return $false }
    $parent = Split-Path $Destination -Parent
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    # Must fail hard - silent copy failures caused "partial update" (VERSION bumped, exe unchanged).
    Copy-Item $Source $Destination -Force -ErrorAction Stop
    return $true
}

function Sync-UpdateTree([string]$SourceRoot, [string]$DestRoot) {
    if (-not (Test-Path $SourceRoot)) { return $false }
    $files = @(Get-ChildItem $SourceRoot -Recurse -File)
    foreach ($file in $files) {
        $rel = $file.FullName.Substring($SourceRoot.Length).TrimStart('\')
        $target = Join-Path $DestRoot $rel
        $parent = Split-Path $target -Parent
        if ($parent -and -not (Test-Path $parent)) {
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
        }
        $attempt = 0
        while ($true) {
            try {
                Copy-Item $file.FullName $target -Force -ErrorAction Stop
                break
            }
            catch {
                $attempt++
                if ($attempt -ge 8) {
                    throw "Failed to copy '$rel' to '$target' (file locked?). Close HMS Desktop/Backend and retry. $_"
                }
                Write-UpdateLog "Retry $attempt copying $rel : $_"
                if ($attempt -eq 3 -or $attempt -eq 6) {
                    Stop-HmsProcesses
                }
                Start-Sleep -Seconds 2
            }
        }
    }
    return $true
}

function Remove-LegacyRootExes([string]$InstallRoot) {
    foreach ($legacy in @("HMS Desktop.exe", "HMS Backend.exe")) {
        $path = Join-Path $InstallRoot $legacy
        if (Test-Path $path) {
            Remove-Item $path -Force -ErrorAction SilentlyContinue
            Write-UpdateLog "Removed legacy root exe: $legacy"
        }
    }
}

function Apply-UpdateZip {
    param(
        [string]$UpdatePath,
        [bool]$IsServerPc
    )

    $temp = Join-Path $env:TEMP ("hms-update-" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Force -Path $temp | Out-Null
    try {
        # UNC zips: copy local first — Expand-Archive on shares is flaky on some PCs.
        $zipForExpand = $UpdatePath
        if ($UpdatePath -match '^\\\\') {
            $zipForExpand = Join-Path $temp "HMS-Update.zip"
            Write-UpdateLog "Copying update zip from share to temp: $UpdatePath"
            Copy-Item -LiteralPath $UpdatePath -Destination $zipForExpand -Force -ErrorAction Stop
        }
        Expand-Archive -Path $zipForExpand -DestinationPath $temp -Force

        $desktopPatch = Join-Path $temp "desktop"
        $backendPatch = Join-Path $temp "backend"
        $hasOnedirPatch = (Test-Path $desktopPatch) -or (Test-Path $backendPatch)

        if ($hasOnedirPatch) {
            if (Test-Path $desktopPatch) {
                Sync-UpdateTree $desktopPatch (Join-Path $root "desktop") | Out-Null
                Assert-FilesMatch `
                    (Join-Path $desktopPatch "HMS Desktop.exe") `
                    (Join-Path $root "desktop\HMS Desktop.exe") `
                    "Desktop exe"
            }
            if ($IsServerPc -and (Test-Path $backendPatch)) {
                Sync-UpdateTree $backendPatch (Join-Path $root "backend") | Out-Null
                Assert-FilesMatch `
                    (Join-Path $backendPatch "HMS Backend.exe") `
                    (Join-Path $root "backend\HMS Backend.exe") `
                    "Backend exe"
            }
            Remove-LegacyRootExes $root
        }
        else {
            # Legacy onefile update zip (pre-onedir) - still apply if present.
            $deskSrc = Join-Path $temp "HMS Desktop.exe"
            $deskDst = Join-Path $root "HMS Desktop.exe"
            if (Copy-IfExists $deskSrc $deskDst) {
                Assert-FilesMatch $deskSrc $deskDst "Desktop exe"
            }
            if ($IsServerPc) {
                $backSrc = Join-Path $temp "HMS Backend.exe"
                $backDst = Join-Path $root "HMS Backend.exe"
                if (Copy-IfExists $backSrc $backDst) {
                    Assert-FilesMatch $backSrc $backDst "Backend exe"
                }
            }
        }

        # Scripts on EVERY PC (server + client) - updater/launchers must stay in sync.
        $scriptsSrc = Join-Path $temp "scripts"
        if (Test-Path $scriptsSrc) {
            Sync-UpdateTree $scriptsSrc (Join-Path $root "scripts") | Out-Null
        }

        if ($IsServerPc) {
            Copy-IfExists (Join-Path $temp "alembic.ini") (Join-Path $root "alembic.ini") | Out-Null
            $alembicSrc = Join-Path $temp "alembic"
            if (Test-Path $alembicSrc) {
                # Copy file-by-file. Copy-Item -Recurse into an existing folder
                # nests a second alembic\alembic and the new migrations never run.
                Sync-UpdateTree $alembicSrc (Join-Path $root "alembic") | Out-Null
            }
        }

        # VERSION last - only after all patches succeed, so a failed exe copy can retry next start.
        $versionSrc = Join-Path $temp "config\VERSION"
        if (-not (Copy-IfExists $versionSrc (Join-Path $root "config\VERSION"))) {
            throw "Update zip missing config\VERSION after extract."
        }
        return $true
    }
    finally {
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Ensure-ServerUpdatesShare([string]$LocalUpdatesDir) {
    if (-not (Test-Path $LocalUpdatesDir)) {
        New-Item -ItemType Directory -Force -Path $LocalUpdatesDir | Out-Null
    }
    try {
        $existing = Get-SmbShare -Name "HMSUpdates" -ErrorAction SilentlyContinue
        if ($existing) {
            Write-UpdateLog "SMB share HMSUpdates already exists -> $($existing.Path)"
            return
        }
    }
    catch {
        # Get-SmbShare missing on very old Windows — ignore.
        Write-UpdateLog "Get-SmbShare not available: $_"
        return
    }
    try {
        New-SmbShare -Name "HMSUpdates" -Path $LocalUpdatesDir -Description "HMS auto-update zip for clients" `
            -ReadAccess "Everyone" -ErrorAction Stop | Out-Null
        Write-UpdateLog "Created SMB share HMSUpdates -> $LocalUpdatesDir (ReadAccess=Everyone)"
        Write-Host "Created network share: \\$env:COMPUTERNAME\HMSUpdates  (for client updates)" -ForegroundColor Green
    }
    catch {
        Write-UpdateLog "Could not create HMSUpdates share (run Start HMS as Administrator once): $_"
        Write-Host "Tip: share D:\HMS\updates as HMSUpdates so clients can auto-update." -ForegroundColor Yellow
    }
}

$envValues = Read-EnvValues $config
$updateRootRaw = $envValues["UPDATE_PATH"]
$localVersion = Get-InstalledVersion
$isServerPc = Test-IsServerPc $envValues
$role = ($envValues["HMS_ROLE"] -as [string])
$baseUrl = ($envValues["BASE_URL"] -as [string])
$searchRoots = Get-UpdateSearchRoots $envValues $isServerPc
$updateRoot = $searchRoots[0]

Write-UpdateLog "===== update check start ====="
Write-UpdateLog "InstallRoot=$root"
Write-UpdateLog "Local VERSION=$localVersion (file=$localVersionFile)"
Write-UpdateLog "HMS_ROLE=$role BASE_URL=$baseUrl serverPc=$isServerPc"
Write-UpdateLog "UPDATE_PATH(raw)='$updateRootRaw' searchRoots=$($searchRoots -join ' | ')"

if ($isServerPc) {
    Ensure-ServerUpdatesShare (Join-Path $root "updates")
}

$summary = [System.Collections.Generic.List[string]]::new()
$updatePathLabel = if ($updateRootRaw) { $updateRootRaw } else { "(empty -> <install>\updates)" }
$summary.Add("Local VERSION: $localVersion")
$summary.Add("UPDATE_PATH (config): $updatePathLabel")
$summary.Add("Search folders: $($searchRoots -join ' | ')")
$summary.Add("Looking for exact names: $($updateFileNames -join ', ')")
$summary.Add("Role: HMS_ROLE=$role  BASE_URL=$baseUrl  treatedAsServer=$isServerPc")

$updatePath = $null

# Clients pull the package over the API they already use for everything else. This
# needs no SMB share, no share permissions and no extra firewall rule, which is why
# it is tried before the shared folder.
if (-not $isServerPc) {
    $apiBase = Get-ApiBaseUrl $envValues
    if ($apiBase) {
        $updatePath = Resolve-HttpUpdateZip $apiBase (Join-Path $root "updates") $summary
    }
    else {
        $summary.Add("Server update API: skipped (BASE_URL is not http://SERVER_IP:8010)")
        Write-UpdateLog "No usable BASE_URL for the update API - falling back to shared folder"
    }
}

if (-not $updatePath) {
    $reachableRoots = [System.Collections.Generic.List[string]]::new()
    foreach ($candidateRoot in $searchRoots) {
        $exists = Test-PathQuick $candidateRoot
        $summary.Add("Folder: $candidateRoot  exists=$exists")
        if (-not $exists) {
            Write-UpdateLog "Updates folder does not exist (or unreachable): $candidateRoot"
            # Never try to create UNC shares; only create local install\updates.
            if ($candidateRoot -notmatch '^\\\\' -and (Test-IsLocalUpdatePath $candidateRoot)) {
                try {
                    New-Item -ItemType Directory -Force -Path $candidateRoot | Out-Null
                    Write-UpdateLog "Created updates folder: $candidateRoot"
                    $summary.Add("  created missing local folder: yes")
                    if (Test-PathQuick $candidateRoot) { $reachableRoots.Add($candidateRoot) }
                }
                catch {
                    Write-UpdateLog "Could not create updates folder: $_"
                    $summary.Add("  created missing folder: FAILED ($_ )")
                }
            }
            elseif ($candidateRoot -match '^\\\\') {
                $summary.Add("  hint: on SERVER share D:\HMS\updates as HMSUpdates (Read for Everyone / hospital users)")
            }
            continue
        }
        $reachableRoots.Add($candidateRoot)
        $folderFiles = @(Get-ChildItem -LiteralPath $candidateRoot -Force -ErrorAction SilentlyContinue)
        if ($folderFiles.Count -eq 0) {
            Write-UpdateLog "Updates folder is EMPTY: $candidateRoot"
            $summary.Add("  contents: (empty)")
        }
        else {
            Write-UpdateLog "Updates folder contents ($($folderFiles.Count) item(s)) at $candidateRoot :"
            $summary.Add("  contents:")
            foreach ($f in $folderFiles) {
                $line = "    $($f.Name)  size=$($f.Length)  modified=$($f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
                Write-UpdateLog $line.Trim()
                $summary.Add($line)
            }
        }
    }

    $updatePath = Resolve-UpdateZipPath @($reachableRoots)
}

if (-not $updatePath) {
    $hintRoots = $searchRoots -join " OR "
    $hint = @(
        "No HMS-Update.zip / update.zip from the server API or in: $hintRoots - skip",
        "On SERVER: copy HMS-Update.zip to D:\HMS\updates (that is all that is needed).",
        "On CLIENT: BASE_URL must be http://SERVER_IP:8010 (not localhost) and the server must be running.",
        "Then close HMS and Start HMS Desktop again.",
        "Common mistakes: server not started, zip named 'HMS-Update (1).zip', old backend without /update/info."
    )
    foreach ($h in $hint) { Write-UpdateLog $h }
    $summary.Add("")
    $summary.Add("RESULT: SKIP - zip not found")
    $summary.Add("Server should have: D:\HMS\updates\HMS-Update.zip")
    $summary.Add("Client looks at: $($searchRoots -join ' , ')")
    $summary.Add("Full log: $logFile")
    Write-CheckSummary $summary.ToArray()
    Write-Host "Update check: no HMS-Update.zip (see logs\update-check.txt)" -ForegroundColor DarkYellow
    exit 0
}

# If we found the zip on the UNC fallback, remember it in config for next start.
$foundRoot = Split-Path $updatePath -Parent
if (-not $isServerPc -and $foundRoot -match '^\\\\' -and (Test-IsLocalUpdatePath $updateRootRaw)) {
    try {
        $lines = Get-Content $config -Encoding utf8
        $wrote = $false
        $out = foreach ($line in $lines) {
            if ($line -match '^\s*UPDATE_PATH\s*=') {
                "UPDATE_PATH=$foundRoot"
                $wrote = $true
            } else { $line }
        }
        if (-not $wrote) { $out = @($out) + "UPDATE_PATH=$foundRoot" }
        $out | Set-Content -Path $config -Encoding utf8
        Write-UpdateLog "Healed client UPDATE_PATH -> $foundRoot (was local/empty template)"
        $summary.Add("Healed UPDATE_PATH in hms.env -> $foundRoot")
    }
    catch {
        Write-UpdateLog "Could not heal UPDATE_PATH in config: $_"
    }
}

Write-UpdateLog "Found zip: $updatePath"
$summary.Add("Found zip: $updatePath")

$remoteVersion = $null
try {
    $remoteVersion = Get-VersionFromZip $updatePath
}
catch {
    Write-UpdateLog "Failed reading config/VERSION from zip: $_"
    $summary.Add("RESULT: SKIP - cannot read zip ($_ )")
    Write-CheckSummary $summary.ToArray()
    exit 0
}

if (-not $remoteVersion) {
    Write-UpdateLog "$(Split-Path $updatePath -Leaf) has no config/VERSION entry - skip"
    $summary.Add("Zip VERSION entry: MISSING (need config/VERSION inside zip)")
    $summary.Add("RESULT: SKIP - bad zip layout")
    Write-CheckSummary $summary.ToArray()
    exit 0
}

Write-UpdateLog "Zip VERSION=$remoteVersion"
$summary.Add("Zip VERSION: $remoteVersion")

$needsUpdate = $false
$cmp = Compare-Versions $remoteVersion $localVersion
Write-UpdateLog "Version compare: zip($remoteVersion) vs local($localVersion) => $cmp (>0 update, 0 same, <0 zip older)"
$summary.Add("Compare: zip vs local => $cmp  (>0=update, 0=same, <0=zip older)")

if ($cmp -gt 0) {
    $needsUpdate = $true
    $summary.Add("Decision: APPLY (zip is newer)")
}
elseif ($cmp -eq 0) {
    # Same VERSION can still mean a partial/failed previous apply (exe never replaced).
    if (-not (Test-CriticalFilesMatchZip $updatePath $isServerPc)) {
        $needsUpdate = $true
        Write-UpdateLog "VERSION already $localVersion but installed files differ from zip - re-applying"
        $summary.Add("Decision: RE-APPLY (same version but exe hash mismatch)")
    }
    else {
        $summary.Add("Decision: SKIP (already up to date, files match)")
    }
}
else {
    $summary.Add("Decision: SKIP (zip version is OLDER than installed)")
    $summary.Add("Rebuild without -NoBump, or bump installer\VERSION, so zip VERSION > $localVersion")
}

if (-not $needsUpdate) {
    Write-UpdateLog "Up to date ($localVersion) - no apply"
    $summary.Add("RESULT: no update applied")
    Write-CheckSummary $summary.ToArray()
    exit 0
}

$summary.Add("RESULT: applying update $localVersion -> $remoteVersion")
Write-CheckSummary $summary.ToArray()

Write-Host ""
Write-Host "HMS update available: $localVersion -> $remoteVersion" -ForegroundColor Yellow
Write-UpdateLog "Update available: $localVersion -> $remoteVersion (server=$isServerPc) zip=$updatePath"

# Missing desktop\ is OK when the zip includes onedir desktop/ — apply restores it
# (common on clients after a bad copy or partial install). Only block legacy zips.
$desktopExe = Join-Path $root "desktop\HMS Desktop.exe"
if (-not (Test-Path $desktopExe)) {
    $zipHasOnedirDesktop = $null -ne (Get-ZipEntrySha256 $updatePath "desktop/HMS Desktop.exe")
    if (-not $zipHasOnedirDesktop) {
        Write-UpdateLog "Missing $desktopExe and zip has no desktop/ onedir - need HMS-Setup.exe once"
        Write-Host "This PC needs a full reinstall (HMS-Setup.exe) before small updates work." -ForegroundColor Red
        $summary.Add("RESULT: BLOCKED - missing $desktopExe (need HMS-Setup.exe once)")
        Write-CheckSummary $summary.ToArray()
        exit 0
    }
    Write-UpdateLog "Missing $desktopExe - restoring from onedir update zip"
    Write-Host "Desktop missing - restoring from update zip..." -ForegroundColor Yellow
}

Stop-HmsProcesses
Start-Sleep -Seconds 1

Write-Host "Applying $(Split-Path $updatePath -Leaf) (app patch)..." -ForegroundColor Cyan
Write-UpdateLog "Applying: $updatePath"
try {
    if (Apply-UpdateZip -UpdatePath $updatePath -IsServerPc $isServerPc) {
        Write-Host "Update applied." -ForegroundColor Green
        Write-UpdateLog "Update applied successfully to $remoteVersion"
        $summary.Add("Apply: SUCCESS -> $remoteVersion")
        Write-CheckSummary $summary.ToArray()
        if ($isServerPc) {
            & (Join-Path $PSScriptRoot "Apply-HMS-Update.ps1") -InstallRoot $root
        }
    }
}
catch {
    $err = "$_"
    Write-UpdateLog "Update FAILED (VERSION not changed - will retry next start): $err"
    Write-Host "Update FAILED: $err" -ForegroundColor Red
    Write-Host "Close all HMS windows, then Start HMS again to retry." -ForegroundColor Yellow
    $summary.Add("Apply: FAILED - $err")
    Write-CheckSummary $summary.ToArray()
}

exit 0
