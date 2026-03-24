"""
logic.py - Logica del Gioco Blackjack (Versione Corretta)
==========================================================
Questo modulo contiene tutte le classi e funzioni per gestire
la logica del gioco Blackjack, inclusi:
- Gestione del mazzo (4 mazzi standard) con controllo anti-duplicazione
- Rappresentazione delle carte
- Calcolo del punteggio con gestione dinamica dell'Asso
- Regole per split, double down, insurance
- Valutazione Perfect Pair (side bet)
- Confronto mani e calcolo vincite (CORRETTO)

Autore: Progetto Esame di Stato
"""

import random
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import copy

# =============================================================================
# COSTANTI DEL GIOCO
# =============================================================================

# I quattro semi delle carte
SEMI = ['cuori', 'quadri', 'fiori', 'picche']

# Tutti i valori possibili delle carte
VALORI = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

# Associazione seme -> colore (per Perfect Pair)
COLORI_SEMI = {
    'cuori': 'rosso',
    'quadri': 'rosso',
    'fiori': 'nero',
    'picche': 'nero'
}

# Simboli Unicode per i semi (per visualizzazione testuale)
SIMBOLI_SEMI = {
    'cuori': '♥',
    'quadri': '♦',
    'fiori': '♣',
    'picche': '♠'
}

# Numero di mazzi utilizzati
NUM_MAZZI = 4

# Saldo iniziale di default (ora configurabile dal client)
SALDO_DEFAULT = 500
SALDO_MINIMO = 100
SALDO_MASSIMO = 10000

# Puntata minima
PUNTATA_MINIMA = 1

# Valori delle fiches disponibili
VALORI_FICHES = [1, 5, 10, 25, 50, 100, 1000, 2000, 5000, 10000, 20000, 50000, 100000]


# =============================================================================
# ENUMERAZIONI
# =============================================================================

class RisultatoMano(Enum):
    """
    Enumera i possibili risultati di una mano rispetto al banco.
    Usato per determinare vincite e perdite.
    """
    VITTORIA = "vittoria"
    SCONFITTA = "sconfitta"
    PAREGGIO = "pareggio"
    BLACKJACK = "blackjack"
    SBALLATO = "sballato"


class FaseGioco(Enum):
    """
    Enumera le fasi di una mano di Blackjack.
    Il server usa questa enum per tracciare lo stato della partita.
    """
    ATTESA_GIOCATORI = "attesa_giocatori"
    RACCOLTA_SALDO_INIZIALE = "raccolta_saldo_iniziale"
    RACCOLTA_NICKNAME = "raccolta_nickname"
    ATTESA_PUNTATE = "attesa_puntate"  # Fase di attesa - il giocatore sceglie quando puntare
    RACCOLTA_PUNTATE = "raccolta_puntate"
    PERFECT_PAIR_BET = "perfect_pair_bet"
    DISTRIBUZIONE = "distribuzione"
    INSURANCE = "insurance"
    TURNO_GIOCATORI = "turno_giocatori"
    TURNO_BANCO = "turno_banco"
    RISULTATI = "risultati"
    ATTESA_NUOVA_MANO = "attesa_nuova_mano"  # Nuova fase: attesa decisione giocatore


# =============================================================================
# CLASSI PRINCIPALI
# =============================================================================

@dataclass
class Carta:
    """
    Rappresenta una singola carta da gioco.
    
    Attributes:
        valore: Il valore della carta (2-10, J, Q, K, A)
        seme: Il seme della carta (cuori, quadri, fiori, picche)
    """
    valore: str
    seme: str
    
    def to_dict(self) -> Dict[str, str]:
        """Converte la carta in dizionario per serializzazione JSON."""
        return {
            "valore": self.valore,
            "seme": self.seme
        }
    
    @staticmethod
    def from_dict(data: Dict[str, str]) -> 'Carta':
        """Crea una carta da un dizionario deserializzato."""
        return Carta(data["valore"], data["seme"])
    
    def get_colore(self) -> str:
        """Restituisce il colore della carta (rosso o nero)."""
        return COLORI_SEMI[self.seme]
    
    def get_valore_numerico(self) -> int:
        """
        Restituisce il valore numerico base della carta.
        L'Asso restituisce 11 (verrà gestito dinamicamente).
        """
        if self.valore == 'A':
            return 11
        elif self.valore in ['J', 'Q', 'K']:
            return 10
        else:
            return int(self.valore)
    
    def get_simbolo(self) -> str:
        """Restituisce la rappresentazione con simbolo Unicode."""
        return f"{self.valore}{SIMBOLI_SEMI[self.seme]}"
    
    def get_id(self) -> str:
        """Restituisce un identificatore univoco per la carta."""
        return f"{self.valore}_{self.seme}"
    
    def __str__(self) -> str:
        """Rappresentazione testuale della carta."""
        return f"{self.valore} di {self.seme}"
    
    def __eq__(self, other) -> bool:
        """Confronta due carte per uguaglianza."""
        if not isinstance(other, Carta):
            return False
        return self.valore == other.valore and self.seme == other.seme
    
    def __hash__(self) -> int:
        """Hash per usare la carta in set/dict."""
        return hash((self.valore, self.seme))


