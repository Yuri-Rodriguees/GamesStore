param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$Message,
    
    [switch]$CommitAll = $false,
    
    [switch]$CreateOldVersion = $false
)

$backupDir = "backup"
$requiredFiles = @("uxmod.py", "xcore.py", "datax.py")

# Função para calcular versão OLD
function Get-OldVersion {
    param([string]$Version)
    $parts = $Version.Split('.')
    if ($parts.Count -ge 3) {
        $patch = [int]$parts[2]
        $patch = [Math]::Max(0, $patch - 1)
        $parts[2] = $patch.ToString()
        return $parts -join '.'
    }
    return "0.9.9"
}

# Se criar versão OLD, fazer isso primeiro
if ($CreateOldVersion) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host "  CRIANDO VERSAO OLD PRIMEIRO...      " -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta
    
    $oldVersion = Get-OldVersion -Version $Version
    $oldTag = "v$oldVersion-beta-old"
    
    Write-Host ""
    Write-Host "Versao OLD: $oldVersion" -ForegroundColor Cyan
    Write-Host "Tag OLD: $oldTag" -ForegroundColor Cyan
    Write-Host ""
    
    # Criar versão OLD usando o workflow do GitHub via API
    # Primeiro, precisamos fazer commit da versão OLD
    Write-Host "[OLD] Atualizando version.py para OLD..." -ForegroundColor Cyan
    $oldVersionContent = "__version__ = `"$oldVersion-beta-old`""
    [System.IO.File]::WriteAllText("version.py", $oldVersionContent, [System.Text.Encoding]::UTF8)
    Write-Host "   OK version.py = $oldVersion-beta-old" -ForegroundColor Green
    
    Write-Host "[OLD] Adicionando ao Git..." -ForegroundColor Cyan
    if ($CommitAll) {
        Write-Host "   [OLD] Adicionando TODOS os arquivos (--all)" -ForegroundColor Yellow
        git add .
    } else {
        git add version.py
    }
    $oldCommitMessage = "beta-old: $oldTag - Versao antiga para testes de atualizacao"
    git commit -m $oldCommitMessage
    
    if ($LASTEXITCODE -eq 0) {
        git push origin develop
        Write-Host "   OK Push OLD concluido" -ForegroundColor Green
    }
    
    # Criar tag OLD
    Write-Host "[OLD] Criando tag OLD..." -ForegroundColor Cyan
    git tag -d $oldTag 2>$null
    git tag -a $oldTag -m $oldCommitMessage
    git push origin $oldTag --force
    Write-Host "   OK Tag OLD criada: $oldTag" -ForegroundColor Green
    
    # Tentar acionar o workflow OLD via API do GitHub (se token disponível)
    $githubToken = $env:GITHUB_TOKEN
    if (-not $githubToken) {
        $githubToken = $env:GH_TOKEN
    }
    
    if ($githubToken) {
        Write-Host "[OLD] Acionando workflow de build OLD..." -ForegroundColor Cyan
        try {
            $headers = @{
                "Accept" = "application/vnd.github+json"
                "Authorization" = "Bearer $githubToken"
                "X-GitHub-Api-Version" = "2022-11-28"
            }
            
            $body = @{
                ref = "develop"
                inputs = @{
                    version = $oldVersion
                    base_version = $Version
                }
            } | ConvertTo-Json
            
            $response = Invoke-RestMethod -Uri "https://api.github.com/repos/Yuri-Rodriguees/GamesStore/actions/workflows/release-beta-old.yml/dispatches" `
                -Method Post -Headers $headers -Body $body -ContentType "application/json"
            
            Write-Host "   OK Workflow OLD acionado via API" -ForegroundColor Green
        } catch {
            Write-Host "   AVISO: Nao foi possivel acionar workflow via API" -ForegroundColor Yellow
            Write-Host "   Voce precisa acionar manualmente o workflow 'Beta Release OLD'" -ForegroundColor Yellow
            Write-Host "   Link: https://github.com/Yuri-Rodriguees/GamesStore/actions/workflows/release-beta-old.yml" -ForegroundColor Cyan
        }
    } else {
        Write-Host "   AVISO: Token GitHub nao encontrado (GITHUB_TOKEN ou GH_TOKEN)" -ForegroundColor Yellow
        Write-Host "   Voce precisa acionar manualmente o workflow 'Beta Release OLD'" -ForegroundColor Yellow
        Write-Host "   Link: https://github.com/Yuri-Rodriguees/GamesStore/actions/workflows/release-beta-old.yml" -ForegroundColor Cyan
        Write-Host "   Versao OLD: $oldVersion" -ForegroundColor Cyan
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  VERSAO OLD CRIADA!                    " -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Aguardando workflow OLD iniciar (15s)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
    Write-Host ""
    Write-Host "Agora criando versao NEW..." -ForegroundColor Yellow
    Write-Host ""
    Start-Sleep -Seconds 5
}

