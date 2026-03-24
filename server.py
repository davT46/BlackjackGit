"""
server.py - Server Autorevole Blackjack Multiplayer (Versione Corretta)
========================================================================
Questo modulo implementa il server TCP che gestisce:
- Connessioni di massimo 3 client
- Stato completo della partita
- Turni dei giocatori e del banco
- Validazione di tutte le azioni
- Comunicazione JSON con separatore newline
- Gestione CORRETTA del saldo (no doppie sottrazioni)
- Attesa esplicita della decisione del giocatore per nuova mano

Autore: Progetto Esame di Stato
"""

import socket
import threading
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Importa la logica del gioco
from logic import (
    Mazzo, Carta, Mano, FaseGioco, RisultatoMano, RisultatoRound,
    valuta_perfect_pair, banco_deve_pescare, confronta_mani,
    calcola_vincita, calcola_vincita_assicurazione,
    crea_stato_giocatore, crea_stato_banco, get_azioni_disponibili,
    SALDO_DEFAULT, SALDO_MINIMO, SALDO_MASSIMO, PUNTATA_MINIMA, VALORI_FICHES
)

# =============================================================================
# CONFIGURAZIONE SERVER
# =============================================================================

HOST = '127.0.0.1'        # Ascolta su tutte le interfacce
PORT = 5555             # Porta di ascolto
MAX_PLAYERS = 3         # Massimo numero di giocatori
MIN_PLAYERS = 1         # Minimo per iniziare
BUFFER_SIZE = 8192      # Dimensione buffer ricezione
DELAY_CARTA_BANCO = 1.0 # Secondi tra le carte del banco


# =============================================================================
# CLASSI PER LA GESTIONE DEI GIOCATORI
# =============================================================================

@dataclass
class Giocatore:
    """
    Rappresenta un giocatore connesso al server.
    """
    player_id: int
    socket: socket.socket
    address: Tuple[str, int]
    nickname: str = ""
    saldo: int = 0  # Ora inizia a 0, verrà impostato dal client
    saldo_impostato: bool = False  # Flag per sapere se il saldo è stato scelto
    mani: List[Mano] = field(default_factory=list)
    mano_attiva: int = 0
    puntata_corrente: int = 0  # Puntata in attesa di conferma
    perfect_pair_bet: int = 0
    perfect_pair_risultato: Optional[Tuple[str, int]] = None
    perfect_pair_pagato: bool = False  # Per evitare doppi pagamenti
    pronto_per_mano: bool = False  # Il giocatore ha confermato la puntata
    attivo: bool = True
    buffer: str = ""
    insurance_risposto: bool = False  # Ha risposto all'offerta assicurazione
    
    def reset_mano(self):
        """Resetta lo stato per una nuova mano."""
        self.mani = []
        self.mano_attiva = 0
        self.puntata_corrente = 0
        self.perfect_pair_bet = 0
        self.perfect_pair_risultato = None
        self.perfect_pair_pagato = False
        self.pronto_per_mano = False
        self.insurance_risposto = False
    
    def mano_corrente(self) -> Optional[Mano]:
        """Restituisce la mano attualmente attiva."""
        if 0 <= self.mano_attiva < len(self.mani):
            return self.mani[self.mano_attiva]
        return None
    
    def prossima_mano(self) -> bool:
        """
        Passa alla prossima mano.
        
        Returns:
            True se c'è una prossima mano, False altrimenti
        """
        self.mano_attiva += 1
        return self.mano_attiva < len(self.mani)
    
    def tutte_mani_complete(self) -> bool:
        """Verifica se tutte le mani sono complete (stand o sballate)."""
        return all(m.is_stand or m.is_sballato() or m.is_from_split_aces 
                   for m in self.mani)
    
    def to_state_dict(self, is_turno: bool) -> Dict[str, Any]:
        """Crea il dizionario di stato per la trasmissione."""
        return crea_stato_giocatore(
            self.player_id,
            self.nickname,
            self.saldo,
            self.mani,
            self.mano_attiva,
            is_turno,
            self.puntata_corrente,
            self.perfect_pair_bet,
            self.perfect_pair_risultato
        )


# =============================================================================
# CLASSE PRINCIPALE DEL SERVER
# =============================================================================

