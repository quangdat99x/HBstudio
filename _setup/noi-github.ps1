# Noi bo tool C:\Tool cua MAY NAY vao repo GitHub chung, de dong bo code voi may kia.
#
#  - May chua co repo (may thu hai, bo tool chep tu truoc): sao luu moi file code khac voi ban tren GitHub
#    vao C:\Tool\_sync_backup\<thoi gian>\ roi lay dung ban tren GitHub. Database, venv, model, du lieu
#    khong bi dung toi (chung khong nam trong Git).
#  - May da co repo nhung chua co remote: chi them remote.
# Chay qua noi-github.bat (bam dup), dan link repo khi duoc hoi.

param([string]$RepoUrl = "")
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Git { & git.exe @args; if ($LASTEXITCODE -ne 0) { throw "git $($args -join ' ') loi (ma $LASTEXITCODE)" } }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Chua cai Git. Chay _setup\cai-git.bat truoc, mo lai cua so nay." -ForegroundColor Red; exit 1
}
if (-not $RepoUrl) { $RepoUrl = Read-Host "Dan link repo GitHub (vd https://github.com/ten-ban/video-tools.git)" }
$RepoUrl = $RepoUrl.Trim()
if ($RepoUrl -notmatch '^https://github\.com/[^/]+/[^/]+?(\.git)?$') { Write-Host "Link khong dung dang https://github.com/<ten>/<repo>" -ForegroundColor Red; exit 1 }

# Lich su Git cu cua tung tool (neu co) cat sang .git-cu, khong xoa
foreach ($d in @("DataBase", "Creater Vid")) {
    $nested = Join-Path $Root "$d\.git"
    if (Test-Path $nested) {
        New-Item -ItemType Directory -Force (Join-Path $Root "$d\.git-cu") | Out-Null
        $dest = Join-Path $Root "$d\.git-cu\git"
        if (Test-Path $dest) { $dest = "$dest-$(Get-Date -Format yyyyMMdd_HHmmss)" }
        Move-Item $nested $dest
        Write-Host "Da cat lich su Git cu cua $d sang $dest"
    }
}

if (-not (Test-Path (Join-Path $Root ".git"))) {
    Invoke-Git init -q -b main
}
Invoke-Git config user.name $env:COMPUTERNAME
# commit can khi co email; may chua tung dung Git thi chua co, dat mot dia chi theo ten may cho rieng repo nay
& git config user.email *> $null
if ($LASTEXITCODE -ne 0) { Invoke-Git config user.email "$($env:COMPUTERNAME.ToLower())@tool.local" }
Invoke-Git config core.autocrlf false
Invoke-Git config core.quotepath false
$hasOrigin = (& git remote) -contains "origin"
if ($hasOrigin) { Invoke-Git remote set-url origin $RepoUrl } else { Invoke-Git remote add origin $RepoUrl }

Write-Host "Dang tai ban code tren GitHub (lan dau co the mo trinh duyet de dang nhap GitHub)..."
Invoke-Git fetch origin
$hasHead = $true
& git rev-parse --verify -q HEAD *> $null; if ($LASTEXITCODE -ne 0) { $hasHead = $false }

if (-not $hasHead) {
    # May thu hai: sao luu file khac ban GitHub roi lay ban GitHub
    $stamp = Get-Date -Format yyyyMMdd_HHmmss
    $backup = Join-Path $Root "_sync_backup\$stamp"
    $files = & git ls-tree -r --name-only origin/main
    $saved = 0
    foreach ($f in $files) {
        $local = Join-Path $Root $f
        if (-not (Test-Path -LiteralPath $local -PathType Leaf)) { continue }
        $remoteHash = (& git rev-parse "origin/main:$f").Trim()
        $localHash = (& git hash-object -- "$local").Trim()
        if ($remoteHash -ne $localHash) {
            $dst = Join-Path $backup $f
            New-Item -ItemType Directory -Force (Split-Path -Parent $dst) | Out-Null
            Copy-Item -LiteralPath $local $dst
            $saved++
        }
    }
    Invoke-Git checkout -q -f -B main origin/main
    Invoke-Git branch -q --set-upstream-to=origin/main main
    if ($saved) {
        Write-Host "$saved file code cua may nay khac ban GitHub, ban cu da sao luu o $backup" -ForegroundColor Yellow
        Write-Host "(May nay co sua gi rieng thi nho Claude gop tu thu muc do vao, roi bam Dong bo trong Tool Manager.)"
    }
    Write-Host "Xong: C:\Tool tren may nay da giong ban tren GitHub." -ForegroundColor Green
} else {
    Write-Host "May nay da co repo. Bam 'Dong bo code' trong Tool Manager de day/keo." -ForegroundColor Green
}
Write-Host "Tu gio: sua code o may nao thi bam 'Dong bo code' trong Tool Manager o may do; may kia mo Tool Manager la tu keo ban moi."