$tag = "v$Version-beta"
Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  BETA RELEASE v$Version (NAO PUBLICA) " -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

# ============================================
# [1/6] Validacoes
# ============================================
Write-Host ""
Write-Host "[1/6] Validacoes..." -ForegroundColor Cyan
$missing = @()
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $missing += $file
    }
}

if ($missing.Count -gt 0) {
    Write-Host "   X ERRO: Arquivos faltando: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "   OK Modulos encontrados" -ForegroundColor Green

# ============================================
# [2/6] Backup
# ============================================
Write-Host ""
Write-Host "[2/6] Criando backup..." -ForegroundColor Cyan
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
Write-Host "[3/6] Atualizando version.py..." -ForegroundColor Cyan
$versionContent = "__version__ = `"$Version`""
[System.IO.File]::WriteAllText("version.py", $versionContent, [System.Text.Encoding]::UTF8)
Write-Host "   OK version.py = $Version" -ForegroundColor Green

# ============================================
# [4/6] Git add
# ============================================
Write-Host ""
Write-Host "[4/6] Adicionando arquivos ao Git..." -ForegroundColor Cyan
git add uxmod.py xcore.py datax.py version.py

if ($CommitAll) {
    Write-Host "   AVISO: Adicionando TODOS os arquivos (--all)" -ForegroundColor Yellow
    git add .
}

Write-Host "   OK Arquivos adicionados" -ForegroundColor Green

# ============================================
# [5/6] Commit e Push
# ============================================
Write-Host ""
Write-Host "[5/6] Commit e push..." -ForegroundColor Cyan
$commitMessage = "beta: $tag - $Message"
git commit -m $commitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "   AVISO: Nada para commitar ou erro no commit" -ForegroundColor Yellow
}

git push origin develop
Write-Host "   OK Push para develop concluido" -ForegroundColor Green

# ============================================
# [6/6] Criar e enviar tag
# ============================================
Write-Host ""
Write-Host "[6/6] Criando tag BETA..." -ForegroundColor Cyan

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

Write-Host "Atualizando repositorio local..." -ForegroundColor Cyan
git pull origin develop --no-rebase

# ============================================
# Restaurar modulos do backup
# ============================================
Write-Host ""
Write-Host "Restaurando modulos do backup..." -ForegroundColor Cyan
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
            Write-Host "   AVISO: Backup de $file nao encontrado" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   INFO: $file ja existe" -ForegroundColor Gray
    }
}

# ============================================
# Resumo final
# ============================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  OK BETA RELEASE CRIADO COM SUCESSO!   " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Write-Host ""
Write-Host "RESUMO:" -ForegroundColor White
Write-Host "   Tag: $tag" -ForegroundColor Cyan
Write-Host "   Versao: $Version" -ForegroundColor Cyan
Write-Host "   Mensagem: $Message" -ForegroundColor Cyan

Write-Host ""
Write-Host "IMPORTANTE:" -ForegroundColor Yellow
Write-Host "   - Esta versao NAO aparecera para usuarios normais" -ForegroundColor White
Write-Host "   - Apenas quem tiver o link direto pode baixar" -ForegroundColor White
Write-Host "   - Usuarios normais so veem releases STABLE" -ForegroundColor White
Write-Host "   - 2 versoes serao geradas: Debug (console) e Release" -ForegroundColor White

if ($CreateOldVersion) {
    $oldVersion = Get-OldVersion -Version $Version
    Write-Host ""
    Write-Host "TESTE DE ATUALIZACAO:" -ForegroundColor Magenta
    Write-Host "   - Versao OLD criada: v$oldVersion-beta-old" -ForegroundColor White
    Write-Host "   - Versao NEW criada: v$Version-beta" -ForegroundColor White
    Write-Host "   - Para testar: instale a versao OLD primeiro" -ForegroundColor White
    Write-Host "   - A versao OLD detectara automaticamente a NEW como atualizacao" -ForegroundColor White
    Write-Host "   - Link OLD: https://github.com/Yuri-Rodriguees/GamesStore/releases/tag/v$oldVersion-beta-old" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "LINKS UTEIS:" -ForegroundColor Cyan
Write-Host "   Release: https://github.com/Yuri-Rodriguees/GamesStore/releases/tag/$tag" -ForegroundColor White
Write-Host "   Actions: https://github.com/Yuri-Rodriguees/GamesStore/actions" -ForegroundColor White

Write-Host ""
Write-Host "Processo concluido!" -ForegroundColor Green
