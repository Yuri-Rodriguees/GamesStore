"""
Utilitários para WinRAR - Download e instalação automática
"""
import os
import sys
import stat
import time
import tempfile
import platform
import subprocess

import requests

from utils import log_message


def find_winrar():
    """Encontra o caminho do WinRAR instalado"""
    winrar_paths = [
        r"C:\Program Files\WinRAR\WinRAR.exe",
        r"C:\Program Files (x86)\WinRAR\WinRAR.exe"
    ]
    
    for path in winrar_paths:
        if os.path.exists(path):
            return path
    
    return None


def download_and_install_winrar(signals=None):
    """
    Baixa e instala o WinRAR PT-BR automaticamente
    
    Args:
        signals: Objeto com signals para emitir progresso (opcional)
    
    Returns:
        str: Caminho do WinRAR instalado ou None se falhar
    """
    try:
        log_message("[WINRAR] Iniciando download e instalação do WinRAR PT-BR...")
        
        # Detectar arquitetura do sistema
        is_64bit = platform.machine().endswith('64') or platform.architecture()[0] == '64bit'
        
        # URL do instalador WinRAR PT-BR (versão mais recente)
        # Tentar múltiplas URLs possíveis
        if is_64bit:
            winrar_urls = [
                "https://www.win-rar.com/fileadmin/winrar-versions/winrar-x64-611br.exe",
                "https://www.rarlab.com/rar/winrar-x64-611br.exe",
                "https://www.win-rar.com/fileadmin/winrar-versions/winrar-x64-700br.exe"  # Versão mais recente
            ]
        else:
            winrar_urls = [
                "https://www.win-rar.com/fileadmin/winrar-versions/wrar611br.exe",
                "https://www.rarlab.com/rar/wrar611br.exe"
            ]
        
        log_message(f"[WINRAR] Arquitetura detectada: {'64-bit' if is_64bit else '32-bit'}")
        
        # Diretório temporário para o instalador
        temp_dir = tempfile.gettempdir()
        installer_path = os.path.join(temp_dir, "winrar_installer.exe")
        
        # Emitir status se tiver signals
        if signals and hasattr(signals, 'status'):
            signals.status.emit("Baixando WinRAR PT-BR...")
        
        # Baixar instalador tentando múltiplas URLs
        download_success = False
        last_error = None
        
        for url_index, winrar_url in enumerate(winrar_urls):
            log_message(f"[WINRAR] Tentando URL {url_index + 1}/{len(winrar_urls)}: {winrar_url}")
            
            max_retries = 2  # Menos tentativas por URL já que temos múltiplas URLs
            for attempt in range(max_retries):
                try:
                    # Headers para simular navegador e evitar bloqueios
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': '*/*',
                        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                        'Referer': 'https://www.win-rar.com/'
                    }
                    
                    response = requests.get(winrar_url, stream=True, timeout=60, headers=headers, allow_redirects=True)
                    response.raise_for_status()
                    
                    # Verificar se o conteúdo é realmente um executável
                    content_type = response.headers.get('content-type', '').lower()
                    if 'html' in content_type or 'text' in content_type:
                        log_message(f"[WINRAR] AVISO: URL retornou HTML ao invés de executável. Tentando próxima URL...")
                        break  # Tentar próxima URL
                    
                    # Verificar magic bytes do arquivo (MZ = executável Windows)
                    first_chunk = b''
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(installer_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                if not first_chunk:
                                    first_chunk = chunk[:2]
                                    # Verificar se começa com MZ (executável Windows)
                                    if first_chunk != b'MZ':
                                        log_message(f"[WINRAR] AVISO: Arquivo não parece ser um executável válido. Magic bytes: {first_chunk.hex()}")
                                        # Continuar mesmo assim, pode ser válido
                                
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Emitir progresso se tiver signals
                                if signals and hasattr(signals, 'progress') and total_size > 0:
                                    progress = int((downloaded / total_size) * 100)
                                    signals.progress.emit(progress)
                    
                    # Verificar se o arquivo foi baixado completamente
                    file_size = os.path.getsize(installer_path)
                    
                    # Verificar tamanho mínimo (WinRAR geralmente tem pelo menos 2MB)
                    if file_size < 2 * 1024 * 1024:
                        log_message(f"[WINRAR] AVISO: Arquivo muito pequeno ({file_size} bytes). Tentando próxima URL...")
                        if os.path.exists(installer_path):
                            os.remove(installer_path)
                        break  # Tentar próxima URL
                    
                    # Verificar se o tamanho corresponde (com tolerância de 1%)
                    if total_size > 0:
                        size_diff = abs(file_size - total_size)
                        size_tolerance = total_size * 0.01  # 1% de tolerância
                        if size_diff > size_tolerance:
                            log_message(f"[WINRAR] AVISO: Tamanho não corresponde exatamente. Esperado: {total_size}, Obtido: {file_size}, Diferença: {size_diff}")
                            # Continuar mesmo assim se o arquivo for grande o suficiente
                    
                    # Verificar magic bytes do arquivo salvo
                    try:
                        with open(installer_path, 'rb') as f:
                            magic = f.read(2)
                            if magic == b'MZ':
                                download_success = True
                                log_message(f"[WINRAR] Download concluído com sucesso: {installer_path} ({file_size} bytes)")
                                break
                            else:
                                log_message(f"[WINRAR] AVISO: Arquivo não é executável válido. Magic bytes: {magic.hex()}")
                                if os.path.exists(installer_path):
                                    os.remove(installer_path)
                                if attempt < max_retries - 1:
                                    continue
                                break  # Tentar próxima URL
                    except Exception as e:
                        log_message(f"[WINRAR] Erro ao verificar arquivo: {e}")
                        if attempt < max_retries - 1:
                            continue
                        break
                    
                except Exception as e:
                    last_error = str(e)
                    log_message(f"[WINRAR] Erro no download da URL {url_index + 1} (tentativa {attempt + 1}/{max_retries}): {e}")
                    if os.path.exists(installer_path):
                        try:
                            os.remove(installer_path)
                        except:
                            pass
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Aguardar antes de tentar novamente
            
            if download_success:
                break
        
        if not download_success:
            raise Exception(f"Falha ao baixar o instalador do WinRAR de todas as URLs. Último erro: {last_error or 'Desconhecido'}")
        
        # Emitir status se tiver signals
        if signals and hasattr(signals, 'status'):
            signals.status.emit("Instalando WinRAR silenciosamente...")
        
        # Verificar se o arquivo existe e é válido antes de instalar
        if not os.path.exists(installer_path):
            raise Exception(f"Instalador não encontrado: {installer_path}")
        
        file_size = os.path.getsize(installer_path)
        if file_size < 2 * 1024 * 1024:
            raise Exception(f"Instalador corrompido ou incompleto: {file_size} bytes")
        
        log_message(f"[WINRAR] Instalador válido: {file_size} bytes")
        
        # Verificar permissões do arquivo
        try:
            # Tentar abrir o arquivo para verificar se não está bloqueado
            with open(installer_path, 'rb') as f:
                f.read(1)  # Ler apenas 1 byte para verificar
            log_message("[WINRAR] Arquivo acessível e legível")
        except PermissionError:
            log_message("[WINRAR] AVISO: Problema de permissão ao acessar arquivo")
            # Tentar remover atributo somente leitura se existir
            try:
                os.chmod(installer_path, stat.S_IWRITE | stat.S_IREAD)
                log_message("[WINRAR] Atributos de arquivo ajustados")
            except Exception as e:
                log_message(f"[WINRAR] Não foi possível ajustar atributos: {e}")
        except Exception as e:
            log_message(f"[WINRAR] AVISO ao verificar arquivo: {e}")
        
        # Instalar silenciosamente
        # Parâmetros: /S = Silent (instalação silenciosa)
        log_message("[WINRAR] Iniciando instalação silenciosa...")
        
        is_frozen = getattr(sys, 'frozen', False)
        creation_flags = 0
        if is_frozen and sys.platform == 'win32':
            creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        
        # Tentar instalar com diferentes métodos
        install_success = False
        install_error = None
        
        # Método 1: Instalação direta
        try:
            log_message("[WINRAR] Tentando instalação direta...")
            proc = subprocess.Popen(
                [installer_path, '/S'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags if creation_flags else 0,
                shell=False
            )
            
            # Aguardar instalação (timeout de 3 minutos)
            return_code = proc.wait(timeout=180)
            
            if return_code == 0:
                install_success = True
                log_message("[WINRAR] Instalação concluída com sucesso (método direto)")
            else:
                log_message(f"[WINRAR] Instalação retornou código: {return_code}")
                
        except subprocess.TimeoutExpired:
            install_error = "Timeout na instalação"
            log_message(f"[WINRAR] {install_error}")
            try:
                proc.kill()
            except:
                pass
        except Exception as e:
            install_error = str(e)
            log_message(f"[WINRAR] Erro na instalação direta: {e}")
        
        # Método 2: Tentar com shell=True se o método 1 falhou
        if not install_success:
            try:
                log_message("[WINRAR] Tentando instalação com shell=True...")
                proc = subprocess.Popen(
                    f'"{installer_path}" /S',
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=creation_flags if creation_flags else 0,
                    shell=True
                )
                
                return_code = proc.wait(timeout=180)
                
                if return_code == 0:
                    install_success = True
                    log_message("[WINRAR] Instalação concluída com sucesso (método shell)")
                else:
                    log_message(f"[WINRAR] Instalação com shell retornou código: {return_code}")
                    
            except subprocess.TimeoutExpired:
                install_error = "Timeout na instalação (método shell)"
                log_message(f"[WINRAR] {install_error}")
                try:
                    proc.kill()
                except:
                    pass
            except Exception as e:
                install_error = str(e)
                log_message(f"[WINRAR] Erro na instalação com shell: {e}")
        
        # Método 3: Tentar executar diretamente sem flags especiais se os anteriores falharam
        if not install_success:
            try:
                log_message("[WINRAR] Tentando instalação sem flags especiais...")
                proc = subprocess.Popen(
                    [installer_path, '/S'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL
                )
                
                return_code = proc.wait(timeout=180)
                
                if return_code == 0:
                    install_success = True
                    log_message("[WINRAR] Instalação concluída com sucesso (método simples)")
                else:
                    stdout, stderr = proc.communicate()
                    log_message(f"[WINRAR] Instalação retornou código: {return_code}")
                    if stderr:
                        log_message(f"[WINRAR] stderr: {stderr.decode('utf-8', errors='ignore')}")
                    
            except subprocess.TimeoutExpired:
                install_error = "Timeout na instalação (método simples)"
                log_message(f"[WINRAR] {install_error}")
                try:
                    proc.kill()
                except:
                    pass
            except Exception as e:
                install_error = str(e)
                log_message(f"[WINRAR] Erro na instalação simples: {e}")
        
        if not install_success:
            raise Exception(f"Falha na instalação do WinRAR: {install_error or 'Erro desconhecido'}")
        
        log_message("[WINRAR] Instalação concluída")
        
        # Limpar instalador temporário
        try:
            if os.path.exists(installer_path):
                os.remove(installer_path)
                log_message("[WINRAR] Instalador temporário removido")
        except Exception as e:
            log_message(f"[WINRAR] Erro ao remover instalador: {e}")
        
        # Aguardar um pouco para garantir que o WinRAR foi instalado
        time.sleep(2)
        
        # Verificar se foi instalado com sucesso
        winrar_path = find_winrar()
        if winrar_path:
            log_message(f"[WINRAR] WinRAR instalado com sucesso: {winrar_path}")
            if signals and hasattr(signals, 'status'):
                signals.status.emit("WinRAR instalado com sucesso!")
            return winrar_path
        else:
            log_message("[WINRAR] AVISO: WinRAR não encontrado após instalação")
            return None
            
    except subprocess.TimeoutExpired:
        log_message("[WINRAR] ERRO: Timeout na instalação")
        if signals and hasattr(signals, 'error'):
            signals.error.emit("Timeout ao instalar WinRAR")
        return None
    except Exception as e:
        log_message(f"[WINRAR] ERRO ao instalar WinRAR: {e}", include_traceback=True)
        if signals and hasattr(signals, 'error'):
            signals.error.emit(f"Erro ao instalar WinRAR: {str(e)}")
        return None


def ensure_winrar_installed(signals=None):
    """
    Garante que o WinRAR está instalado. Se não estiver, baixa e instala automaticamente.
    
    Args:
        signals: Objeto com signals para emitir progresso (opcional)
    
    Returns:
        str: Caminho do WinRAR ou None se não conseguir instalar
    """
    # Verificar se já está instalado
    winrar_path = find_winrar()
    if winrar_path:
        log_message(f"[WINRAR] WinRAR já instalado: {winrar_path}")
        return winrar_path
    
    # Se não estiver, instalar
    log_message("[WINRAR] WinRAR não encontrado. Iniciando instalação automática...")
    return download_and_install_winrar(signals)
