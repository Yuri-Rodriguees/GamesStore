param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$Message,
    
    [switch]$CommitAll = $false
)

$tag = "v$Version"
$backupDir = "backup"
$requiredFiles = @("uxmod.py", "xcore.py", "datax.py")
$requiredDirs = @("core")

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GAMESSTORE RELEASE v$Version          " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ============================================
# [1/6] Validações
# ============================================
Write-Host ""
Write-Host "[1/6] Validações..." -ForegroundColor Yellow

$missing = @()
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $missing += $file
    }
}
foreach ($dir in $requiredDirs) {
    if (-not (Test-Path $dir -PathType Container)) {
        $missing += $dir
    }
}

if ($missing.Count -gt 0) {
    Write-Host "   X ERRO: Arquivos/pastas faltando: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "   OK Módulos e diretórios encontrados" -ForegroundColor Green

# ============================================
# [2/6] Backup
# ============================================
Write-Host ""
Write-Host "[2/6] Criando backup..." -ForegroundColor Yellow
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

$timestamp = Get-Date -Format "dd-MM-yyyy_HH-mm-ss"
foreach ($file in $requiredFiles) {
    $fileBase = $file.Replace('.py', '')
    $backupFile = "$backupDir/$fileBase-$timestamp.py"
    Copy-Item $file $backupFile -Force
    Write-Host "   OK $file -> $backupFile" -ForegroundColor Green
}

# ============================================
# [3/6] Atualizar version.py
# ============================================
Write-Host ""
Write-Host "[3/6] Atualizando version.py..." -ForegroundColor Yellow
$versionContent = "__version__ = `"$Version`""
[System.IO.File]::WriteAllText("version.py", $versionContent, [System.Text.Encoding]::UTF8)
Write-Host "   OK version.py = $Version" -ForegroundColor Green

# ============================================
# [4/6] Git add
# ============================================
Write-Host ""
Write-Host "[4/6] Adicionando arquivos ao Git..." -ForegroundColor Yellow
git add uxmod.py xcore.py datax.py version.py core/

if ($CommitAll) {
    Write-Host "   AVISO: Adicionando TODOS os arquivos (--all)" -ForegroundColor Yellow
    git add .
}

Write-Host "   OK Arquivos adicionados" -ForegroundColor Green

# ============================================
# [5/6] Commit e Push
# ============================================
Write-Host ""
Write-Host "[5/6] Commit e push..." -ForegroundColor Yellow
$commitMessage = "$tag - $Message"
git commit -m $commitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "   AVISO: Nada para commitar ou erro no commit" -ForegroundColor Yellow
}

git push origin develop
Write-Host "   OK Push para develop concluído" -ForegroundColor Green

# ============================================
# [6/6] Criar e enviar tag
# ============================================
Write-Host ""
Write-Host "[6/6] Criando tag RELEASE..." -ForegroundColor Yellow

# Remover tag local se existir
git tag -d $tag 2>$null

# Criar nova tag
git tag -a $tag -m $commitMessage
Write-Host "   OK Tag $tag criada localmente" -ForegroundColor Green

# Enviar tag
git push origin $tag --force
Write-Host "   OK Tag enviada para GitHub" -ForegroundColor Green

# ============================================
# Aguardar e atualizar
# ============================================
Write-Host ""
Write-Host "Aguardando workflow iniciar (10s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host "Atualizando repositório local..." -ForegroundColor Yellow
git pull origin develop --no-rebase

# ============================================
# Restaurar módulos do backup
# ============================================
Write-Host ""
Write-Host "Restaurando módulos do backup..." -ForegroundColor Yellow
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $fileBase = $file.Replace('.py', '')
        $latestBackup = Get-ChildItem $backupDir -Filter "$fileBase-*.py" | 
                        Sort-Object LastWriteTime -Descending | 
                        Select-Object -First 1
        
        if ($latestBackup) {
            Copy-Item $latestBackup.FullName $file -Force
            Write-Host "   OK $file restaurado" -ForegroundColor Green
        } else {
            Write-Host "   AVISO: Backup de $file não encontrado" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   INFO: $file já existe" -ForegroundColor Gray
    }
}

# ============================================
# Resumo final
# ============================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  OK RELEASE CRIADO COM SUCESSO!        " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Write-Host ""
Write-Host "RESUMO:" -ForegroundColor White
Write-Host "   Tag: $tag" -ForegroundColor Cyan
Write-Host "   Versão: $Version" -ForegroundColor Cyan
Write-Host "   Mensagem: $Message" -ForegroundColor Cyan

Write-Host ""
Write-Host "IMPORTANTE:" -ForegroundColor Yellow
Write-Host "   - Esta versão aparecerá para todos os usuários" -ForegroundColor White
Write-Host "   - Aparece na verificação automática de atualizações" -ForegroundColor White
Write-Host "   - 2 versões serão geradas: Debug (console) e Release" -ForegroundColor White

Write-Host ""
Write-Host "LINKS ÚTEIS:" -ForegroundColor Cyan
Write-Host "   Release: https://github.com/Yuri-Rodriguees/GamesStore/releases/tag/$tag" -ForegroundColor White
Write-Host "   Actions: https://github.com/Yuri-Rodriguees/GamesStore/actions" -ForegroundColor White

Write-Host ""
Write-Host "Processo concluído!" -ForegroundColor Green