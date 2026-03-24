import socket, threading, json
import customtkinter as ctk

# Impostazione tema
ctk.set_appearance_mode("dark")

# Simboli Unicode per i semi delle carte
SUIT_SYMBOLS = {'hearts': '♥', 'diamonds': '♦', 'clubs': '♣', 'spades': '♠'}

class CardWidget(ctk.CTkFrame):
    """Componente grafico per disegnare una carta da gioco senza immagini esterne"""
    def __init__(self, master, rank, suit, mini=False):
        # Dimensioni diverse per carte grandi (banco) e piccole (giocatori)
        w, h = (65, 95) if mini else (90, 130)
        is_hidden = (rank == "hidden")
        
        super().__init__(master, width=w, height=h, 
                         fg_color="#2c3e50" if is_hidden else "white", 
                         corner_radius=10, border_width=2, 
                         border_color="gold" if is_hidden else "#bdc3c7")
        self.pack_propagate(False)
        
        if is_hidden:
            # Mostra un punto di domanda per la carta coperta del banco
            ctk.CTkLabel(self, text="?", font=("Arial", 36, "bold"), text_color="white").place(relx=0.5, rely=0.5, anchor="center")
        else:
            # Colore rosso per cuori e quadri, blu scuro per fiori e picche
            color = "#e74c3c" if suit in ['hearts', 'diamonds'] else "#2c3e50"
            r = rank.upper()[0] if rank in ["jack", "queen", "king", "ace"] else rank
            
            # Valore in alto a sinistra
            ctk.CTkLabel(self, text=r, font=("Arial", 16, "bold"), text_color=color).place(x=8, y=5)
            # Simbolo grande al centro
            ctk.CTkLabel(self, text=SUIT_SYMBOLS.get(suit, ''), font=("Arial", 32), text_color=color).place(relx=0.5, rely=0.5, anchor="center")
            # Valore in basso a destra
            ctk.CTkLabel(self, text=r, font=("Arial", 16, "bold"), text_color=color).place(relx=1.0, rely=1.0, x=-8, y=-5, anchor="se")

class BlackjackClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Blackjack Multiplayer - Progetto Esame")
        self.geometry("1100x850")
        self.configure(fg_color="#1a472a") # Verde tavolo da gioco
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.my_nick = ""
        self.connected = False
        self.game_over_shown = False
        
        self.setup_login_ui()

    def setup_login_ui(self):
        """Schermata iniziale di login"""
        self.login_frame = ctk.CTkFrame(self, fg_color="#2c3e50", corner_radius=20, border_width=2, border_color="gold")
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(self.login_frame, text="♠ BLACKJACK CASINÒ ♣", font=("Arial", 28, "bold"), text_color="gold").pack(pady=30, padx=50)
        self.nick_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Inserisci il tuo nickname", width=200)
        self.nick_entry.pack(pady=10)
        
        self.join_btn = ctk.CTkButton(self.login_frame, text="ENTRA IN PARTITA", command=self.start_connect, fg_color="#27ae60", font=("Arial", 16, "bold"))
        self.join_btn.pack(pady=20)
        self.error_label = ctk.CTkLabel(self.login_frame, text="", text_color="#e74c3c")
        self.error_label.pack()

    def start_connect(self):
        """Tenta la connessione al server"""
        self.my_nick = self.nick_entry.get().strip()
        if not self.my_nick: return
        
        try:
            self.sock.settimeout(3)
            self.sock.connect(('127.0.0.1', 65432))
            self.sock.settimeout(None)
            self.connected = True
            
            # Invia il comando di join in formato JSON
            msg = json.dumps({"type": "join", "name": self.my_nick}) + "\n"
            self.sock.sendall(msg.encode('utf-8'))
            
            self.login_frame.place_forget()
            self.setup_game_ui()
            # Avvia il thread per ascoltare il server senza bloccare la GUI
            threading.Thread(target=self.listen, daemon=True).start()
        except:
            self.error_label.configure(text="Errore: Server non raggiungibile!")

    def setup_game_ui(self):
        """Inizializza la struttura dell'interfaccia di gioco"""
        # 1. Barra dei comandi inferiore
        self.bar = ctk.CTkFrame(self, height=150, fg_color="#0e2a18", border_width=2, border_color="gold")
        self.bar.pack(side="bottom", fill="x", padx=10, pady=10)
        
        self.bal_label = ctk.CTkLabel(self.bar, text="Saldo: $500", font=("Arial", 22, "bold"), text_color="gold")
        self.bal_label.pack(side="left", padx=20)

        # Contenitore bottoni azione
        self.btn_frame = ctk.CTkFrame(self.bar, fg_color="transparent")
        self.btn_frame.pack(side="right", padx=10)
        self.btns = {}
        for a in ["Carta", "Stai", "Raddoppia", "Split", "Assicura"]:
            btn = ctk.CTkButton(self.btn_frame, text=a.upper(), width=90, state="disabled", 
                                 command=lambda x=a: self.send_action(x), font=("Arial", 13, "bold"))
            btn.pack(side="left", padx=3)
            self.btns[a] = btn

        # Area puntate
        self.bet_ui = ctk.CTkFrame(self.bar, fg_color="transparent")
        self.bet_ui.pack(side="right", padx=10)
        self.bet_val = ctk.CTkEntry(self.bet_ui, width=60); self.bet_val.insert(0, "50"); self.bet_val.pack(side="left", padx=2)
        self.side_val = ctk.CTkEntry(self.bet_ui, width=60); self.side_val.insert(0, "0"); self.side_val.pack(side="left", padx=2)
        ctk.CTkButton(self.bet_ui, text="PUNTA", width=80, command=self.send_bet, fg_color="gold", text_color="black", font=("Arial", 14, "bold")).pack(side="left")

        # 2. Contenitore area di gioco superiore
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Area del Banco
        self.dealer_ui = ctk.CTkFrame(self.main_container, fg_color="#0e2a18", corner_radius=15, border_width=1, border_color="#27ae60")
        self.dealer_ui.pack(fill="x", pady=10)
        self.dealer_label = ctk.CTkLabel(self.dealer_ui, text="BANCO", font=("Arial", 20, "bold"), text_color="white")
        self.dealer_label.pack(pady=5)
        self.dealer_cards = ctk.CTkFrame(self.dealer_ui, fg_color="transparent"); self.dealer_cards.pack(pady=10)
        
        # Messaggi di stato
        self.note_label = ctk.CTkLabel(self.main_container, text="In attesa degli altri giocatori...", font=("Arial", 18, "italic"), text_color="white")
        self.note_label.pack(pady=5)
        
        # Area dove compariranno i giocatori
        self.players_ui = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.players_ui.pack(fill="both", expand=True)

    def send_bet(self): 
        """Invia la puntata al server"""
        msg = {"type": "bet", "amount": self.bet_val.get(), "side": self.side_val.get()}
        self.sock.sendall((json.dumps(msg) + "\n").encode('utf-8'))

    def send_action(self, a):
        """Invia l'azione (Hit, Stand, ecc.) al server"""
        m = {"Carta": "hit", "Stai": "stand", "Raddoppia": "double", "Split": "split", "Assicura": "insurance"}
        self.sock.sendall((json.dumps({"type": "action", "action": m[a]}) + "\n").encode('utf-8'))

    def listen(self):
        """Ciclo di ascolto messaggi dal server"""
        buf = ""
        while True:
            try:
                data = self.sock.recv(4096).decode('utf-8')
                if not data: break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if line.strip(): 
                        # Aggiorna la UI nel thread principale
                        self.after(0, self.refresh, json.loads(line))
            except: break

    def refresh(self, data):
        """Aggiorna l'intera interfaccia con i dati ricevuti dal server"""
        if data["type"] != "update": return
        
        # 1. Aggiorna note e banco
        self.note_label.configure(text=data["note"].upper())
        self.dealer_label.configure(text=f"BANCO (Punti: {data['dealer']['value']})")
        
        for w in self.dealer_cards.winfo_children(): w.destroy()
        for c in data["dealer"]["cards"]: 
            CardWidget(self.dealer_cards, c["rank"], c["suit"]).pack(side="left", padx=5)
        
        # 2. Aggiorna l'area giocatori
        for w in self.players_ui.winfo_children(): w.destroy()
        for p in data["players"]:
            is_me = (p["name"] == self.my_nick)
            is_turn = (p["name"] == data["current"])
            
            # Frame del singolo giocatore
            f = ctk.CTkFrame(self.players_ui, fg_color="#2c3e50" if is_turn else "#16212c", 
                             border_width=2 if is_turn else 0, border_color="gold")
            f.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            
            ctk.CTkLabel(f, text=p["name"].upper(), font=("Arial", 16, "bold"), text_color="gold" if is_me else "white").pack(pady=5)
            ctk.CTkLabel(f, text=f"Saldo: ${p['balance']}", font=("Arial", 14)).pack()
            
            # Disegna le mani del giocatore (supporto per Split)
            for i, h in enumerate(p["hands"]):
                is_active_h = (is_turn and i == p["active_idx"])
                h_f = ctk.CTkFrame(f, fg_color="#34495e" if is_active_h else "transparent", corner_radius=10)
                h_f.pack(fill="x", pady=5, padx=5)
                
                row = ctk.CTkFrame(h_f, fg_color="transparent"); row.pack()
                for c in h["cards"]: 
                    CardWidget(row, c["rank"], c["suit"], mini=True).pack(side="left", padx=2)
                
                status = f"Punti: {h['value']}"
                if h['is_bust']: status += " (SBALLATO!)"
                ctk.CTkLabel(h_f, text=status, font=("Arial", 13, "bold")).pack()
            
            if is_me:
                # 3. Aggiorna saldo personale e abilita/disabilita bottoni
                self.bal_label.configure(text=f"Saldo: ${p['balance']}")
                can_act = (data["state"]=="PLAYING" and is_turn)
                for b in self.btns.values(): 
                    b.configure(state="normal" if can_act else "disabled")
                
                # Controllo Bancarotta: se saldo zero in fase di puntata
                if p["balance"] <= 0 and data["state"] == "BETTING":
                    self.show_game_over()

    def show_game_over(self):
        """Schermata finale a tutto schermo in caso di bancarotta"""
        if self.game_over_shown: return
        self.game_over_shown = True
        ov = ctk.CTkFrame(self, fg_color="black"); ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(ov, text="💸 BANCAROTTA! 💸", font=("Arial", 40, "bold"), text_color="red").place(relx=0.5, rely=0.4, anchor="center")
        ctk.CTkLabel(ov, text="Hai esaurito il tuo saldo virtuale.", font=("Arial", 18)).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkButton(ov, text="ESCI DAL GIOCO", command=self.destroy, fg_color="red", height=50, font=("Arial", 16, "bold")).place(relx=0.5, rely=0.65, anchor="center")

if __name__ == "__main__":
    app = BlackjackClient()
    app.mainloop()
