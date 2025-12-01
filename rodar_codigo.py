import subprocess
import time
import sys
import os

#Alunos: Lucas Silva Braga e Davi Vittore Loriato

def main():
    print("=" * 50)
    print("SISTEMA DISTRIBUÍDO - VERSÃO CORRIGIDA")
    print("=" * 50)
    
    total_nodes = 3
    session_id = 1234  # Fixo para garantir comunicação
    
    processes = []
    
    print(f"Iniciando {total_nodes} nós com Session ID: {session_id}")
    
    try:
        for i in range(total_nodes):
            print(f"Iniciando nó {i+1}/{total_nodes}...")
            process = subprocess.Popen([
                sys.executable, "main.py", str(total_nodes), str(session_id)
            ])
            processes.append(process)
            time.sleep(4)  # Delay maior para estabilização
            
        print(f"\nTodos os {total_nodes} nós iniciados!")
        print("Agora devem:")
        print("   1. Trocar mensagens INIT automaticamente")
        print("   2. Iniciar eleição quando todos se conectarem")
        print("   3. Líder gerar desafios criptográficos")
        print("   4. Mineradores resolverem desafios")
        print("\n Pressione Ctrl+C para encerrar tudo")
        
        # Mantém rodando
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n Encerrando sistema...")
        for process in processes:
            try:
                process.terminate()
            except:
                pass

if __name__ == "__main__":
    main()