class Mazzo:
    """
    Gestisce un mazzo di carte composto da più mazzi standard.
    Implementa il rimescolamento automatico quando le carte scarseggiano.
    Include controlli anti-duplicazione migliorati.
    
    Attributes:
        num_mazzi: Numero di mazzi standard da utilizzare
        carte: Lista delle carte disponibili nel mazzo
        carte_usate: Set delle carte già estratte (per debug)
    """
    
    def __init__(self, num_mazzi: int = NUM_MAZZI):
        """
        Inizializza il mazzo con il numero specificato di mazzi standard.
        
        Args:
            num_mazzi: Numero di mazzi da 52 carte da combinare
        """
        self.num_mazzi = num_mazzi
        self.carte: List[Carta] = []
        self.carte_estratte: List[Carta] = []  # Traccia le carte estratte
        # Rimescola quando rimangono circa il 20% delle carte per non interrompere una mano
        self._carte_totali = 52 * num_mazzi
        self._soglia_rimescola = int(self._carte_totali * 0.2)
        self.reset()
    
    def reset(self):
        """Ricrea il mazzo completo e lo mescola."""
        self.carte = []
        self.carte_estratte = []
        
        # Crea tutte le carte per ogni mazzo
        for mazzo_idx in range(self.num_mazzi):
            for seme in SEMI:
                for valore in VALORI:
                    self.carte.append(Carta(valore, seme))
        
        # Verifica integrità
        assert len(self.carte) == self._carte_totali, \
            f"Errore: mazzo ha {len(self.carte)} carte invece di {self._carte_totali}"
        
        self.mescola()
        print(f"[MAZZO] Reset completato: {len(self.carte)} carte disponibili")
    
    def mescola(self):
        """Mescola le carte del mazzo usando l'algoritmo Fisher-Yates."""
        random.shuffle(self.carte)
    
    def pesca(self) -> Carta:
        """
        Pesca una carta dalla cima del mazzo.
        Se le carte sono poche, rimescola automaticamente.
        
        Returns:
            La carta pescata
            
        Raises:
            RuntimeError: Se il mazzo è vuoto (non dovrebbe mai accadere)
        """
        # Controlla se serve rimescolare
        if len(self.carte) < self._soglia_rimescola:
            print(f"[MAZZO] Carte rimanenti: {len(self.carte)} - Rimescolo")
            self.reset()
        
        if len(self.carte) == 0:
            raise RuntimeError("Errore critico: mazzo vuoto!")
        
        carta = self.carte.pop()
        self.carte_estratte.append(carta)
        
        return carta
    
    def carte_rimanenti(self) -> int:
        """Restituisce il numero di carte ancora nel mazzo."""
        return len(self.carte)
    
    def get_statistiche(self) -> Dict[str, int]:
        """Restituisce statistiche sul mazzo per debug."""
        return {
            "totali": self._carte_totali,
            "rimanenti": len(self.carte),
            "estratte": len(self.carte_estratte),
            "soglia_rimescola": self._soglia_rimescola
        }


