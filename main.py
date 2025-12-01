import json
import random
import hashlib
import time
import threading
import paho.mqtt.client as mqtt
import sys

#Alunos: Lucas Silva Braga e Davi Vittore Loriato

class DistributedMinerWithTimeout:
    def __init__(self, total_nodes, session_id=None, broker_host="broker.hivemq.com", broker_port=1883):
        self.total_nodes = total_nodes
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        # Gera IDs únicos
        self.client_id = random.randint(0, 65535)
        
        #SESSION ID COMPARTILHADO - Todos os nós devem usar o MESMO!
        if session_id is None:
            self.session_id = 1234  # ID fixo para testes
        else:
            self.session_id = session_id
            
        self.vote_id = random.randint(0, 65535)
        
        # Estados do sistema
        self.state = "INIT"
        self.leader_id = None
        self.is_leader = False
        
        # Tabelas
        self.transaction_table = []
        self.mining_table = []
        
        # Coletas -CORREÇÃO: Inclui o próprio ID desde o início
        self.received_init_msgs = set([self.client_id])
        self.received_votes = {}
        
        # Configura MQTT
        unique_id = f"miner_{self.session_id}_{self.client_id}"
        self.client = mqtt.Client(client_id=unique_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
        self.lock = threading.Lock()
        self.current_transaction_id = 0
        
        # TODOS usam o MESMO prefixo de tópico
        self.topic_prefix = f"sd_{self.session_id}"
        
        print(f"Session ID COMPARTILHADO: {self.session_id}")
        
    def _get_topic(self, base_topic):
        return f"{self.topic_prefix}/{base_topic}"
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"Node {self.client_id} conectado e usando Session ID: {self.session_id}")
            
            # Subscreve nos tópicos COMPARTILHADOS
            client.subscribe(self._get_topic("init"))
            client.subscribe(self._get_topic("voting"))
            client.subscribe(self._get_topic("challenge"))
            client.subscribe(self._get_topic("solution"))
            client.subscribe(self._get_topic("result"))
            
            # CORREÇÃO: Publica INIT imediatamente após conectar
            init_msg = {"client_id": self.client_id}
            client.publish(self._get_topic("init"), json.dumps(init_msg))
            print(f" Node {self.client_id} publicou INIT (aguardando {self.total_nodes-1} outros nós)")
        else:
            print(f"Falha na conexão: {rc}")
    
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            
            # Remove prefixo do tópico
            base_topic = topic.replace(f"{self.topic_prefix}/", "")
            
            with self.lock:
                if base_topic == "init" and self.state == "INIT":
                    self._handle_init_message(payload)
                elif base_topic == "voting" and self.state == "ELECTION":
                    self._handle_voting_message(payload)
                elif base_topic == "challenge" and self.state == "CHALLENGE":
                    self._handle_challenge_message(payload)
                elif base_topic == "solution" and self.state == "CHALLENGE" and self.is_leader:
                    self._handle_solution_message(payload)
                elif base_topic == "result" and self.state == "CHALLENGE" and not self.is_leader:
                    self._handle_result_message(payload)
                    
        except Exception as e:
            print(f"Erro ao processar mensagem: {e}")
    
    def _handle_init_message(self, payload):
        sender_id = payload.get("client_id")
        if sender_id not in self.received_init_msgs:
            self.received_init_msgs.add(sender_id)
            print(f"Node {self.client_id} recebeu INIT de {sender_id} "
                  f"({len(self.received_init_msgs)-1}/{self.total_nodes-1} outros nós)")
            
            # CORREÇÃO: Condição fixa - quando temos TOTAL de nós únicos
            if len(self.received_init_msgs) >= self.total_nodes:
                print(f" Node {self.client_id} - TODOS CONECTADOS! Iniciando eleição...")
                self._start_election()
    
    def _handle_voting_message(self, payload):
        sender_id = payload.get("client_id")
        vote_id = payload.get("vote_id")
        
        if sender_id not in self.received_votes:
            self.received_votes[sender_id] = vote_id
            print(f"  Node {self.client_id} recebeu VOTO de {sender_id}: {vote_id} "
                  f"({len(self.received_votes)}/{self.total_nodes})")
            
            if len(self.received_votes) >= self.total_nodes:
                self._finish_election()
    
    def _handle_challenge_message(self, payload):
        transaction_id = payload.get("transaction_id")
        challenge = payload.get("challenge")
        
        print(f"Node {self.client_id} recebeu DESAFIO {transaction_id}: dificuldade {challenge}")
        
        self.mining_table.append({
            "transaction_id": transaction_id,
            "challenge": challenge,
            "solution": "",
            "winner": -1
        })
        
        threading.Thread(target=self._mine, args=(transaction_id, challenge), daemon=True).start()
    
    #Verificando se o transactionID está pendente e se a solução atende aos requisitos do desafio proposto
    def _handle_solution_message(self, payload):
        if not self.is_leader:
            return
            
        sender_id = payload.get("client_id")
        transaction_id = payload.get("transaction_id")
        solution = payload.get("solution")
        
        print(f"Líder {self.client_id} recebeu SOLUÇÃO de {sender_id}")
        #Verifica se a transactionID está pendente
        transaction = next((t for t in self.transaction_table 
                          if t["transaction_id"] == transaction_id and t["winner"] == -1), None)
        
        if transaction and self._verify_solution(solution, transaction["challenge"]):
            transaction["winner"] = sender_id
            transaction["solution"] = solution
            
            result_msg = {
                "client_id": sender_id,
                "transaction_id": transaction_id,
                "solution": solution,
                "result": 1
            }
            self.client.publish(self._get_topic("result"), json.dumps(result_msg))
            print(f"Líder {self.client_id} VALIDOU solução de {sender_id}")
        else:
            result_msg = {
                "client_id": sender_id,
                "transaction_id": transaction_id,
                "solution": solution,
                "result": 0
            }
            self.client.publish(self._get_topic("result"), json.dumps(result_msg))
            print(f"Líder {self.client_id} REJEITOU solução de {sender_id}")
    
    def _handle_result_message(self, payload):
        transaction_id = payload.get("transaction_id")
        result = payload.get("result")
        winner_id = payload.get("client_id")
        
        if result != 0:
            for entry in self.mining_table:
                if entry["transaction_id"] == transaction_id:
                    entry["winner"] = winner_id
                    entry["solution"] = payload.get("solution")
                    print(f"Node {self.client_id} - Transação {transaction_id} RESOLVIDA por {winner_id}")
                    break
    
    def _verify_solution(self, solution, difficulty):
        """Verifica se a solução atende ao desafio"""
        try:
            hash_result = hashlib.sha1(solution.encode()).hexdigest()
            required_prefix = "0" * difficulty
            return hash_result.startswith(required_prefix)
        except:
            return False
    
    def _mine(self, transaction_id, difficulty):
        """Tenta resolver o desafio criptográfico"""
        print(f"Node {self.client_id} INICIOU MINERAÇÃO para transação {transaction_id}")
        
        attempts = 0
        start_time = time.time()
        max_attempts = 50000  # Limite para testes
        
        while attempts < max_attempts:
            # Gera solução candidata
            solution = f"{transaction_id}_{self.client_id}_{attempts}_{random.random()}"
            attempts += 1
            
            # Verifica se atende ao desafio
            if self._verify_solution(solution, difficulty):
                elapsed = time.time() - start_time
                print(f"Node {self.client_id} ENCONTROU SOLUÇÃO para transação {transaction_id}!")
                print(f"Tempo: {elapsed:.2f}s, Tentativas: {attempts}")
                print(f"Solução: {solution[:50]}...")
                
                # Publica solução
                solution_msg = {
                    "client_id": self.client_id,
                    "transaction_id": transaction_id,
                    "solution": solution
                }
                self.client.publish(self._get_topic("solution"), json.dumps(solution_msg))
                break
            
            # Para se já foi resolvido
            transaction_resolved = any(
                t["transaction_id"] == transaction_id and t["winner"] != -1 
                for t in self.mining_table
            )
            if transaction_resolved:
                print(f"Node {self.client_id} parou mineração - transação {transaction_id} já resolvida")
                break
            
            # Pequena pausa para não travar o sistema
            if attempts % 5000 == 0:
                time.sleep(0.1)
        
        if attempts >= max_attempts:
            print(f"Node {self.client_id} atingiu limite de tentativas para transação {transaction_id}")
    
    def _start_election(self):
        """Inicia fase de eleição com timeout"""
        print(f"Node {self.client_id} INICIANDO ELEIÇÃO")
        self.state = "ELECTION"
        
        # Publica seu voto
        vote_msg = {
            "client_id": self.client_id,
            "vote_id": self.vote_id
        }
        self.client.publish(self._get_topic("voting"), json.dumps(vote_msg))
        
        # Adiciona próprio voto
        self.received_votes[self.client_id] = self.vote_id
        print(f"    Votou: {self.vote_id}")
        
        #Timeout para evitar travamento
        def election_timeout():
            time.sleep(10)  # Aguarda 10 segundos
            with self.lock:
                if self.state == "ELECTION" and len(self.received_votes) < self.total_nodes:
                    print(f"  Node {self.client_id} - TIMEOUT na eleição!")
                    print(f"   Votos recebidos: {len(self.received_votes)}/{self.total_nodes}")
                    print("   Forçando conclusão da eleição...")
                    # Força a eleição com os votos que tem
                    if len(self.received_votes) > 0:
                        self._finish_election()
        
        threading.Thread(target=election_timeout, daemon=True).start()
    
    
    def _finish_election(self):
        """Finaliza eleição e determina líder"""
        # Encontra vencedor
        winner = max(self.received_votes.items(), 
                    key=lambda x: (x[1], x[0]))[0]
        
        self.leader_id = winner
        self.is_leader = (self.client_id == winner)
        
        print(f" Node {self.client_id} - ELEIÇÃO CONCLUÍDA!")
        print(f"    Líder eleito: {winner}")
        print(f"    Sou líder: {self.is_leader}")
        
        self.state = "CHALLENGE"
        self._start_challenge_phase()
    
    def _start_challenge_phase(self):
        """Inicia fase de desafios"""
        if self.is_leader:
            print(f" Node {self.client_id} ASSUMINDO COMO LÍDER")
            # Líder começa gerando primeiro desafio
            threading.Timer(2.0, self._generate_new_challenge).start()
        else:
            print(f"  Node {self.client_id} ASSUMINDO COMO MINERADOR")
    
    def _generate_new_challenge(self):
        """Gera novo desafio (apenas líder)"""
        if not self.is_leader:
            return
        
        # Gera desafio com dificuldade baixa para testes
        challenge = random.randint(1, 2)  # 1-2 zeros no hash
        
        transaction_entry = {
            "transaction_id": self.current_transaction_id,
            "challenge": challenge,
            "solution": "",
            "winner": -1
        }
        
        self.transaction_table.append(transaction_entry)
        
        # Publica desafio
        challenge_msg = {
            "transaction_id": self.current_transaction_id,
            "challenge": challenge
        }
        self.client.publish(self._get_topic("challenge"), json.dumps(challenge_msg))
        
        print(f" Líder {self.client_id} PUBLICOU NOVO DESAFIO!")
        print(f"    Transação ID: {self.current_transaction_id}")
        print(f"    Dificuldade: {challenge} zeros no hash SHA-1")
        
        self.current_transaction_id += 1
        
        # Agenda próximo desafio
        if self.current_transaction_id < 3:  # Gera 3 desafios para teste
            threading.Timer(10.0, self._generate_new_challenge).start()
        else:
            print(f" Líder {self.client_id} finalizou geração de desafios")
    
    def start(self):
        """Inicia o nó"""
        print(f" Iniciando Node {self.client_id}")
        print(f" Broker: {self.broker_host}:{self.broker_port}")
        print(f" Session ID COMPARTILHADO: {self.session_id}")
        print(f" Total de nós: {self.total_nodes}")
        
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
           
            def resend_init():
                while self.state == "INIT" and len(self.received_init_msgs) < self.total_nodes:
                    time.sleep(2)
                    init_msg = {"client_id": self.client_id}
                    self.client.publish(self._get_topic("init"), json.dumps(init_msg))
                    print(f" Node {self.client_id} reenviou INIT - Tem {len(self.received_init_msgs)-1}/{self.total_nodes-1} outros")
            
            threading.Thread(target=resend_init, daemon=True).start()
            
            # Menu interativo
            try:
                while True:
                    cmd = input("\n Digite 'status' ou 'quit': ").strip().lower()
                    if cmd == 'status':
                        self.print_status()
                    elif cmd == 'quit':
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n Encerrando...")
                
        except Exception as e:
            print(f" Erro: {e}")
        finally:
            self.client.loop_stop()
    
    def print_status(self):
        """Imprime status atual do nó"""
        print(f"\n=== STATUS Node {self.client_id} ===")
        print(f"Estado: {self.state}")
        print(f"Líder: {self.leader_id} (Sou líder: {self.is_leader})")
        print(f"Session ID: {self.session_id}")
        
        if self.state == "INIT":
            print(f"INITs recebidos: {len(self.received_init_msgs)-1}/{self.total_nodes-1} outros nós")
        elif self.state == "ELECTION":
            print(f"Votos recebidos: {len(self.received_votes)}/{self.total_nodes}")
        elif self.state == "CHALLENGE":
            if self.is_leader:
                print(" Tabela de Transações (Líder):")
                for entry in self.transaction_table:
                    status = " PENDENTE" if entry["winner"] == -1 else f" RESOLVIDO por {entry['winner']}"
                    print(f"  Transação {entry['transaction_id']}: dificuldade {entry['challenge']} - {status}")
            else:
                print(" Tabela de Mineração (Minerador):")
                for entry in self.mining_table:
                    status = "  MINERANDO" if entry["winner"] == -1 else f" RESOLVIDO por {entry['winner']}"
                    print(f"  Transação {entry['transaction_id']}: dificuldade {entry['challenge']} - {status}")

def main():
    if len(sys.argv) < 2:
        print("Uso: python node_fixed_with_timeout.py <total_nodes> [session_id]")
        print(" Exemplo: python node_fixed_with_timeout.py 3 1234")
        sys.exit(1)
    
    total_nodes = int(sys.argv[1])
    
    # Session ID compartilhado - padrão 1234 se não especificado
    session_id = int(sys.argv[2]) if len(sys.argv) >= 3 else 1234
    
    node = DistributedMinerWithTimeout(total_nodes, session_id)
    node.start()

if __name__ == "__main__":
    main()