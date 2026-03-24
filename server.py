import socket, threading, json, time
from logic import Deck, Hand

HOST = '127.0.0.1'
PORT = 65432

class BlackjackServer:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((HOST, PORT))
        self.clients = {} 
        self.deck = Deck()
        self.dealer_hand = Hand()
        self.state = "WAITING" 
        self.current_player_idx = 0
        self.players_order = []

    def broadcast(self, data):
        """Invia un messaggio JSON a tutti i client collegati"""
        msg = (json.dumps(data) + "\n").encode('utf-8')
        for sock in list(self.clients.keys()):
            try: sock.sendall(msg)
            except: self.disconnect(sock)

    def disconnect(self, sock):
        """Gestisce l'uscita o il crash di un giocatore"""
        if sock in self.clients:
            name = self.clients[sock]["name"]
            del self.clients[sock]
            if sock in self.players_order: self.players_order.remove(sock)
            self.send_update(f"{name} ha lasciato il tavolo.")

    def send_update(self, note=""):
        """Invia lo stato completo del tavolo a tutti i client"""
        players_data = []
        for s in self.players_order:
            p = self.clients[s]
            players_data.append({
                "name": p["name"], "balance": p["balance"],
                "hands": [h.to_dict() for h in p["hands"]],
                "active_idx": p["active_idx"]
            })
        
        d_data = self.dealer_hand.to_dict()
        # Nascondi la carta del banco se non è il suo turno
        if self.state in ["BETTING", "PLAYING"] and len(d_data["cards"]) > 1:
            d_data["cards"] = [d_data["cards"][0], {"rank": "hidden", "suit": "hidden"}]
            d_data["value"] = "?"

        self.broadcast({
            "type": "update", "state": self.state,
            "players": players_data, "dealer": d_data,
            "current": self.get_current_name(), "note": note
        })

    def get_current_name(self):
        if self.state == "PLAYING" and self.current_player_idx < len(self.players_order):
            return self.clients[self.players_order[self.current_player_idx]]["name"]
        return "Banco" if self.state == "DEALER_TURN" else ""

    def handle_client(self, sock):
        """Gestisce i messaggi in arrivo da un client specifico"""
        while True:
            try:
                data = sock.recv(4096).decode('utf-8')
                if not data: break
                for line in data.strip().split('\n'):
                    if line: self.process_command(sock, json.loads(line))
            except: break
        self.disconnect(sock)

    def process_command(self, sock, msg):
        """Applica le azioni ricevute dai client"""
        p = self.clients[sock]
        m_type = msg.get("type")

        if m_type == "join":
            p["name"] = msg["name"]
            if sock not in self.players_order: self.players_order.append(sock)
            if self.state == "WAITING": self.state = "BETTING"
            self.send_update(f"{p['name']} è al tavolo.")

        elif m_type == "bet" and self.state == "BETTING":
            try:
                amt, side = int(msg["amount"]), int(msg.get("side", 0))
                if p["balance"] >= (amt + side):
                    p["balance"] -= (amt + side)
                    p["hands"] = [Hand(amt)]
                    p["side_bet"] = side
                    p["ready"] = True
                    self.check_ready()
            except: pass

        elif m_type == "action" and self.state == "PLAYING":
            if self.players_order[self.current_player_idx] == sock:
                self.execute_action(sock, msg["action"])

    def check_ready(self):
        if all(self.clients[s]["ready"] for s in self.players_order):
            self.deal_initial()

    def deal_initial(self):
        self.state = "PLAYING"
        self.dealer_hand = Hand()
        # Distribuzione iniziale delle carte
        for _ in range(2):
            for s in self.players_order: self.clients[s]["hands"][0].add_card(self.deck.draw())
            self.dealer_hand.add_card(self.deck.draw())
        
        # Gestione Perfect Pair side bet
        for s in self.players_order:
            p = self.clients[s]
            mult = p["hands"][0].check_perfect_pair()
            if mult > 0: p["balance"] += p["side_bet"] * mult
            
        self.current_player_idx = 0
        self.send_update("Le carte sono state servite!")

    def execute_action(self, sock, action):
        p = self.clients[sock]
        if not p["hands"]: return
        h = p["hands"][p["active_idx"]]

        if action == "hit":
            h.add_card(self.deck.draw())
            if h.is_bust(): self.next_hand(p)
        elif action == "stand":
            h.is_standing = True
            self.next_hand(p)
        elif action == "double":
            if p["balance"] >= h.bet:
                p["balance"] -= h.bet
                h.bet *= 2
                h.add_card(self.deck.draw())
                h.is_standing = True
                self.next_hand(p)
        elif action == "split":
            if len(h.cards) == 2 and h.cards[0].rank == h.cards[1].rank and p["balance"] >= h.bet:
                p["balance"] -= h.bet
                new_h = Hand(h.bet)
                new_h.add_card(h.cards.pop())
                h.add_card(self.deck.draw())
                new_h.add_card(self.deck.draw())
                p["hands"].append(new_h)
        elif action == "insurance":
            ins_amt = h.bet // 2
            if p["balance"] >= ins_amt:
                p["balance"] -= ins_amt
                h.insurance_bet = ins_amt
        
        self.send_update()

    def next_hand(self, p):
        """Passa alla prossima mano del giocatore o al prossimo giocatore"""
        if p["active_idx"] < len(p["hands"]) - 1:
            p["active_idx"] += 1
        else:
            self.current_player_idx += 1
            if self.current_player_idx >= len(self.players_order):
                threading.Thread(target=self.dealer_play).start()

    def dealer_play(self):
        """Turno automatico del banco"""
        self.state = "DEALER_TURN"
        while self.dealer_hand.get_value() < 17:
            time.sleep(1)
            self.dealer_hand.add_card(self.deck.draw())
            self.send_update()
        self.resolve_round()

    def resolve_round(self):
        """Assegna le vincite e resetta la partita"""
        dv = self.dealer_hand.get_value()
        is_blackjack_dealer = (dv == 21 and len(self.dealer_hand.cards) == 2)

        for s in self.players_order:
            p = self.clients[s]
            for h in p["hands"]:
                # Assicurazione: paga 3:1 (il premio per la puntata laterale)
                if is_blackjack_dealer:
                    p["balance"] += h.insurance_bet * 3
                
                pv = h.get_value()
                if not h.is_bust():
                    if dv > 21 or pv > dv: 
                        p["balance"] += h.bet * 2 # Vittoria
                    elif pv == dv: 
                        p["balance"] += h.bet # Pareggio (Push)
            p["active_idx"] = 0
            p["ready"] = False
        
        self.state = "BETTING"
        self.send_update("Round concluso. Puntate per il prossimo!")

    def run(self):
        print(f"Server Blackjack attivo su {HOST}:{PORT}")
        self.server.listen()
        while True:
            conn, _ = self.server.accept()
            # Stato iniziale di un nuovo client connesso
            self.clients[conn] = {"name": "", "balance": 500, "hands": [], "active_idx": 0, "ready": False, "side_bet": 0}
            threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()

if __name__ == "__main__":
    BlackjackServer().run()