@dataclass
class Mano:
    """
    Rappresenta una mano di carte di un giocatore.
    Supporta split, double down e tutte le azioni del Blackjack.
    
    Attributes:
        carte: Lista delle carte nella mano
        puntata: Importo scommesso su questa mano
        is_split: True se questa mano deriva da uno split
        is_doubled: True se è stato fatto double down
        is_stand: True se il giocatore ha scelto di stare
        is_from_split_aces: True se deriva da split di Assi (una sola carta)
        assicurazione: Importo dell'assicurazione (0 se non presa)
        indice_split: Indice della mano in caso di split multipli
    """
    carte: List[Carta] = field(default_factory=list)
    puntata: int = 0
    is_split: bool = False
    is_doubled: bool = False
    is_stand: bool = False
    is_from_split_aces: bool = False
    assicurazione: int = 0
    indice_split: int = 0  # Per identificare la mano in caso di split
    
    def aggiungi_carta(self, carta: Carta):
        """Aggiunge una carta alla mano."""
        self.carte.append(carta)
    
    def calcola_punteggio(self) -> int:
        """
        Calcola il punteggio ottimale della mano.
        
        Gli Assi vengono contati come 11 se possibile, altrimenti come 1.
        Questo implementa la regola del "soft hand" del Blackjack.
        
        Returns:
            Il punteggio ottimale (massimo senza sballare, se possibile)
        """
        punteggio = 0
        num_assi = 0
        
        # Prima somma tutti i valori, contando gli Assi come 11
        for carta in self.carte:
            if carta.valore == 'A':
                num_assi += 1
                punteggio += 11
            elif carta.valore in ['J', 'Q', 'K']:
                punteggio += 10
            else:
                punteggio += int(carta.valore)
        
        # Converti gli Assi da 11 a 1 finché necessario per non sballare
        while punteggio > 21 and num_assi > 0:
            punteggio -= 10
            num_assi -= 1
        
        return punteggio
    
    def is_soft(self) -> bool:
        """
        Verifica se la mano è "soft" (contiene un Asso contato come 11).
        
        Returns:
            True se la mano è soft
        """
        punteggio = 0
        num_assi = 0
        
        for carta in self.carte:
            if carta.valore == 'A':
                num_assi += 1
                punteggio += 11
            elif carta.valore in ['J', 'Q', 'K']:
                punteggio += 10
            else:
                punteggio += int(carta.valore)
        
        return num_assi > 0 and punteggio <= 21
    
    def is_sballato(self) -> bool:
        """Verifica se la mano ha sballato (punteggio > 21)."""
        return self.calcola_punteggio() > 21
    
    def is_blackjack(self) -> bool:
        """
        Verifica se la mano è un Blackjack naturale.
        
        Returns:
            True se è un Blackjack naturale
        """
        return (len(self.carte) == 2 and 
                self.calcola_punteggio() == 21 and 
                not self.is_split)
    
    def puo_splittare(self) -> bool:
        """
        Verifica se la mano può essere splittata.
        
        Returns:
            True se lo split è consentito
        """
        if len(self.carte) != 2:
            return False
        
        v1, v2 = self.carte[0].valore, self.carte[1].valore
        
        # Stessa carta
        if v1 == v2:
            return True
        
        # Figure e 10 possono essere splittate insieme
        valori_dieci = ['10', 'J', 'Q', 'K']
        return v1 in valori_dieci and v2 in valori_dieci
    
    def puo_raddoppiare(self) -> bool:
        """
        Verifica se è possibile fare double down.
        
        Returns:
            True se il double down è consentito
        """
        return len(self.carte) == 2 and not self.is_stand
    
    def is_coppia_assi(self) -> bool:
        """Verifica se la mano è una coppia di Assi."""
        if len(self.carte) != 2:
            return False
        return self.carte[0].valore == 'A' and self.carte[1].valore == 'A'
    
    def to_dict(self, nascondi_carte: bool = False) -> Dict[str, Any]:
        """
        Converte la mano in dizionario per serializzazione JSON.
        
        Args:
            nascondi_carte: Se True, non include le carte (per il banco)
            
        Returns:
            Dizionario con tutti i dati della mano
        """
        result = {
            "puntata": self.puntata,
            "punteggio": self.calcola_punteggio(),
            "is_split": self.is_split,
            "is_doubled": self.is_doubled,
            "is_stand": self.is_stand,
            "is_sballato": self.is_sballato(),
            "is_blackjack": self.is_blackjack(),
            "assicurazione": self.assicurazione,
            "indice_split": self.indice_split,
            "num_carte": len(self.carte)
        }
        
        if not nascondi_carte:
            result["carte"] = [c.to_dict() for c in self.carte]
        
        return result
    
    def copia(self) -> 'Mano':
        """Crea una copia profonda della mano."""
        nuova_mano = Mano(
            carte=[Carta(c.valore, c.seme) for c in self.carte],
            puntata=self.puntata,
            is_split=self.is_split,
            is_doubled=self.is_doubled,
            is_stand=self.is_stand,
            is_from_split_aces=self.is_from_split_aces,
            assicurazione=self.assicurazione,
            indice_split=self.indice_split
        )
        return nuova_mano


