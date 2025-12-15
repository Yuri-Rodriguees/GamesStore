param(
    [string]$Version = "2.0.0",
    [string]$Message = "Secure Release"
)

# 1. Backup Completo
$backupDir = "../GamesStore_Backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "1. Criando backup em $backupDir..." -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Copy-Item -Path . -Destination $backupDir -Recurse -Force

# 1.5 Atualizar version.py
Write-Host ""
Write-Host "Atualizando version.py para $Version..." -ForegroundColor Yellow
$versionContent = "__version__ = `"$Version`""
[System.IO.File]::WriteAllText("version.py", $versionContent, [System.Text.Encoding]::UTF8)

# 2. Compilação
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "2. Compilando projeto (Cython)..." -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

# Detectar Python do venv
$pythonCmd = "python"
if (Test-Path "venv/Scripts/python.exe") {
    $pythonCmd = ".\venv\Scripts\python.exe"
    Write-Host "Usando Python do venv: $pythonCmd" -ForegroundColor Cyan
} elseif (Test-Path ".venv/Scripts/python.exe") {
    $pythonCmd = ".\.venv\Scripts\python.exe"
    Write-Host "Usando Python do .venv: $pythonCmd" -ForegroundColor Cyan
}

& $pythonCmd setup.py build_ext --inplace

if ($LASTEXITCODE -ne 0) {
    Write-Error "Falha na compilação! Abortando para não perder código fonte."
    exit 1
}

# 3. Limpeza de Código Fonte
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "3. Limpando arquivos fonte (.py)..." -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

# Arquivos .py que DEVEM ser mantidos para o funcionamento básico ou build
$keepFiles = @("main.py", "setup.py", "version.py", "secure_release.ps1")

# Remover .py da raiz
Get-ChildItem -Path . -Filter "*.py" | Where-Object { $keepFiles -notcontains $_.Name } | ForEach-Object {
    Write-Host "Removendo $($_.Name)" -ForegroundColor Gray
    Remove-Item $_.FullName -Force
}

# Remover .py de core (recursivo)
if (Test-Path "core") {
    Get-ChildItem -Path "core" -Filter "*.py" -Recurse | ForEach-Object {
        Write-Host "Removendo $($_.FullName)" -ForegroundColor Gray
        Remove-Item $_.FullName -Force
    }
}

# Remover arquivos .c gerados pelo Cython
Get-ChildItem -Path . -Filter "*.c" -Recurse | Remove-Item -Force
if (Test-Path "build") { Remove-Item -Path "build" -Recurse -Force }
if (Test-Path "venv") { Remove-Item -Path "venv" -Recurse -Force }
if (Test-Path "__pycache__") { Remove-Item -Path "__pycache__" -Recurse -Force }

# 4. Reset do Git
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "4. Resetando repositório Git..." -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

if (Test-Path ".git") {
    Remove-Item -Path ".git" -Recurse -Force -ErrorAction SilentlyContinue
}

git init
git remote add origin https://github.com/Yuri-Rodriguees/GamesStore.git

# Criar .gitignore restritivo
$ignoreContent = @"
# Ignorar fontes Python
*.py
!main.py
!setup.py
!version.py

# Ignorar artefatos de build locais
__pycache__/
*.spec
build/
dist/
*.user
*.log
venv/
.vscode/
.idea/

# Manter binários compilados
!*.pyd
!*.dll
!*.so
"@
Set-Content -Path ".gitignore" -Value $ignoreContent

# Adicionar arquivos
git add .

# Commit
git commit -m "v$Version - $Message (Secure Build)"

# Push (Forçado)
git branch -M develop
Write-Host "Enviando para GitHub (Force Push)..." -ForegroundColor Yellow
git push -f origin develop

# Tag
git tag -a "v$Version" -m "$Message"
git push -f origin "v$Version"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "SUCESSO! Repositório limpo e seguro." -ForegroundColor Green
Write-Host "Código fonte removido. Apenas binários mantidos." -ForegroundColor Green
Write-Host "Backup salvo em: $backupDir" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