class BlackjackServer:
    """
    Server principale del gioco Blackjack.
    """
    
    def __init__(self, host: str = HOST, port: int = PORT):
        """Inizializza il server."""
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Stato del gioco
        self.giocatori: Dict[int, Giocatore] = {}
        self.mazzo = Mazzo()
        self.mano_banco = Mano()
        self.fase = FaseGioco.ATTESA_GIOCATORI
        self.giocatore_corrente_id: Optional[int] = None
        
        # Contatori e lock
        self.next_player_id = 0
        self.lock = threading.RLock()  # Usa RLock per evitare deadlock
        self.partita_in_corso = False
        
        # Flag per il server
        self.running = True
    
    # =========================================================================
    # GESTIONE CONNESSIONI
    # =========================================================================
    
    def avvia(self):
        """Avvia il server e inizia ad accettare connessioni."""
        self.socket.bind((self.host, self.port))
        self.socket.listen(MAX_PLAYERS)
        print(f"[SERVER] Avviato su {self.host}:{self.port}")
        print(f"[SERVER] In attesa di giocatori (max {MAX_PLAYERS})...")
        
        while self.running:
            try:
                self.socket.settimeout(1.0)
                try:
                    client_socket, address = self.socket.accept()
                except socket.timeout:
                    continue
                
                with self.lock:
                    if len(self.giocatori) >= MAX_PLAYERS:
                        self._invia_messaggio_diretto(
                            client_socket,
                            {"type": "error", "message": "Server pieno"}
                        )
                        client_socket.close()
                        continue
                    
                    # Crea nuovo giocatore
                    player_id = self.next_player_id
                    self.next_player_id += 1
                    
                    giocatore = Giocatore(
                        player_id=player_id,
                        socket=client_socket,
                        address=address
                    )
                    self.giocatori[player_id] = giocatore
                    
                    print(f"[SERVER] Nuovo giocatore connesso: ID={player_id}, "
                          f"Address={address}")
                    
                    # Avvia thread per gestire il giocatore
                    thread = threading.Thread(
                        target=self._gestisci_giocatore,
                        args=(giocatore,),
                        daemon=True
                    )
                    thread.start()
                    
            except Exception as e:
                if self.running:
                    print(f"[SERVER] Errore accettazione: {e}")
    
    def _gestisci_giocatore(self, giocatore: Giocatore):
        """Thread principale per gestire un singolo giocatore."""
        try:
            # Invia benvenuto
            self._invia_messaggio(giocatore, {
                "type": "welcome",
                "player_id": giocatore.player_id,
                "message": "Benvenuto al tavolo di Blackjack!",
                "saldo_min": SALDO_MINIMO,
                "saldo_max": SALDO_MASSIMO,
                "saldo_default": SALDO_DEFAULT,
                "valori_fiches": VALORI_FICHES
            })
            
            # Loop ricezione messaggi
            while giocatore.attivo and self.running:
                try:
                    giocatore.socket.settimeout(0.5)
                    data = giocatore.socket.recv(BUFFER_SIZE)
                    
                    if not data:
                        raise ConnectionError("Connessione chiusa")
                    
                    # Aggiungi al buffer e processa messaggi completi
                    giocatore.buffer += data.decode('utf-8')
                    
                    while '\n' in giocatore.buffer:
                        line, giocatore.buffer = giocatore.buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self._processa_messaggio(giocatore, line)
                            
                except socket.timeout:
                    continue
                except json.JSONDecodeError as e:
                    self._invia_errore(giocatore, f"JSON non valido: {e}")
                except ConnectionError:
                    break
                except Exception as e:
                    print(f"[SERVER] Errore ricezione da {giocatore.player_id}: {e}")
                    break
                    
        except Exception as e:
            print(f"[SERVER] Errore gestione giocatore {giocatore.player_id}: {e}")
        finally:
            self._rimuovi_giocatore(giocatore)
    
    def _rimuovi_giocatore(self, giocatore: Giocatore):
        """Rimuove un giocatore dal server."""
        with self.lock:
            if giocatore.player_id in self.giocatori:
                print(f"[SERVER] Giocatore {giocatore.player_id} "
                      f"({giocatore.nickname or 'senza nome'}) disconnesso")
                
                giocatore.attivo = False
                try:
                    giocatore.socket.close()
                except:
                    pass
                
                del self.giocatori[giocatore.player_id]
                
                # Notifica gli altri giocatori
                self._broadcast({
                    "type": "player_disconnected",
                    "player_id": giocatore.player_id,
                    "nickname": giocatore.nickname
                })
                
                # Se era il turno di questo giocatore, passa al prossimo
                if (self.partita_in_corso and 
                    self.giocatore_corrente_id == giocatore.player_id):
                    self._prossimo_turno()
                
                # Se non ci sono più giocatori, resetta la partita
                if len(self.giocatori) == 0:
                    self._reset_partita()
    
    # =========================================================================
    # COMUNICAZIONE
    # =========================================================================
    
    def _invia_messaggio(self, giocatore: Giocatore, messaggio: dict):
        """Invia un messaggio JSON a un giocatore."""
        if not giocatore.attivo:
            return
        try:
            data = json.dumps(messaggio, ensure_ascii=False) + '\n'
            giocatore.socket.sendall(data.encode('utf-8'))
        except Exception as e:
            print(f"[SERVER] Errore invio a {giocatore.player_id}: {e}")
            giocatore.attivo = False
    
    def _invia_messaggio_diretto(self, sock: socket.socket, messaggio: dict):
        """Invia un messaggio a un socket specifico."""
        try:
            data = json.dumps(messaggio, ensure_ascii=False) + '\n'
            sock.sendall(data.encode('utf-8'))
        except:
            pass
    
    def _broadcast(self, messaggio: dict, escludi: Optional[int] = None):
        """Invia un messaggio a tutti i giocatori attivi."""
        for pid, giocatore in list(self.giocatori.items()):
            if giocatore.attivo and pid != escludi:
                self._invia_messaggio(giocatore, messaggio)
    
    def _invia_errore(self, giocatore: Giocatore, messaggio: str):
        """Invia un messaggio di errore a un giocatore."""
        self._invia_messaggio(giocatore, {
            "type": "error",
            "message": messaggio
        })
    
    def _broadcast_stato_lobby(self):
        """Invia lo stato della lobby a tutti."""
        stato = {
            "type": "lobby_state",
            "num_giocatori": len(self.giocatori),
            "min_giocatori": MIN_PLAYERS,
            "max_giocatori": MAX_PLAYERS,
            "puo_iniziare": len(self.giocatori) >= MIN_PLAYERS,
            "giocatori": [
                {
                    "id": g.player_id, 
                    "nickname": g.nickname or f"Giocatore {g.player_id}",
                    "saldo": g.saldo,
                    "pronto": g.saldo_impostato
                }
                for g in self.giocatori.values()
            ]
        }
        self._broadcast(stato)
    def _broadcast_stato_gioco(self, nascondi_carta_banco: bool = True):
        """Invia lo stato completo del gioco a tutti i giocatori."""
        stato = {
            "type": "game_state",
            "fase": self.fase.value,
            "banco": crea_stato_banco(self.mano_banco, nascondi_carta_banco),
            "giocatori": [
                g.to_state_dict(g.player_id == self.giocatore_corrente_id)
                for g in self.giocatori.values() if g.attivo
            ],
            "giocatore_corrente": self.giocatore_corrente_id,
            "mazzo_stats": self.mazzo.get_statistiche()
        }
        self._broadcast(stato)
    
    # =========================================================================
    # PROCESSAMENTO MESSAGGI
    # =========================================================================
    
    def _processa_messaggio(self, giocatore: Giocatore, raw_message: str):
        """Processa un messaggio ricevuto da un giocatore."""
        try:
            messaggio = json.loads(raw_message)
        except json.JSONDecodeError:
            self._invia_errore(giocatore, "Formato JSON non valido")
            return
        
        msg_type = messaggio.get("type", "")
        
        # Dispatch in base al tipo di messaggio
        handlers = {
            "set_initial_balance": self._handle_set_balance,
            "nickname": self._handle_nickname,
            "ready_to_play": self._handle_ready_to_play,
            "place_bet": self._handle_place_bet,
            "confirm_bet": self._handle_confirm_bet,
            "perfect_pair": self._handle_perfect_pair,
            "skip_perfect_pair": self._handle_skip_perfect_pair,
            "action": self._handle_action,
            "insurance": self._handle_insurance,
            "new_hand": self._handle_new_hand,
            "change_bet": self._handle_change_bet,
            "chat": self._handle_chat,
            "disconnect": self._handle_disconnect
        }
        
        handler = handlers.get(msg_type)
        if handler:
            with self.lock:
                handler(giocatore, messaggio)
        else:
            self._invia_errore(giocatore, f"Tipo messaggio sconosciuto: {msg_type}")
    
    def _handle_set_balance(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce l'impostazione del saldo iniziale."""
        try:
            saldo = int(messaggio.get("value", SALDO_DEFAULT))
        except (ValueError, TypeError):
            saldo = SALDO_DEFAULT
        
        # Valida il saldo
        saldo = max(SALDO_MINIMO, min(saldo, SALDO_MASSIMO))
        
        giocatore.saldo = saldo
        giocatore.saldo_impostato = True
        
        print(f"[SERVER] {giocatore.player_id} imposta saldo iniziale: {saldo}€")
        
        self._invia_messaggio(giocatore, {
            "type": "balance_set",
            "saldo": saldo
        })
        
        # Richiedi nickname
        self._invia_messaggio(giocatore, {
            "type": "request_nickname"
        })
    
    def _handle_nickname(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce l'impostazione del nickname."""
        nickname = messaggio.get("value", "").strip()
        
        if not nickname:
            nickname = f"Giocatore {giocatore.player_id}"
        
        nickname = nickname[:20]
        giocatore.nickname = nickname
        
        print(f"[SERVER] Giocatore {giocatore.player_id} -> {nickname}")
        
        self._invia_messaggio(giocatore, {
            "type": "nickname_accepted",
            "nickname": nickname
        })
        
        self._broadcast_stato_lobby()
        
        # Invia stato di attesa puntate
        self._invia_messaggio(giocatore, {
            "type": "waiting_for_bet",
            "saldo": giocatore.saldo,
            "min_bet": PUNTATA_MINIMA,
            "max_bet": giocatore.saldo,
            "valori_fiches": VALORI_FICHES
        })
    
    def _handle_ready_to_play(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce la conferma di essere pronto a giocare."""
        if not giocatore.saldo_impostato:
            self._invia_errore(giocatore, "Devi prima impostare il saldo iniziale")
            return
        
        self._broadcast_stato_lobby()
    
    def _handle_place_bet(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce l'aggiornamento della puntata (fiches aggiunte/rimosse)."""
        try:
            puntata = int(messaggio.get("value", 0))
        except (ValueError, TypeError):
            self._invia_errore(giocatore, "Puntata non valida")
            return
        
        # Validazione
        if puntata < 0:
            puntata = 0
        if puntata > giocatore.saldo:
            puntata = giocatore.saldo
        
        giocatore.puntata_corrente = puntata
        
        self._invia_messaggio(giocatore, {
            "type": "bet_updated",
            "puntata": puntata,
            "saldo": giocatore.saldo
        })
    
    def _handle_confirm_bet(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce la conferma della puntata e l'inizio della mano."""
        puntata = giocatore.puntata_corrente
        perfect_pair = messaggio.get("perfect_pair", 0)
        
        # Validazione puntata principale
        if puntata < PUNTATA_MINIMA:
            self._invia_errore(giocatore, 
                f"La puntata deve essere almeno {PUNTATA_MINIMA}€")
            return
        
        if puntata > giocatore.saldo:
            self._invia_errore(giocatore, "Saldo insufficiente")
            return
        
        # Validazione perfect pair
        try:
            perfect_pair = int(perfect_pair)
        except:
            perfect_pair = 0
        
        if perfect_pair < 0:
            perfect_pair = 0
        
        puntata_totale = puntata + perfect_pair
        if puntata_totale > giocatore.saldo:
            self._invia_errore(giocatore, "Saldo insufficiente per puntata + side bet")
            return
        
        # Sottrai le puntate dal saldo (UNA SOLA VOLTA)
        giocatore.saldo -= puntata_totale
        giocatore.perfect_pair_bet = perfect_pair
        giocatore.perfect_pair_pagato = False
        
        # Crea la mano con la puntata
        mano = Mano(puntata=puntata)
        giocatore.mani = [mano]
        giocatore.pronto_per_mano = True
        
        print(f"[SERVER] {giocatore.nickname} punta {puntata}€ "
              f"(PP: {perfect_pair}€, Saldo: {giocatore.saldo}€)")
        
        self._invia_messaggio(giocatore, {
            "type": "bet_confirmed",
            "puntata": puntata,
            "perfect_pair": perfect_pair,
            "saldo": giocatore.saldo
        })
        
        # Verifica se tutti i giocatori pronti sono pronti
        self._check_tutti_pronti()
    
    def _handle_perfect_pair(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce la side bet Perfect Pair (legacy, ora integrata in confirm_bet)."""
        pass  # Gestito in confirm_bet
    
    def _handle_skip_perfect_pair(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce lo skip della Perfect Pair."""
        giocatore.perfect_pair_bet = 0
    
    def _handle_action(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce un'azione di gioco (hit, stand, double, split)."""
        if self.fase != FaseGioco.TURNO_GIOCATORI:
            self._invia_errore(giocatore, "Non è il momento per azioni")
            return
        
        if self.giocatore_corrente_id != giocatore.player_id:
            self._invia_errore(giocatore, "Non è il tuo turno")
            return
        
        azione = messaggio.get("value", "").lower()
        mano = giocatore.mano_corrente()
        
        if not mano:
            self._invia_errore(giocatore, "Nessuna mano attiva")
            return
        
        azioni_valide = get_azioni_disponibili(mano, giocatore.saldo)
        
        if azione not in azioni_valide:
            self._invia_errore(giocatore, 
                f"Azione non valida. Azioni possibili: {azioni_valide}")
            return
        
        # Esegui l'azione
        if azione == "hit":
            self._esegui_hit(giocatore, mano)
        elif azione == "stand":
            self._esegui_stand(giocatore, mano)
        elif azione == "double":
            self._esegui_double(giocatore, mano)
        elif azione == "split":
            self._esegui_split(giocatore, mano)
    
    def _handle_insurance(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce la scelta dell'assicurazione."""
        if self.fase != FaseGioco.INSURANCE:
            self._invia_errore(giocatore, "Non è il momento per l'assicurazione")
            return
        
        accetta = messaggio.get("value", False)
        mano = giocatore.mano_corrente()
        
        if not mano:
            return
        
        if accetta:
            costo = mano.puntata // 2
            if costo <= giocatore.saldo:
                mano.assicurazione = costo
                giocatore.saldo -= costo
                print(f"[SERVER] {giocatore.nickname} prende assicurazione: {costo}€")
        
        giocatore.insurance_risposto = True
        
        self._invia_messaggio(giocatore, {
            "type": "insurance_response",
            "assicurazione": mano.assicurazione,
            "saldo": giocatore.saldo
        })
        
        self._check_insurance_complete()
    
    def _handle_new_hand(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce la richiesta di una nuova mano."""
        if self.fase != FaseGioco.ATTESA_NUOVA_MANO:
            self._invia_errore(giocatore, "Non è il momento per iniziare una nuova mano")
            return
        
        # Reset del giocatore per la nuova mano
        giocatore.reset_mano()
        
        # Invia la richiesta di puntata
        self._invia_messaggio(giocatore, {
            "type": "waiting_for_bet",
            "saldo": giocatore.saldo,
            "min_bet": PUNTATA_MINIMA,
            "max_bet": giocatore.saldo,
            "valori_fiches": VALORI_FICHES
        })
    
    def _handle_change_bet(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce la richiesta di cambiare puntata."""
        # Reset della puntata corrente
        giocatore.puntata_corrente = 0
        giocatore.pronto_per_mano = False
        
        self._invia_messaggio(giocatore, {
            "type": "bet_reset",
            "saldo": giocatore.saldo
        })
    
    def _handle_chat(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce la ricezione di un messaggio chat e lo invia a tutti."""
        testo = messaggio.get("message", "").strip()
        if not testo:
            return
            
        print(f"[CHAT] {giocatore.nickname}: {testo}")
        
        self._broadcast({
            "type": "chat",
            "player_id": giocatore.player_id,
            "nickname": giocatore.nickname,
            "message": testo
        })
    
    def _handle_disconnect(self, giocatore: Giocatore, messaggio: dict):
        """Gestisce la richiesta di disconnessione."""
        print(f"[SERVER] {giocatore.nickname} richiede disconnessione")
        giocatore.attivo = False
    
    # =========================================================================
    # VERIFICA STATI
    # =========================================================================
    
    def _check_tutti_pronti(self):
        """Verifica se tutti i giocatori sono pronti e avvia la distribuzione."""
        giocatori_attivi = [g for g in self.giocatori.values() if g.attivo and g.saldo_impostato]
        
        if not giocatori_attivi:
            return
        
        tutti_pronti = all(g.pronto_per_mano for g in giocatori_attivi)
        
        if tutti_pronti:
            self._avvia_distribuzione()
    
    def _check_insurance_complete(self):
        """Procede ai turni solo quando tutti i giocatori hanno risposto all'assicurazione."""
        giocatori_attivi = [g for g in self.giocatori.values() if g.attivo and g.mani]
        if not giocatori_attivi:
            self._avvia_turni_giocatori()
            return
        # Aspetta che tutti abbiano risposto
        if all(g.insurance_risposto for g in giocatori_attivi):
            self._avvia_turni_giocatori()
    
    # =========================================================================
    # AZIONI DI GIOCO
    # =========================================================================
    
    def _esegui_hit(self, giocatore: Giocatore, mano: Mano):
        """Esegue l'azione Hit: pesca una carta."""
        carta = self.mazzo.pesca()
        mano.aggiungi_carta(carta)
        
        print(f"[SERVER] {giocatore.nickname} pesca {carta}")
        
        self._broadcast({
            "type": "card_dealt",
            "player_id": giocatore.player_id,
            "mano_idx": giocatore.mano_attiva,
            "carta": carta.to_dict(),
            "punteggio": mano.calcola_punteggio()
        })
        
        self._broadcast_stato_gioco()
        
        if mano.is_sballato():
            print(f"[SERVER] {giocatore.nickname} sballa con {mano.calcola_punteggio()}")
            mano.is_stand = True
            self._avanza_mano_o_giocatore(giocatore)
        elif mano.calcola_punteggio() == 21:
            print(f"[SERVER] {giocatore.nickname} ha 21! Stand automatico.")
            mano.is_stand = True
            self._avanza_mano_o_giocatore(giocatore)
        else:
            self._richiedi_azione(giocatore)
    
    def _esegui_stand(self, giocatore: Giocatore, mano: Mano):
        """Esegue l'azione Stand: il giocatore si ferma."""
        mano.is_stand = True
        print(f"[SERVER] {giocatore.nickname} sta con {mano.calcola_punteggio()}")
        
        self._broadcast_stato_gioco()
        self._avanza_mano_o_giocatore(giocatore)
    
    def _esegui_double(self, giocatore: Giocatore, mano: Mano):
        """Esegue l'azione Double Down: raddoppia la puntata e pesca una carta."""
        # Sottrai la puntata aggiuntiva
        giocatore.saldo -= mano.puntata
        mano.puntata *= 2
        mano.is_doubled = True
        
        # Pesca una carta
        carta = self.mazzo.pesca()
        mano.aggiungi_carta(carta)
        mano.is_stand = True
        
        print(f"[SERVER] {giocatore.nickname} raddoppia (puntata: {mano.puntata}€) "
              f"e pesca {carta}")
        
        self._broadcast({
            "type": "double_down",
            "player_id": giocatore.player_id,
            "mano_idx": giocatore.mano_attiva,
            "carta": carta.to_dict(),
            "nuova_puntata": mano.puntata,
            "punteggio": mano.calcola_punteggio(),
            "saldo": giocatore.saldo
        })
        
        self._broadcast_stato_gioco()
        self._avanza_mano_o_giocatore(giocatore)
    
    def _esegui_split(self, giocatore: Giocatore, mano: Mano):
        """Esegue l'azione Split: divide la mano in due."""
        # Sottrai la puntata per la nuova mano
        giocatore.saldo -= mano.puntata
        
        is_split_assi = mano.is_coppia_assi()
        
        # Crea la nuova mano con la seconda carta
        carta_split = mano.carte.pop()
        nuova_mano = Mano(
            carte=[carta_split],
            puntata=mano.puntata,
            is_split=True,
            is_from_split_aces=is_split_assi,
            indice_split=len(giocatore.mani)
        )
        
        # La mano originale diventa anche split
        mano.is_split = True
        mano.is_from_split_aces = is_split_assi
        
        # Aggiungi una carta a ciascuna mano
        carta1 = self.mazzo.pesca()
        carta2 = self.mazzo.pesca()
        mano.aggiungi_carta(carta1)
        nuova_mano.aggiungi_carta(carta2)
        
        # Inserisci la nuova mano dopo quella corrente
        giocatore.mani.insert(giocatore.mano_attiva + 1, nuova_mano)
        
        print(f"[SERVER] {giocatore.nickname} splitta {'Assi' if is_split_assi else 'coppia'}")
        print(f"[SERVER]   Mano 1: {[str(c) for c in mano.carte]}")
        print(f"[SERVER]   Mano 2: {[str(c) for c in nuova_mano.carte]}")
        
        self._broadcast({
            "type": "split",
            "player_id": giocatore.player_id,
            "mano_idx": giocatore.mano_attiva,
            "mano1": mano.to_dict(),
            "mano2": nuova_mano.to_dict(),
            "saldo": giocatore.saldo
        })
        
        self._broadcast_stato_gioco()
        
        if is_split_assi:
            mano.is_stand = True
            nuova_mano.is_stand = True
            # Invia messaggio esplicativo ai giocatori
            self._broadcast({
                "type": "chat",
                "player_id": None,
                "nickname": "Sistema",
                "message": f"♠♠ {giocatore.nickname} ha splittato due Assi: una carta per mano, stand automatico."
            })
            self._avanza_mano_o_giocatore(giocatore)
        else:
            self._richiedi_azione(giocatore)
    
    def _avanza_mano_o_giocatore(self, giocatore: Giocatore):
        """Passa alla prossima mano del giocatore o al prossimo giocatore."""
        # Prova a passare alla prossima mano
        while giocatore.prossima_mano():
            mano = giocatore.mano_corrente()
            if mano and not mano.is_stand and not mano.is_sballato():
                self._broadcast_stato_gioco()
                self._richiedi_azione(giocatore)
                return
        
        # Tutte le mani complete, passa al prossimo giocatore
        self._prossimo_turno()
    
    # =========================================================================
    # FASI DEL GIOCO
    # =========================================================================
    
    def _avvia_distribuzione(self):
        """Distribuisce le carte iniziali."""
        self.fase = FaseGioco.DISTRIBUZIONE
        self.partita_in_corso = True
        self.mano_banco = Mano()
        
        print("\n[SERVER] ========== DISTRIBUZIONE CARTE ==========")
        
        # Due giri di carte
        for giro in range(2):
            # Carte ai giocatori
            for g in self.giocatori.values():
                if g.attivo and g.mani:
                    carta = self.mazzo.pesca()
                    g.mani[0].aggiungi_carta(carta)
                    print(f"[SERVER] {g.nickname} riceve {carta}")
            
            # Carta al banco
            carta_banco = self.mazzo.pesca()
            self.mano_banco.aggiungi_carta(carta_banco)
            print(f"[SERVER] Banco riceve {carta_banco}")
        
        print(f"[SERVER] Banco mostra: {self.mano_banco.carte[0]}")
        
        # Valuta e paga Perfect Pair per ogni giocatore
        for g in self.giocatori.values():
            if g.attivo and g.perfect_pair_bet > 0 and len(g.mani[0].carte) >= 2:
                if not g.perfect_pair_pagato:
                    tipo, moltiplicatore = valuta_perfect_pair(
                        g.mani[0].carte[0],
                        g.mani[0].carte[1]
                    )
                    g.perfect_pair_risultato = (tipo, moltiplicatore)
                    vincita = g.perfect_pair_bet * moltiplicatore
                    
                    if moltiplicatore > 0:
                        # Vincita Perfect Pair: restituisci puntata + vincita
                        g.saldo += g.perfect_pair_bet + vincita
                        print(f"[SERVER] {g.nickname} vince Perfect Pair ({tipo}): +{vincita}€")
                    else:
                        # Persa - la puntata è già stata sottratta
                        print(f"[SERVER] {g.nickname} perde Perfect Pair")
                    
                    # Invia messaggio specifico al giocatore
                    self._invia_messaggio(g, {
                        "type": "perfect_pair_result",
                        "risultato": tipo,
                        "moltiplicatore": moltiplicatore,
                        "vincita": vincita,
                        "saldo": g.saldo
                    })
                    
                    g.perfect_pair_pagato = True
        
        self._broadcast_stato_gioco(nascondi_carta_banco=True)
        
        # Verifica se il banco mostra un Asso
        if self.mano_banco.carte[0].valore == 'A':
            self._avvia_fase_insurance()
        else:
            self._avvia_turni_giocatori()
    
    def _avvia_fase_insurance(self):
        """Offre l'assicurazione ai giocatori."""
        self.fase = FaseGioco.INSURANCE
        print("[SERVER] Fase: ASSICURAZIONE")
        
        almeno_uno_puo = False
        for g in self.giocatori.values():
            if g.attivo and g.mani:
                g.insurance_risposto = False  # reset flag prima di offrire
                costo = g.mani[0].puntata // 2
                if costo <= g.saldo:
                    almeno_uno_puo = True
                    self._invia_messaggio(g, {
                        "type": "offer_insurance",
                        "costo": costo,
                        "saldo": g.saldo
                    })
                else:
                    # Non può permettersi l'assicurazione: già considerato risposto
                    g.insurance_risposto = True
        
        if not almeno_uno_puo:
            self._avvia_turni_giocatori()
    
    def _avvia_turni_giocatori(self):
        """Avvia la fase dei turni dei giocatori."""
        self.fase = FaseGioco.TURNO_GIOCATORI
        print("[SERVER] Fase: TURNI GIOCATORI")
        
        for g in self.giocatori.values():
            if g.attivo and g.mani:
                punteggio = g.mani[0].calcola_punteggio()
                if punteggio >= 21:
                    print(f"[SERVER] {g.nickname} ha {punteggio}. Stand automatico.")
                    g.mani[0].is_stand = True
                    continue # Prova con il prossimo giocatore
                
                self.giocatore_corrente_id = g.player_id
                g.mano_attiva = 0
                self._broadcast_stato_gioco()
                self._richiedi_azione(g)
                return
        
        self._turno_banco()
    
    def _richiedi_azione(self, giocatore: Giocatore):
        """Richiede un'azione al giocatore corrente."""
        mano = giocatore.mano_corrente()
        if not mano:
            self._avanza_mano_o_giocatore(giocatore)
            return
        
        azioni = get_azioni_disponibili(mano, giocatore.saldo)
        
        if not azioni:
            self._avanza_mano_o_giocatore(giocatore)
            return
        
        self._invia_messaggio(giocatore, {
            "type": "request_action",
            "azioni": azioni,
            "mano_attiva": giocatore.mano_attiva,
            "num_mani": len(giocatore.mani),
            "mano": mano.to_dict()
        })
    
    def _prossimo_turno(self):
        """Passa al turno del prossimo giocatore o al banco."""
        giocatori_ids = sorted([
            g.player_id for g in self.giocatori.values() 
            if g.attivo and g.mani
        ])
        
        if not giocatori_ids:
            self._turno_banco()
            return
        
        try:
            idx_corrente = giocatori_ids.index(self.giocatore_corrente_id)
            for i in range(1, len(giocatori_ids) + 1):
                next_idx = (idx_corrente + i) % len(giocatori_ids)
                next_id = giocatori_ids[next_idx]
                giocatore = self.giocatori.get(next_id)
                
                if giocatore and not giocatore.tutte_mani_complete():
                    self.giocatore_corrente_id = next_id
                    giocatore.mano_attiva = 0
                    while (giocatore.mano_attiva < len(giocatore.mani) and
                           giocatore.mani[giocatore.mano_attiva].is_stand):
                        giocatore.mano_attiva += 1
                    
                    if giocatore.mano_attiva < len(giocatore.mani):
                        self._broadcast_stato_gioco()
                        self._richiedi_azione(giocatore)
                        return
        except ValueError:
            pass
        
        self._turno_banco()
    
    def _turno_banco(self):
        """Esegue il turno del banco."""
        self.fase = FaseGioco.TURNO_BANCO
        self.giocatore_corrente_id = None
        print("[SERVER] Fase: TURNO BANCO")
        
        self._broadcast({
            "type": "dealer_reveal",
            "carta": self.mano_banco.carte[1].to_dict() if len(self.mano_banco.carte) > 1 else None,
            "punteggio": self.mano_banco.calcola_punteggio()
        })
        
        self._broadcast_stato_gioco(nascondi_carta_banco=False)
        
        giocatori_in_gioco = [
            g for g in self.giocatori.values()
            if g.attivo and g.mani and 
            any(not m.is_sballato() for m in g.mani)
        ]
        
        if not giocatori_in_gioco:
            print("[SERVER] Tutti i giocatori sballati")
            self._concludi_mano()
            return
        
        time.sleep(DELAY_CARTA_BANCO)
        
        while banco_deve_pescare(self.mano_banco):
            carta = self.mazzo.pesca()
            self.mano_banco.aggiungi_carta(carta)
            
            print(f"[SERVER] Banco pesca: {carta} (totale: {self.mano_banco.calcola_punteggio()})")
            
            self._broadcast({
                "type": "dealer_card",
                "carta": carta.to_dict(),
                "punteggio": self.mano_banco.calcola_punteggio(),
                "is_sballato": self.mano_banco.is_sballato()
            })
            
            self._broadcast_stato_gioco(nascondi_carta_banco=False)
            time.sleep(DELAY_CARTA_BANCO)
        
        self._concludi_mano()
    
    def _concludi_mano(self):
        """Calcola i risultati e conclude la mano."""
        self.fase = FaseGioco.RISULTATI
        print("[SERVER] Fase: RISULTATI")
        
        risultati = []
        banco_ha_blackjack = self.mano_banco.is_blackjack()
        
        for g in self.giocatori.values():
            if not g.attivo or not g.mani:
                continue
            
            risultati_mani = []
            vincita_totale = 0
            
            # Calcola vincita assicurazione
            vincita_assicurazione = 0
            for mano in g.mani:
                vincita_assicurazione += calcola_vincita_assicurazione(
                    mano, banco_ha_blackjack
                )
            
            # Calcola risultati per ogni mano
            for idx, mano in enumerate(g.mani):
                risultato = confronta_mani(mano, self.mano_banco)
                # calcola_vincita restituisce l'importo da AGGIUNGERE al saldo
                vincita = calcola_vincita(mano, risultato)
                vincita_totale += vincita
                
                risultati_mani.append({
                    "mano_idx": idx,
                    "risultato": risultato.value,
                    "punteggio": mano.calcola_punteggio(),
                    "puntata": mano.puntata,
                    "vincita": vincita
                })
                
                print(f"[SERVER] {g.nickname} mano {idx+1}: {risultato.value} "
                      f"(vincita: {vincita}€)")
            
            # Aggiungi vincite al saldo
            g.saldo += vincita_totale + vincita_assicurazione
            
            # Calcola vincita PP (già pagata durante distribuzione)
            vincita_pp = 0
            if g.perfect_pair_risultato and g.perfect_pair_risultato[1] > 0:
                vincita_pp = g.perfect_pair_bet * g.perfect_pair_risultato[1]
            
            print(f"[SERVER] {g.nickname} saldo finale: {g.saldo}€")
            
            risultato_giocatore = RisultatoRound(
                player_id=g.player_id,
                nickname=g.nickname,
                risultati_mani=risultati_mani,
                vincita_totale=vincita_totale,
                vincita_assicurazione=vincita_assicurazione,
                vincita_perfect_pair=vincita_pp,
                nuovo_saldo=g.saldo
            )
            risultati.append(risultato_giocatore.to_dict())
        
        self._broadcast({
            "type": "round_results",
            "banco": {
                "carte": [c.to_dict() for c in self.mano_banco.carte],
                "punteggio": self.mano_banco.calcola_punteggio(),
                "is_blackjack": self.mano_banco.is_blackjack(),
                "is_sballato": self.mano_banco.is_sballato()
            },
            "risultati": risultati
        })
        
        self.partita_in_corso = False
        
        # Passa alla fase di attesa nuova mano
        time.sleep(2)
        self._fase_attesa_nuova_mano()
    
    def _fase_attesa_nuova_mano(self):
        """Imposta la fase di attesa della decisione del giocatore."""
        self.fase = FaseGioco.ATTESA_NUOVA_MANO
        print("[SERVER] Fase: ATTESA NUOVA MANO")
        
        for g in self.giocatori.values():
            if g.attivo:
                puo_giocare = g.saldo >= PUNTATA_MINIMA
                
                self._invia_messaggio(g, {
                    "type": "hand_complete",
                    "saldo": g.saldo,
                    "puo_giocare": puo_giocare,
                    "min_bet": PUNTATA_MINIMA,
                    "valori_fiches": VALORI_FICHES
                })
    
    def _reset_partita(self):
        """Resetta lo stato della partita."""
        print("[SERVER] Reset partita")
        self.partita_in_corso = False
        self.fase = FaseGioco.ATTESA_GIOCATORI
        self.mano_banco = Mano()
        self.giocatore_corrente_id = None
    
    # =========================================================================
    # CLEANUP
    # =========================================================================
    
    def ferma(self):
        """Ferma il server."""
        print("[SERVER] Arresto in corso...")
        self.running = False
        
        for g in list(self.giocatori.values()):
            try:
                self._invia_messaggio(g, {"type": "server_shutdown"})
                g.socket.close()
            except:
                pass
        
        try:
            self.socket.close()
        except:
            pass
        
        print("[SERVER] Arrestato")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    server = BlackjackServer()
    
    try:
        server.avvia()
    except KeyboardInterrupt:
        print("\n[SERVER] Interruzione da tastiera")
    finally:
        server.ferma()