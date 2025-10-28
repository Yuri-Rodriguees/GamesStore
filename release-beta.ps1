param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$Message,
    
    [switch]$CommitAll = $false
)

$tag = "v$Version-beta"
$backupDir = "backup"
$requiredFiles = @("uxmod.py", "xcore.py", "datax.py")

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  BETA RELEASE v$Version (NÃO PÚBLICA) " -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

# Validações
Write-Host "`n[1/5] Validações..." -ForegroundColor Yellow
$missing = @()
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $missing += $file
    }
}

if ($missing.Count -gt 0) {
    Write-Host "   ERRO: Arquivos faltando: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "   OK Módulos encontrados" -ForegroundColor Green

# Backup
Write-Host "`n[2/5] Backup..." -ForegroundColor Yellow
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

$timestamp = Get-Date -Format "dd-MM-yyyy_HH-mm-ss"
foreach ($file in $requiredFiles) {
    $fileBase = $file.Replace('.py', '')
    $backupFile = "$backupDir/$fileBase-$timestamp.py"
    Copy-Item $file $backupFile
    Write-Host "   OK Backup: $backupFile" -ForegroundColor Green
}

# Atualizar version.py (SEM CANAL)
Write-Host "`n[3/5] Atualizando version.py..." -ForegroundColor Yellow
"__version__ = `"$Version`"" | Out-File -FilePath "version.py" -Encoding utf8 -NoNewline
Write-Host "   OK version.py = $Version" -ForegroundColor Green

# Commit
Write-Host "`n[4/5] Commit..." -ForegroundColor Yellow
git add uxmod.py xcore.py datax.py version.py

if ($CommitAll) {
    git add .
}

git commit -m "beta: $tag - $Message"
git push origin develop
Write-Host "   OK Push concluído" -ForegroundColor Green

# Tag BETA
Write-Host "`n[5/5] Criando tag BETA $tag..." -ForegroundColor Yellow
git tag -d $tag 2>$null
git tag $tag
git push origin $tag
Write-Host "   OK Tag enviada (será marcada como PRERELEASE)" -ForegroundColor Green

# Aguardar workflow
Write-Host "`nAguardando workflow (10s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
git pull origin develop

# Restaurar módulos
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $fileBase = $file.Replace('.py', '')
        $latestBackup = Get-ChildItem $backupDir -Filter "$fileBase-*.py" | 
                        Sort-Object LastWriteTime -Descending | 
                        Select-Object -First 1
        
        if ($latestBackup) {
            Copy-Item $latestBackup.FullName $file
            Write-Host "   OK $file restaurado" -ForegroundColor Green
        }
    }
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  ✅ BETA RELEASE CRIADO!                " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Write-Host "`n⚠️  IMPORTANTE:" -ForegroundColor Yellow
Write-Host "  - Esta versão NÃO aparecerá para usuários normais" -ForegroundColor White
Write-Host "  - Apenas quem tiver o link direto pode baixar" -ForegroundColor White
Write-Host "  - Usuários normais só veem releases STABLE" -ForegroundColor White

Write-Host "`nLink da release:" -ForegroundColor Cyan
Write-Host "  https://github.com/Yuri-Rodriguees/GamesStore/releases/tag/$tag" -ForegroundColor White