# =============================================================================
# FUNZIONI DI VALUTAZIONE
# =============================================================================

def valuta_perfect_pair(carta1: Carta, carta2: Carta) -> Tuple[str, int]:
    """
    Valuta la side bet Perfect Pair.
    
    Args:
        carta1: Prima carta
        carta2: Seconda carta
        
    Returns:
        Tupla (tipo_pair, moltiplicatore)
    """
    # Se i valori sono diversi, nessun pair
    if carta1.valore != carta2.valore:
        return ("none", 0)
    
    # Stesso seme = Perfect Pair
    if carta1.seme == carta2.seme:
        return ("perfect", 25)
    
    # Stesso colore = Colored Pair
    elif carta1.get_colore() == carta2.get_colore():
        return ("colored", 12)
    
    # Colore diverso = Mixed Pair
    else:
        return ("mixed", 6)


def banco_deve_pescare(mano: Mano) -> bool:
    """
    Determina se il banco deve pescare un'altra carta.
    
    Regola: Il banco DEVE pescare su 16 o meno.
            Il banco DEVE stare su 17 o più (incluso soft 17).
    
    Args:
        mano: La mano del banco
        
    Returns:
        True se il banco deve pescare
    """
    punteggio = mano.calcola_punteggio()
    return punteggio < 17


def confronta_mani(mano_giocatore: Mano, mano_banco: Mano) -> RisultatoMano:
    """
    Confronta la mano del giocatore con quella del banco.
    
    Args:
        mano_giocatore: La mano del giocatore
        mano_banco: La mano del banco
        
    Returns:
        RisultatoMano indicante l'esito
    """
    punteggio_giocatore = mano_giocatore.calcola_punteggio()
    punteggio_banco = mano_banco.calcola_punteggio()
    
    # Giocatore sballato - perde sempre
    if punteggio_giocatore > 21:
        return RisultatoMano.SBALLATO
    
    # Banco sballato - giocatore vince
    if punteggio_banco > 21:
        return RisultatoMano.VITTORIA
    
    # Blackjack del giocatore (paga 3:2)
    if mano_giocatore.is_blackjack() and not mano_banco.is_blackjack():
        return RisultatoMano.BLACKJACK

    # Blackjack del banco vs non-blackjack giocatore → sconfitta
    # Gestisce il caso: giocatore ha 21 normale, banco ha Blackjack
    if mano_banco.is_blackjack() and not mano_giocatore.is_blackjack():
        return RisultatoMano.SCONFITTA

    # Confronto punteggi standard (include entrambi blackjack → pareggio)
    if punteggio_giocatore > punteggio_banco:
        return RisultatoMano.VITTORIA
    elif punteggio_giocatore < punteggio_banco:
        return RisultatoMano.SCONFITTA
    else:
        return RisultatoMano.PAREGGIO


def calcola_vincita(mano: Mano, risultato: RisultatoMano) -> int:
    """
    Calcola l'importo DA RESTITUIRE al giocatore in base al risultato.
    
    IMPORTANTE: La puntata è già stata sottratta dal saldo all'inizio.
    Questa funzione restituisce quanto va AGGIUNTO al saldo:
    - Blackjack: puntata + 1.5*puntata = 2.5*puntata
    - Vittoria: puntata + puntata = 2*puntata
    - Pareggio: solo la puntata (restituita)
    - Sconfitta/Sballato: 0 (puntata già persa)
    
    Args:
        mano: La mano del giocatore
        risultato: L'esito del confronto
        
    Returns:
        Importo da aggiungere al saldo
    """
    puntata = mano.puntata
    
    if risultato == RisultatoMano.BLACKJACK:
        # Blackjack paga 3:2 - restituisci puntata + vincita 1.5x
        return puntata + int(puntata * 1.5)
    elif risultato == RisultatoMano.VITTORIA:
        # Vittoria normale paga 1:1 - restituisci puntata + vincita 1x
        return puntata * 2
    elif risultato == RisultatoMano.PAREGGIO:
        # Push - restituisci solo la puntata
        return puntata
    else:
        # Sconfitta o sballato - la puntata è già stata sottratta, non restituire nulla
        return 0


