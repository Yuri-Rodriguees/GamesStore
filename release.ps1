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

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GAMESSTORE RELEASE v$Version        " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ============================================
# 0. VALIDAÇÕES
# ============================================
Write-Host "`n[0/6] Validacoes..." -ForegroundColor Yellow

$missing = @()
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $missing += $file
        Write-Host "   Erro: $file nao encontrado!" -ForegroundColor Red
    }
}

if ($missing.Count -gt 0) {
    Write-Host "`n   Arquivos faltando: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}

Write-Host "   OK Todos os modulos encontrados (uxmod.py, xcore.py, datax.py)" -ForegroundColor Green

# ============================================
# 1. BACKUP
# ============================================
Write-Host "`n[1/6] Criando backup dos modulos..." -ForegroundColor Yellow

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

# ============================================
# 2. COMMIT MUDANÇAS EXTRAS (SE -CommitAll)
# ============================================
if ($CommitAll) {
    Write-Host "`n[2/6] Commitando todas as mudancas..." -ForegroundColor Yellow
    git add .
    
    $changes = git status --porcelain
    if ($changes) {
        git commit -m "feat: $Message"
        git push origin develop
        Write-Host "   OK Mudancas commitadas" -ForegroundColor Green
    } else {
        Write-Host "   Info: Nenhuma mudanca" -ForegroundColor Gray
    }
} else {
    Write-Host "`n[2/6] Pulando commit extra (use -CommitAll se necessario)" -ForegroundColor Gray
}

# ============================================
# 3. ATUALIZAR VERSION.PY
# ============================================
Write-Host "`n[3/6] Atualizando version.py..." -ForegroundColor Yellow
"__version__ = `"$Version`"" | Out-File -FilePath "version.py" -Encoding utf8 -NoNewline
Write-Host "   OK version.py = $Version" -ForegroundColor Green

# ============================================
# 4. COMMIT MODULOS + VERSION
# ============================================
Write-Host "`n[4/6] Commit modulos + version.py..." -ForegroundColor Yellow
git add uxmod.py xcore.py datax.py version.py
git commit -m "$tag - $Message"
git push origin develop
Write-Host "   OK Push concluido" -ForegroundColor Green

# ============================================
# 5. CRIAR E ENVIAR TAG (DISPARA WORKFLOW)
# ============================================
Write-Host "`n[5/6] Criando e enviando tag $tag..." -ForegroundColor Yellow

# Deletar tag local se existir
git tag -d $tag 2>$null

# Criar nova tag
git tag $tag
git push origin $tag

Write-Host "   OK Tag $tag enviada" -ForegroundColor Green

# ============================================
# 6. AGUARDAR E RESTAURAR MODULOS
# ============================================
Write-Host "`n[6/6] Aguardando workflow (10s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host "   Sincronizando..." -ForegroundColor Yellow
git pull origin develop

# Restaurar módulos se foram removidos
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $fileBase = $file.Replace('.py', '')
        $latestBackup = Get-ChildItem $backupDir -Filter "$fileBase-*.py" | 
                        Sort-Object LastWriteTime -Descending | 
                        Select-Object -First 1
        
        if ($latestBackup) {
            Copy-Item $latestBackup.FullName $file
            Write-Host "   OK $file restaurado de $($latestBackup.Name)" -ForegroundColor Green
        } else {
            Write-Host "   AVISO: Backup de $file nao encontrado" -ForegroundColor Yellow
        }
    }
}

# ============================================
# CONCLUÍDO
# ============================================
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  RELEASE $tag INICIADO!                " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Write-Host "`nO workflow 'Release Completo' vai:" -ForegroundColor Cyan
Write-Host "  1. Upload uxmod.py, xcore.py, datax.py como artifacts" -ForegroundColor White
Write-Host "  2. Remover modulos do Git" -ForegroundColor White
Write-Host "  3. Compilar uxmod.pyd, xcore.pyd, datax.pyd" -ForegroundColor White
Write-Host "  4. Gerar GamesStore.exe" -ForegroundColor White
Write-Host "  5. Criar release $tag" -ForegroundColor White

Write-Host "`nBackups disponiveis:" -ForegroundColor Cyan
Get-ChildItem $backupDir -Filter "*-*.py" | 
    Select-Object Name, @{Name="Size (KB)";Expression={[math]::Round($_.Length/1KB,2)}}, LastWriteTime | 
    Format-Table -AutoSize

Write-Host "`nAcompanhe em:" -ForegroundColor Cyan
Write-Host "  Actions: https://github.com/Yuri-Rodriguees/GamesStore/actions" -ForegroundColor White
Write-Host "  Release: https://github.com/Yuri-Rodriguees/GamesStore/releases" -ForegroundColor White

Write-Host "`nBuild estimado: 8-12 minutos" -ForegroundColor Yellow
Write-Host "O .exe sera criado automaticamente!" -ForegroundColor Gray
