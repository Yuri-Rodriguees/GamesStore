param(
    [string]$Message = "Updates e correções"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GAMESSTORE RELEASE ESPECIAL (SEM VERSÃO)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Adicionar e Commitar
Write-Host "`n[1/3] Enviando alterações para o GitHub..." -ForegroundColor Yellow
git add .
git commit -m "$Message"
git push origin develop

if ($LASTEXITCODE -ne 0) {
    Write-Host "   AVISO: Erro ao fazer push ou nada para enviar." -ForegroundColor Yellow
} else {
    Write-Host "   OK Alterações enviadas" -ForegroundColor Green
}

# 2. Trigger Workflow
Write-Host "`n[2/3] Iniciando Workflow..." -ForegroundColor Yellow

# Verificar se gh cli está instalado
if (Get-Command "gh" -ErrorAction SilentlyContinue) {
    Write-Host "   Usando GitHub CLI..." -ForegroundColor Gray
    gh workflow run release-special.yml --ref develop
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   OK Workflow iniciado com sucesso!" -ForegroundColor Green
        Write-Host "`n   Acompanhe em: https://github.com/Yuri-Rodriguees/GamesStore/actions" -ForegroundColor White
    } else {
        Write-Host "   ERRO ao iniciar workflow via CLI." -ForegroundColor Red
    }
} else {
    Write-Host "   AVISO: GitHub CLI (gh) não encontrado." -ForegroundColor Yellow
    Write-Host "   Por favor, inicie manualmente no navegador:" -ForegroundColor White
    Write-Host "   https://github.com/Yuri-Rodriguees/GamesStore/actions/workflows/release-special.yml" -ForegroundColor Cyan
}

Write-Host "`n[3/3] Concluído" -ForegroundColor Green