def calcola_vincita_assicurazione(mano: Mano, banco_ha_blackjack: bool) -> int:
    """
    Calcola la vincita dell'assicurazione.
    
    L'assicurazione paga 2:1 se il banco ha Blackjack.
    La puntata assicurazione è già stata sottratta.
    
    Args:
        mano: La mano con l'assicurazione
        banco_ha_blackjack: True se il banco ha Blackjack
        
    Returns:
        Importo da aggiungere al saldo
    """
    if mano.assicurazione <= 0:
        return 0
    
    if banco_ha_blackjack:
        # Assicurazione vinta - paga 2:1 (restituisci puntata + 2x vincita)
        return mano.assicurazione * 3
    else:
        # Assicurazione persa - già sottratta, restituisci 0
        return 0


# =============================================================================
# FUNZIONI DI UTILITÀ
# =============================================================================

def carta_nascosta() -> Dict[str, str]:
    """Restituisce un dizionario rappresentante una carta coperta."""
    return {"valore": "?", "seme": "nascosto"}


def crea_stato_giocatore(
    player_id: int,
    nickname: str,
    saldo: int,
    mani: List[Mano],
    mano_attiva: int,
    is_turno: bool,
    puntata_corrente: int = 0,
    perfect_pair_bet: int = 0,
    perfect_pair_risultato: Optional[Tuple[str, int]] = None
) -> Dict[str, Any]:
    """
    Crea il dizionario di stato di un giocatore per la trasmissione.
    """
    return {
        "id": player_id,
        "nickname": nickname,
        "saldo": saldo,
        "mani": [m.to_dict() for m in mani],
        "mano_attiva": mano_attiva,
        "is_turno": is_turno,
        "puntata_corrente": puntata_corrente,
        "perfect_pair_bet": perfect_pair_bet,
        "perfect_pair_risultato": perfect_pair_risultato,
        "num_mani": len(mani)
    }


def crea_stato_banco(
    mano: Mano, 
    nascondi_seconda: bool = False
) -> Dict[str, Any]:
    """
    Crea il dizionario di stato del banco.
    """
    if nascondi_seconda and len(mano.carte) >= 2:
        carte_visibili = [mano.carte[0].to_dict(), carta_nascosta()]
        punteggio_visibile = mano.carte[0].get_valore_numerico()
        if mano.carte[0].valore == 'A':
            punteggio_visibile = 11
    else:
        carte_visibili = [c.to_dict() for c in mano.carte]
        punteggio_visibile = mano.calcola_punteggio()
    
    return {
        "carte": carte_visibili,
        "punteggio": punteggio_visibile,
        "carta_nascosta": nascondi_seconda,
        "is_sballato": mano.is_sballato() if not nascondi_seconda else False,
        "is_blackjack": mano.is_blackjack() if not nascondi_seconda else False
    }


def get_azioni_disponibili(mano: Mano, saldo: int, prima_azione: bool = True) -> List[str]:
    """
    Determina le azioni disponibili per una mano.
    """
    if mano.is_stand or mano.is_sballato():
        return []
    
    if mano.is_from_split_aces:
        return []
    
    azioni = ["hit", "stand"]
    
    if mano.puo_raddoppiare() and saldo >= mano.puntata:
        azioni.append("double")
    
    if mano.puo_splittare() and saldo >= mano.puntata:
        azioni.append("split")
    
    return azioni


# =============================================================================
# CLASSE HELPER PER I RISULTATI
# =============================================================================

@dataclass
class RisultatoRound:
    """
    Contiene tutti i risultati di un round per un giocatore.
    """
    player_id: int
    nickname: str
    risultati_mani: List[Dict[str, Any]]
    vincita_totale: int
    vincita_assicurazione: int
    vincita_perfect_pair: int
    nuovo_saldo: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per JSON."""
        return {
            "player_id": self.player_id,
            "nickname": self.nickname,
            "risultati_mani": self.risultati_mani,
            "vincita_totale": self.vincita_totale,
            "vincita_assicurazione": self.vincita_assicurazione,
            "vincita_perfect_pair": self.vincita_perfect_pair,
            "nuovo_saldo": self.nuovo_saldo
        }