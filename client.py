"""
client.py - Client GUI per Blackjack Multiplayer (Versione Migliorata)
=======================================================================
Questo modulo implementa il client grafico usando CustomTkinter.
Migliorie:
- Sistema di fiches per le puntate
- Selezione saldo iniziale con slider
- Visualizzazione corretta delle mani split
- Grafica moderna e ordinata
- Gestione disconnessione pulita

Autore: Progetto Esame di Stato
"""

import socket
import threading
import json
import time
import os
import sys
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5555
BUFFER_SIZE = 8192

# Dimensioni delle carte
CARD_WIDTH = 60
CARD_HEIGHT = 84

# Colori tema migliorati
COLORE_TAVOLO = "#0d5c2e"           # Verde tavolo
COLORE_TAVOLO_SCURO = "#094d24"     # Verde più scuro
COLORE_PANNELLO = "#1a1a2e"         # Blu scuro
COLORE_PANNELLO_CHIARO = "#16213e"  # Blu medio
COLORE_ACCENTO = "#e94560"          # Rosso accento
COLORE_ORO = "#ffd700"              # Oro
COLORE_ARGENTO = "#c0c0c0"          # Argento
COLORE_TESTO = "#ffffff"            # Bianco
COLORE_TESTO_SCURO = "#b0b0b0"      # Grigio chiaro
COLORE_SUCCESSO = "#00d26a"         # Verde successo
COLORE_ERRORE = "#ff4757"           # Rosso errore
COLORE_WARNING = "#ffa502"          # Arancione warning

# Colori fiches
COLORI_FICHES = {
    1: "#ffffff",        # Bianco
    5: "#ff4444",        # Rosso
    10: "#4444ff",       # Blu
    25: "#44ff44",       # Verde
    50: "#ff8800",       # Arancione
    100: "#000000",      # Nero
    1000: "#ffd700",     # Oro
    2000: "#c0c0c0",     # Argento
    5000: "#e94560",     # Rosso Accento
    10000: "#7c3aed",    # Viola
    20000: "#2563eb",    # Blu acceso
    50000: "#00d26a",    # Verde smeraldo
    100000: "#ff4757"    # Corallo
}

# Simboli delle carte
SIMBOLI = {
    'cuori': '♥',
    'quadri': '♦', 
    'fiori': '♣',
    'picche': '♠'
}

# Configurazione CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# =============================================================================
# GENERATORE DI IMMAGINI DELLE CARTE
# =============================================================================

class CardImageGenerator:
    """Genera immagini delle carte dinamicamente."""
    
    def __init__(self, width: int = CARD_WIDTH, height: int = CARD_HEIGHT):
        self.width = width
        self.height = height
        self.cache: Dict[str, ctk.CTkImage] = {}
        
        try:
            self.font_large = ImageFont.truetype("arial.ttf", 18)
            self.font_small = ImageFont.truetype("arial.ttf", 12)
            self.font_symbol = ImageFont.truetype("arial.ttf", 28)
        except:
            self.font_large = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_symbol = ImageFont.load_default()
    
    def get_card_image(self, valore: str, seme: str) -> ctk.CTkImage:
        """Ottiene l'immagine di una carta."""
        key = f"{valore}_{seme}"
        
        if key in self.cache:
            return self.cache[key]
        
        image = self._generate_card(valore, seme)
        ctk_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=(self.width, self.height)
        )
        
        self.cache[key] = ctk_image
        return ctk_image
    
    def get_back_image(self) -> ctk.CTkImage:
        """Restituisce l'immagine del retro della carta."""
        if "back" in self.cache:
            return self.cache["back"]
        
        image = self._generate_back()
        ctk_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=(self.width, self.height)
        )
        
        self.cache["back"] = ctk_image
        return ctk_image
    
    def _generate_card(self, valore: str, seme: str) -> Image.Image:
        """Genera un'immagine della carta realistica."""
        W, H = self.width, self.height
        
        is_red = seme in ['cuori', 'quadri']
        colore_seme = (200, 30, 30) if is_red else (15, 15, 15)
        simbolo = SIMBOLI.get(seme, '?')
        
        # Sfondo bianco con angoli arrotondati
        image = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Ombra leggera (offset 2px)
        shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow)
        sdraw.rounded_rectangle([2, 2, W-1, H-1], radius=7, fill=(0, 0, 0, 60))
        image = Image.alpha_composite(image, shadow)
        draw = ImageDraw.Draw(image)
        
        # Corpo bianco
        draw.rounded_rectangle([0, 0, W-3, H-3], radius=7,
                                fill=(255, 255, 255, 255),
                                outline=(190, 190, 190), width=1)
        
        # Bordo interno sottile
        draw.rounded_rectangle([3, 3, W-6, H-6], radius=5,
                                outline=(230, 230, 230), width=1)
        
        # --- Font ---
        try:
            f_val   = ImageFont.truetype("arialbd.ttf", 14)
            f_sym   = ImageFont.truetype("arial.ttf",   11)
            f_big   = ImageFont.truetype("arial.ttf",   22)
        except:
            f_val = f_sym = f_big = ImageFont.load_default()
        
        # Angolo in alto a sinistra: valore + simbolo
        draw.text((5, 3),  valore,  fill=colore_seme, font=f_val)
        draw.text((5, 18), simbolo, fill=colore_seme, font=f_sym)
        
        # Angolo in basso a destra: ruotato 180° (specchiato)
        txt_img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((5, 3),  valore,  fill=colore_seme, font=f_val)
        txt_draw.text((5, 18), simbolo, fill=colore_seme, font=f_sym)
        txt_rot = txt_img.rotate(180)
        image = Image.alpha_composite(image, txt_rot)
        draw = ImageDraw.Draw(image)
        
        # Simbolo centrale grande
        bbox = draw.textbbox((0, 0), simbolo, font=f_big)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        cx = (W - 3 - tw) // 2
        cy = (H - 3 - th) // 2
        draw.text((cx, cy), simbolo, fill=colore_seme, font=f_big)
        
        return image
    
    def _generate_back(self) -> Image.Image:
        """Genera l'immagine del retro della carta con pattern a diamanti."""
        W, H = self.width, self.height
        
        image = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Corpo principale blu navy
        draw.rounded_rectangle([0, 0, W-3, H-3], radius=7,
                                fill=(18, 42, 90, 255),
                                outline=(100, 130, 180), width=1)
        
        # Pattern a quadri interni
        spacing = 7
        for y in range(4, H-4, spacing):
            for x in range(4, W-4, spacing):
                draw.rectangle([x, y, x+3, y+3], fill=(30, 65, 130, 200))
        
        # Bordo dorato interno
        draw.rounded_rectangle([4, 4, W-7, H-7], radius=5,
                                outline=(180, 140, 50), width=2)
        
        # Mini simbolo centrale
        try:
            f = ImageFont.truetype("arial.ttf", 14)
        except:
            f = ImageFont.load_default()
        
        sym = "♠"
        bbox = draw.textbbox((0, 0), sym, font=f)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((W-3-tw)//2, (H-3-th)//2), sym,
                  fill=(180, 140, 50, 220), font=f)
        
        return image


# =============================================================================
# CLIENT DI RETE
# =============================================================================

class NetworkClient:
    """Gestisce la comunicazione di rete con il server."""
    
    def __init__(self):
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.buffer = ""
        self.receive_thread: Optional[threading.Thread] = None
        self.running = False
        self.message_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None
        self._lock = threading.Lock()
    
    def connect(self, host: str, port: int) -> bool:
        """Connette al server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((host, port))
            self.socket.settimeout(None)
            self.connected = True
            self.running = True
            
            self.receive_thread = threading.Thread(
                target=self._receive_loop,
                daemon=True
            )
            self.receive_thread.start()
            
            return True
        except Exception as e:
            print(f"[CLIENT] Errore connessione: {e}")
            if self.error_callback:
                self.error_callback(f"Impossibile connettersi: {e}")
            return False
    
    def disconnect(self):
        """Chiude la connessione in modo pulito."""
        self.running = False
        self.connected = False
        
        with self._lock:
            if self.socket:
                try:
                    # Invia messaggio di disconnessione
                    self.send({"type": "disconnect"})
                    time.sleep(0.1)
                    self.socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
    
    def send(self, message: dict):
        """Invia un messaggio JSON al server."""
        if not self.connected or not self.socket:
            return
        
        with self._lock:
            try:
                data = json.dumps(message, ensure_ascii=False) + '\n'
                self.socket.sendall(data.encode('utf-8'))
            except Exception as e:
                print(f"[CLIENT] Errore invio: {e}")
                self.connected = False
    
    def set_callbacks(self, message_cb: Callable, error_cb: Callable):
        """Imposta i callback per messaggi ed errori."""
        self.message_callback = message_cb
        self.error_callback = error_cb
    
    def _receive_loop(self):
        """Loop di ricezione messaggi."""
        while self.running and self.connected:
            try:
                if not self.socket:
                    break
                
                self.socket.settimeout(0.5)
                try:
                    data = self.socket.recv(BUFFER_SIZE)
                except socket.timeout:
                    continue
                
                if not data:
                    raise ConnectionError("Connessione chiusa")
                
                self.buffer += data.decode('utf-8')
                
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        try:
                            message = json.loads(line)
                            if self.message_callback:
                                self.message_callback(message)
                        except json.JSONDecodeError:
                            pass
                            
            except (ConnectionError, OSError):
                break
            except Exception as e:
                if self.running:
                    print(f"[CLIENT] Errore ricezione: {e}")
        
        self.connected = False


# =============================================================================
# WIDGET FICHES
# =============================================================================

class ChipSelector(ctk.CTkFrame):
    """Widget per la selezione delle fiches."""
    
    def __init__(self, parent, valori_fiches: List[int], on_change: Callable = None, gui_ref=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.valori_fiches = valori_fiches
        self.on_change = on_change
        self.puntata_corrente = 0
        self.saldo_max = 0
        self.gui_ref = gui_ref  # Riferimento diretto alla BlackjackGUI
        
        self._build_ui()
    
    def _build_ui(self):
        """Costruisce l'interfaccia delle fiches."""
        # Titolo
        self.title_label = ctk.CTkLabel(
            self,
            text="💰 SELEZIONA FICHES",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORE_ORO
        )
        self.title_label.pack(pady=(0, 10))
        
        # Frame fiches (ora scrollabile)
        self.chips_scroll = ctk.CTkScrollableFrame(
            self, 
            fg_color="transparent", 
            orientation="horizontal",
            height=90
        )
        self.chips_scroll.pack(fill="x", pady=5)
        
        self.chip_buttons = {}
        for valore in self.valori_fiches:
            # Formattazione K
            display_val = str(valore)
            if valore >= 1000:
                display_val = f"{valore // 1000}K"
                
            btn = ctk.CTkButton(
                self.chips_scroll,
                text=display_val,
                width=65,
                height=65,
                corner_radius=32,
                fg_color=COLORI_FICHES.get(valore, "#888888"),
                hover_color=self._darken_color(COLORI_FICHES.get(valore, "#888888")),
                text_color="black" if valore in [1, 25, 1000, 2000] else "white",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda v=valore: self._add_chip(v)
            )
            btn.pack(side="left", padx=5)
            self.chip_buttons[valore] = btn
        
        # Display puntata
        self.bet_display_frame = ctk.CTkFrame(self, fg_color=COLORE_PANNELLO_CHIARO)
        self.bet_display_frame.pack(fill="x", pady=10, padx=5)
        
        self.bet_label = ctk.CTkLabel(
            self.bet_display_frame,
            text="Puntata: €0",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORE_ORO
        )
        self.bet_label.pack(pady=10)
        
        # Pulsanti controllo
        self.control_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.control_frame.pack(pady=5)
        
        self.btn_reset = ctk.CTkButton(
            self.control_frame,
            text="🗑️ RESET",
            width=80,
            height=35,
            fg_color=COLORE_ERRORE,
            command=self._reset_bet
        )
        self.btn_reset.pack(side="left", padx=3)
        
        self.btn_undo = ctk.CTkButton(
            self.control_frame,
            text="↩️ ANNULLA",
            width=80,
            height=35,
            fg_color=COLORE_WARNING,
            command=self._undo_last
        )
        self.btn_undo.pack(side="left", padx=3)
        
        self.btn_repeat = ctk.CTkButton(
            self.control_frame,
            text="🔁 RIPETI",
            width=80,
            height=35,
            fg_color="#2563eb",
            command=lambda: self.gui_ref._repeat_last_bet(double=False) if self.gui_ref else None
        )
        self.btn_repeat.pack(side="left", padx=3)
        
        self.btn_repeat_double = ctk.CTkButton(
            self.control_frame,
            text="2️⃣x RIPETI",
            width=80,
            height=35,
            fg_color="#7c3aed",
            command=lambda: self.gui_ref._repeat_last_bet(double=True) if self.gui_ref else None
        )
        self.btn_repeat_double.pack(side="left", padx=3)
        
        # Stack delle fiches aggiunte (per annulla)
        self.chip_stack = []
    
    def _darken_color(self, hex_color: str) -> str:
        """Scurisce un colore hex."""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = max(0, int(r * 0.7))
        g = max(0, int(g * 0.7))
        b = max(0, int(b * 0.7))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _add_chip(self, valore: int):
        """Aggiunge una fiche alla puntata."""
        if self.puntata_corrente + valore <= self.saldo_max:
            self.puntata_corrente += valore
            self.chip_stack.append(valore)
            self._update_display()
            if self.on_change:
                self.on_change(self.puntata_corrente)
    
    def _reset_bet(self):
        """Azzera la puntata."""
        self.puntata_corrente = 0
        self.chip_stack = []
        self._update_display()
        if self.on_change:
            self.on_change(self.puntata_corrente)
    
    def _undo_last(self):
        """Annulla l'ultima fiche aggiunta."""
        if self.chip_stack:
            valore = self.chip_stack.pop()
            self.puntata_corrente -= valore
            self._update_display()
            if self.on_change:
                self.on_change(self.puntata_corrente)
    
    def _update_display(self):
        """Aggiorna il display."""
        self.bet_label.configure(text=f"Puntata: €{self.puntata_corrente}")
        
        # Mostra solo fiches che il giocatore può permettersi
        for valore, btn in self.chip_buttons.items():
            if valore <= self.saldo_max:
                btn.pack(side="left", padx=5)
            else:
                btn.pack_forget()
    
    def set_max_bet(self, saldo: int):
        """Imposta il saldo massimo disponibile."""
        self.saldo_max = saldo
        self._update_display()
    
    def get_bet(self) -> int:
        """Restituisce la puntata corrente."""
        return self.puntata_corrente
    
    def reset(self):
        """Reset completo."""
        self._reset_bet()


# =============================================================================
# INTERFACCIA GRAFICA PRINCIPALE
# =============================================================================

class BlackjackGUI(ctk.CTk):
    """Finestra principale del client Blackjack."""
    
    def __init__(self):
        super().__init__()
        
        # Configurazione finestra
        self.title("♠♥ BLACKJACK MULTIPLAYER ♦♣")
        self.geometry("1300x900")
        self.minsize(1100, 750)
        self.configure(fg_color=COLORE_TAVOLO_SCURO)
        
        # Componenti
        self.network = NetworkClient()
        self.card_generator = CardImageGenerator()
        
        # Stato locale
        self.player_id: Optional[int] = None
        self.nickname = ""
        self.saldo = 0
        self.last_main_bet = 0
        self.last_pp_bet = 0
        self.game_state: Optional[dict] = None
        self.available_actions: List[str] = []
        self.valori_fiches = [1, 5, 10, 25, 50, 100, 1000, 2000, 5000, 10000]
        self.fase_corrente = ""
        
        # Overlay risultati
        self.results_overlay = None
        self.countdown_job = None
        
        # Flag
        self._is_closing = False
        self._pending_update = False  # Throttle per _update_display
        
        # Costruisci l'interfaccia
        self._build_ui()
        
        # Imposta callback
        self.network.set_callbacks(
            self._on_message_received,
            self._on_error
        )
        
        # Gestione chiusura
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Connessione
        self.after(100, self._show_connection_dialog)
    
    def _build_ui(self):
        """Costruisce tutti i componenti dell'interfaccia."""
        # Layout principale
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Area di gioco
        self._build_game_area()
        
        # Pannello laterale
        self._build_side_panel()
    
    def _build_game_area(self):
        """Costruisce l'area di gioco principale."""
        self.game_frame = ctk.CTkFrame(self, fg_color=COLORE_TAVOLO)
        self.game_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.game_frame.grid_columnconfigure(0, weight=1)
        self.game_frame.grid_rowconfigure(0, weight=1)  # Banco
        self.game_frame.grid_rowconfigure(1, weight=2)  # Giocatori
        self.game_frame.grid_rowconfigure(2, weight=0)  # Azioni
        
        # Area banco
        self._build_dealer_area()
        
        # Area giocatori
        self._build_players_area()
        
        # Area azioni
        self._build_actions_area()
        
        # Area puntate (inizialmente nascosta)
        self._build_betting_area()
    
    def _build_dealer_area(self):
        """Costruisce l'area del banco."""
        self.dealer_frame = ctk.CTkFrame(
            self.game_frame,
            fg_color=COLORE_TAVOLO_SCURO,
            corner_radius=15,
            border_width=2,
            border_color=COLORE_ORO
        )
        self.dealer_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=15)
        
        ctk.CTkLabel(
            self.dealer_frame,
            text="🎰 BANCO",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORE_ORO
        ).pack(pady=(15, 5))
        
        self.dealer_cards_frame = ctk.CTkFrame(
            self.dealer_frame,
            fg_color="transparent"
        )
        self.dealer_cards_frame.pack(pady=10)
        
        self.dealer_score_label = ctk.CTkLabel(
            self.dealer_frame,
            text="",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.dealer_score_label.pack(pady=(0, 15))
    
    def _build_players_area(self):
        """Costruisce l'area dei giocatori."""
        self.players_container = ctk.CTkFrame(
            self.game_frame,
            fg_color="transparent"
        )
        self.players_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.players_container.grid_columnconfigure(0, weight=1)
        self.players_container.grid_rowconfigure(0, weight=1)
        
        self.players_scroll = ctk.CTkScrollableFrame(
            self.players_container,
            fg_color="transparent",
            orientation="horizontal"
        )
        self.players_scroll.grid(row=0, column=0, sticky="nsew")
        
        self.player_frames: Dict[int, ctk.CTkFrame] = {}
    
    def _build_actions_area(self):
        """Costruisce l'area dei pulsanti azione."""
        self.actions_frame = ctk.CTkFrame(
            self.game_frame,
            fg_color=COLORE_PANNELLO,
            corner_radius=15,
            height=100
        )
        self.actions_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        self.actions_frame.grid_propagate(False)
        
        # Status label
        self.status_game_label = ctk.CTkLabel(
            self.actions_frame,
            text="In attesa...",
            font=ctk.CTkFont(size=14),
            text_color=COLORE_TESTO_SCURO
        )
        self.status_game_label.pack(pady=(10, 5))
        
        # Pulsanti azione
        buttons_frame = ctk.CTkFrame(self.actions_frame, fg_color="transparent")
        buttons_frame.pack(pady=10)
        
        self.btn_hit = ctk.CTkButton(
            buttons_frame,
            text="🎴 CARTA",
            width=120,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=lambda: self._send_action("hit"),
            state="disabled"
        )
        self.btn_hit.pack(side="left", padx=5)
        
        self.btn_stand = ctk.CTkButton(
            buttons_frame,
            text="✋ STAI",
            width=120,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#ca8a04",
            hover_color="#a16207",
            command=lambda: self._send_action("stand"),
            state="disabled"
        )
        self.btn_stand.pack(side="left", padx=5)
        
        self.btn_double = ctk.CTkButton(
            buttons_frame,
            text="💰 RADDOPPIA",
            width=130,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#dc2626",
            hover_color="#b91c1c",
            command=lambda: self._send_action("double"),
            state="disabled"
        )
        self.btn_double.pack(side="left", padx=5)
        
        self.btn_split = ctk.CTkButton(
            buttons_frame,
            text="✂️ SPLIT",
            width=120,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            command=lambda: self._send_action("split"),
            state="disabled"
        )
        self.btn_split.pack(side="left", padx=5)
    
    def _build_betting_area(self):
        """Costruisce l'area per le puntate con fiches."""
        self.betting_frame = ctk.CTkFrame(
            self.game_frame,
            fg_color=COLORE_PANNELLO,
            corner_radius=15
        )
        # Non mostrato inizialmente
        
        # Chip selector principale
        self.main_chip_selector = ChipSelector(
            self.betting_frame,
            valori_fiches=self.valori_fiches,
            on_change=self._on_main_bet_change,
            gui_ref=self
        )
        self.main_chip_selector.pack(fill="x", padx=20, pady=10)
        
        # Separatore
        ctk.CTkLabel(
            self.betting_frame,
            text="─" * 40,
            text_color=COLORE_TESTO_SCURO
        ).pack()
        
        # Side bet (Perfect Pair)
        self.sidebet_label = ctk.CTkLabel(
            self.betting_frame,
            text="🎯 SIDE BET - Perfect Pair",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORE_ARGENTO
        )
        self.sidebet_label.pack(pady=(10, 5))
        
        self.sidebet_info = ctk.CTkLabel(
            self.betting_frame,
            text="Perfect: 25:1 | Colored: 12:1 | Mixed: 6:1",
            font=ctk.CTkFont(size=11),
            text_color=COLORE_TESTO_SCURO
        )
        self.sidebet_info.pack()
        
        self.sidebet_chip_selector = ChipSelector(
            self.betting_frame,
            valori_fiches=[1, 5, 10, 25],
            on_change=self._on_sidebet_change,
            gui_ref=self
        )
        self.sidebet_chip_selector.pack(fill="x", padx=20, pady=10)
        
        # Pulsante conferma
        self.btn_confirm_bet = ctk.CTkButton(
            self.betting_frame,
            text="✅ CONFERMA E GIOCA",
            width=250,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORE_SUCCESSO,
            hover_color="#00b359",
            command=self._confirm_bet
        )
        self.btn_confirm_bet.pack(pady=15)
    
    def _build_side_panel(self):
        """Costruisce il pannello laterale."""
        self.side_panel = ctk.CTkFrame(self, fg_color=COLORE_PANNELLO)
        self.side_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        
        # Info giocatore
        self.info_frame = ctk.CTkFrame(self.side_panel, fg_color=COLORE_PANNELLO_CHIARO)
        self.info_frame.pack(fill="x", padx=10, pady=10)
        
        self.nickname_label = ctk.CTkLabel(
            self.info_frame,
            text="👤 Giocatore",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORE_ORO
        )
        self.nickname_label.pack(pady=(10, 5))
        
        self.balance_label = ctk.CTkLabel(
            self.info_frame,
            text="💵 €0",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORE_SUCCESSO
        )
        self.balance_label.pack(pady=5)
        
        self.status_label = ctk.CTkLabel(
            self.info_frame,
            text="Stato: Disconnesso",
            font=ctk.CTkFont(size=12),
            text_color=COLORE_TESTO_SCURO
        )
        self.status_label.pack(pady=(5, 10))
        
        # Log eventi
        ctk.CTkLabel(
            self.side_panel,
            text="📋 Eventi",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(10, 5))
        
        self.log_text = ctk.CTkTextbox(
            self.side_panel,
            width=280,
            height=200,
            font=ctk.CTkFont(size=11),
            fg_color=COLORE_PANNELLO_CHIARO
        )
        self.log_text.pack(fill="x", padx=10, pady=5)
        
        # Info Mazzo
        self.deck_frame = ctk.CTkFrame(self.side_panel, fg_color=COLORE_PANNELLO_CHIARO)
        self.deck_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.deck_label = ctk.CTkLabel(
            self.deck_frame,
            text="🎴 Carte nel mazzo: --",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORE_ARGENTO
        )
        self.deck_label.pack(pady=10)
        
        # Area Chat
        ctk.CTkLabel(
            self.side_panel,
            text="💬 Chat",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(10, 5))
        
        self.chat_frame = ctk.CTkFrame(self.side_panel, fg_color="transparent")
        self.chat_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.chat_text = ctk.CTkTextbox(
            self.chat_frame,
            height=150,
            font=ctk.CTkFont(size=11),
            fg_color=COLORE_PANNELLO_CHIARO,
            state="disabled"
        )
        self.chat_text.pack(fill="both", expand=True, pady=(0, 5))
        # Configura i tag una volta sola (solo foreground, font non supportato da CTkTextbox)
        self.chat_text.tag_config("time", foreground=COLORE_TESTO_SCURO)
        self.chat_text.tag_config("nick_self", foreground=COLORE_ORO)
        self.chat_text.tag_config("nick_other", foreground=COLORE_TESTO)
        self.chat_text.tag_config("nick_sistema", foreground=COLORE_WARNING)
        
        chat_input_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        chat_input_frame.pack(fill="x")
        
        self.chat_entry = ctk.CTkEntry(
            chat_input_frame,
            placeholder_text="Scrivi un messaggio...",
            font=ctk.CTkFont(size=12)
        )
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.chat_entry.bind("<Return>", lambda e: self._send_chat())
        
        self.btn_send_chat = ctk.CTkButton(
            chat_input_frame,
            text="Invia",
            width=60,
            command=self._send_chat
        )
        self.btn_send_chat.pack(side="right")
        
        # Pulsanti
        self.buttons_frame = ctk.CTkFrame(self.side_panel, fg_color="transparent")
        self.buttons_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_disconnect = ctk.CTkButton(
            self.buttons_frame,
            text="🚪 DISCONNETTI",
            fg_color=COLORE_ERRORE,
            hover_color="#cc3344",
            command=self._disconnect
        )
        self.btn_disconnect.pack(fill="x", pady=2)
    
    # =========================================================================
    # DIALOGHI
    # =========================================================================
    
    def _show_connection_dialog(self):
        """Mostra il dialogo di connessione."""
        dialog = ConnectionDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            host, port = dialog.result
            self._connect(host, port)
        else:
            self._connect(SERVER_HOST, SERVER_PORT)
    
    def _show_balance_dialog(self, min_val: int, max_val: int, default: int):
        """Mostra il dialogo per selezionare il saldo iniziale."""
        dialog = BalanceDialog(self, min_val, max_val, default)
        self.wait_window(dialog)
        
        if dialog.result:
            self.network.send({"type": "set_initial_balance", "value": dialog.result})
    
    def _show_nickname_dialog(self):
        """Mostra il dialogo per inserire il nickname."""
        dialog = ctk.CTkInputDialog(
            text="Inserisci il tuo nickname:",
            title="Scegli Nickname"
        )
        result = dialog.get_input()
        
        nickname = result.strip()[:20] if result else "Giocatore"
        self.network.send({"type": "nickname", "value": nickname})
    
    def _show_insurance_dialog(self, costo: int):
        """Mostra il dialogo per l'assicurazione."""
        dialog = InsuranceDialog(self, costo)
        self.wait_window(dialog)
        
        self.network.send({"type": "insurance", "value": dialog.result})
    
    # =========================================================================
    # GESTIONE RETE
    # =========================================================================
    
    def _connect(self, host: str, port: int):
        """Connette al server."""
        self._log(f"Connessione a {host}:{port}...")
        
        if self.network.connect(host, port):
            self._log("✅ Connesso!")
            self.status_label.configure(text="Stato: Connesso")
        else:
            self._log("❌ Connessione fallita")
            self.status_label.configure(text="Stato: Errore")
    
    def _disconnect(self):
        """Disconnette dal server."""
        self._is_closing = True
        self.network.disconnect()
        self._log("Disconnesso")
        self.status_label.configure(text="Stato: Disconnesso")
        self._disable_all_actions()
        self.after(500, self.destroy)
    
    def _on_closing(self):
        """Gestisce la chiusura della finestra."""
        self._is_closing = True
        self.network.disconnect()
        self.destroy()
    
    def _on_message_received(self, message: dict):
        """Callback per messaggi ricevuti."""
        if self._is_closing:
            return
        self.after(0, lambda: self._process_message(message))
    
    def _on_error(self, error: str):
        """Callback per errori."""
        if self._is_closing:
            return
        self.after(0, lambda: self._handle_error(error))
    
    def _handle_error(self, error: str):
        """Gestisce errori."""
        self._log(f"❌ {error}")
        self.status_label.configure(text="Stato: Errore")
    
    def _process_message(self, message: dict):
        """Processa un messaggio dal server."""
        msg_type = message.get("type", "")
        
        handlers = {
            "welcome": self._handle_welcome,
            "balance_set": self._handle_balance_set,
            "request_nickname": self._handle_request_nickname,
            "nickname_accepted": self._handle_nickname_accepted,
            "lobby_state": self._handle_lobby_state,
            "waiting_for_bet": self._handle_waiting_for_bet,
            "bet_updated": self._handle_bet_updated,
            "bet_confirmed": self._handle_bet_confirmed,
            "game_state": self._handle_game_state,
            "perfect_pair_result": self._handle_perfect_pair_result,
            "request_action": self._handle_request_action,
            "offer_insurance": self._handle_offer_insurance,
            "insurance_response": self._handle_insurance_response,
            "card_dealt": self._handle_card_dealt,
            "double_down": self._handle_double_down,
            "split": self._handle_split,
            "dealer_reveal": self._handle_dealer_reveal,
            "dealer_card": self._handle_dealer_card,
            "round_results": self._handle_round_results,
            "hand_complete": self._handle_hand_complete,
            "chat": self._handle_chat_message,
            "player_disconnected": self._handle_player_disconnected,
            "server_shutdown": self._handle_server_shutdown,
            "error": self._handle_server_error
        }
        
        handler = handlers.get(msg_type)
        if handler:
            handler(message)
    
    # =========================================================================
    # HANDLER MESSAGGI
    # =========================================================================
    
    def _handle_welcome(self, msg: dict):
        """Gestisce il benvenuto."""
        self.player_id = msg.get("player_id")
        self.valori_fiches = msg.get("valori_fiches", self.valori_fiches)
        
        self._log(f"✨ {msg.get('message', 'Benvenuto!')}")
        
        # Mostra dialogo saldo
        self.after(100, lambda: self._show_balance_dialog(
            msg.get("saldo_min", 100),
            msg.get("saldo_max", 10000),
            msg.get("saldo_default", 500)
        ))
    
    def _handle_balance_set(self, msg: dict):
        """Gestisce la conferma del saldo."""
        self.saldo = msg.get("saldo", 0)
        self.balance_label.configure(text=f"💵 €{self.saldo}")
        self._log(f"💰 Saldo iniziale: €{self.saldo}")
    
    def _handle_request_nickname(self, msg: dict):
        """Gestisce la richiesta nickname."""
        self.after(100, self._show_nickname_dialog)
    
    def _handle_nickname_accepted(self, msg: dict):
        """Gestisce l'accettazione del nickname."""
        self.nickname = msg.get("nickname", "")
        self.nickname_label.configure(text=f"👤 {self.nickname}")
        self._log(f"✅ Nickname: {self.nickname}")
    
    def _handle_lobby_state(self, msg: dict):
        """Gestisce lo stato della lobby."""
        num = msg.get("num_giocatori", 0)
        self._log(f"👥 Giocatori: {num}")
        self.status_label.configure(text=f"In lobby: {num} giocatori")
    
    def _handle_waiting_for_bet(self, msg: dict):
        """Gestisce l'attesa puntata."""
        self.saldo = msg.get("saldo", self.saldo)
        self.balance_label.configure(text=f"💵 €{self.saldo}")
        
        self.fase_corrente = "puntata"
        self.status_game_label.configure(text="Seleziona la tua puntata")
        
        # Configura e mostra area puntate
        self.main_chip_selector.set_max_bet(self.saldo)
        self.main_chip_selector.reset()
        self.sidebet_chip_selector.set_max_bet(min(self.saldo, 100))
        self.sidebet_chip_selector.reset()
        
        # Mostra area puntate, nascondi azioni
        self.actions_frame.grid_remove()
        self.betting_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        
        self._log("🎰 Seleziona la puntata e conferma")
    
    def _handle_bet_updated(self, msg: dict):
        """Gestisce l'aggiornamento della puntata."""
        pass  # Gestito localmente
    
    def _handle_bet_confirmed(self, msg: dict):
        """Gestisce la conferma della puntata."""
        puntata = msg.get("puntata", 0)
        pp = msg.get("perfect_pair", 0)
        self.saldo = msg.get("saldo", self.saldo)
        
        # Salva per "Ripeti Puntata"
        self.last_main_bet = puntata
        self.last_pp_bet = pp
        
        self.balance_label.configure(text=f"💵 €{self.saldo}")
        
        # Nascondi area puntate, mostra azioni
        self.betting_frame.grid_remove()
        self.actions_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        self.status_game_label.configure(text="In attesa degli altri giocatori...")
    
    def _handle_game_state(self, msg: dict):
        """Gestisce l'aggiornamento dello stato — coalescenza rapida."""
        self.game_state = msg
        if not self._pending_update:
            self._pending_update = True
            self.after(50, self._flush_display_update)

    def _flush_display_update(self):
        """Esegue il ridisegno effettivo dopo la coalescenza."""
        self._pending_update = False
        self._update_display()
    
    def _handle_perfect_pair_result(self, msg: dict):
        """Gestisce il risultato della side bet Perfect Pair."""
        tipo = msg.get("risultato")
        moltiplicatore = msg.get("moltiplicatore", 0)
        vincita = msg.get("vincita", 0)
        saldo = msg.get("saldo", self.saldo)
        
        if moltiplicatore > 0:
            self._log(f"🎯 Perfect Pair! {tipo.upper()} - Vinto €{vincita}")
        
        self.saldo = saldo
        self.balance_label.configure(text=f"💵 €{self.saldo}")
    
    def _handle_request_action(self, msg: dict):
        """Gestisce la richiesta di azione."""
        self.available_actions = msg.get("azioni", [])
        mano_attiva = msg.get("mano_attiva", 0)
        num_mani = msg.get("num_mani", 1)
        
        self._update_action_buttons()
        
        if num_mani > 1:
            self.status_game_label.configure(
                text=f"🎯 Il tuo turno! Mano {mano_attiva + 1} di {num_mani}"
            )
        else:
            self.status_game_label.configure(text="🎯 Il tuo turno!")
    
    def _handle_offer_insurance(self, msg: dict):
        """Gestisce l'offerta di assicurazione."""
        costo = msg.get("costo", 0)
        self.after(100, lambda: self._show_insurance_dialog(costo))
    
    def _handle_insurance_response(self, msg: dict):
        """Gestisce la risposta all'assicurazione."""
        assicurazione = msg.get("assicurazione", 0)
        self.saldo = msg.get("saldo", self.saldo)
        self.balance_label.configure(text=f"💵 €{self.saldo}")
        
        if assicurazione > 0:
            self._log(f"🛡️ Assicurazione presa: €{assicurazione}")
    
    def _handle_card_dealt(self, msg: dict):
        """Gestisce una carta distribuita."""
        pass
    
    def _handle_double_down(self, msg: dict):
        """Gestisce un double down."""
        player_id = msg.get("player_id")
        self.saldo = msg.get("saldo", self.saldo)
        
        if player_id == self.player_id:
            self.balance_label.configure(text=f"💵 €{self.saldo}")
    
    def _handle_split(self, msg: dict):
        """Gestisce uno split."""
        player_id = msg.get("player_id")
        self.saldo = msg.get("saldo", self.saldo)
        
        if player_id == self.player_id:
            self.balance_label.configure(text=f"💵 €{self.saldo}")
    
    def _handle_dealer_reveal(self, msg: dict):
        """Gestisce la rivelazione del banco."""
        pass
    
    def _handle_dealer_card(self, msg: dict):
        """Gestisce una carta del banco."""
        pass
    
    def _handle_round_results(self, msg: dict):
        """Gestisce i risultati del round: log dettagliato + overlay catchy."""
        banco = msg.get("banco", {})
        risultati = msg.get("risultati", [])

        # --- Log dettagliato ---
        self._log("\n" + "=" * 30)
        self._log("📊 RISULTATI")
        punteggio_banco = banco.get("punteggio", 0)
        if banco.get("is_sballato"):
            self._log(f"🎰 Banco: SBALLATO ({punteggio_banco})")
        else:
            self._log(f"🎰 Banco: {punteggio_banco}")

        for r in risultati:
            nickname = r.get("nickname", "?")
            nuovo_saldo = r.get("nuovo_saldo", 0)
            self._log(f"\n👤 {nickname}:")
            for mano in r.get("risultati_mani", []):
                risultato = mano.get("risultato", "?")
                punteggio = mano.get("punteggio", 0)
                vincita = mano.get("vincita", 0)
                emoji = {"vittoria": "✅", "sconfitta": "❌", "pareggio": "🟡",
                         "blackjack": "🎰", "sballato": "💥"}.get(risultato, "❓")
                self._log(f"  {emoji} {risultato.upper()} ({punteggio}) €{vincita}")
            self._log(f"  💵 Saldo: €{nuovo_saldo}")
        self._log("=" * 30 + "\n")

        # --- Overlay e aggiornamento saldo per il giocatore locale ---
        mio_risultato = next((r for r in risultati if r.get("player_id") == self.player_id), None)
        if mio_risultato:
            vincita = (mio_risultato.get("vincita_totale", 0) +
                       mio_risultato.get("vincita_assicurazione", 0) +
                       mio_risultato.get("vincita_perfect_pair", 0))
            puntata_totale = sum(
                m.get("puntata", 0) for m in mio_risultato.get("risultati_mani", [])
            )
            self._show_results_overlay(vincita, puntata_totale)
            self.saldo = mio_risultato.get("nuovo_saldo", self.saldo)
            self.balance_label.configure(text=f"💵 €{self.saldo}")
            if mio_risultato.get("risultati_mani"):
                self.last_main_bet = mio_risultato["risultati_mani"][0].get("puntata", 0)

        self._disable_all_actions()
    
    def _handle_hand_complete(self, msg: dict):
        """Gestisce il completamento della mano."""
        self.saldo = msg.get("saldo", self.saldo)
        puo_giocare = msg.get("puo_giocare", False)
        self.balance_label.configure(text=f"💵 €{self.saldo}")
        if not puo_giocare:
            # Annulla il countdown e mostra messaggio saldo insufficiente
            if self.countdown_job:
                self.after_cancel(self.countdown_job)
                self.countdown_job = None
            if self.results_overlay and self.results_overlay.winfo_exists():
                self.results_overlay.destroy()
                self.results_overlay = None
            self.status_game_label.configure(text="❌ Saldo insufficiente per continuare")
            self._log("❌ Saldo insufficiente per continuare")
    
    def _handle_player_disconnected(self, msg: dict):
        """Gestisce la disconnessione di un giocatore."""
        nickname = msg.get("nickname", "Giocatore")
        player_id = msg.get("player_id")
        
        self._log(f"👋 {nickname} si è disconnesso")
        
        if player_id in self.player_frames:
            self.player_frames[player_id].destroy()
            del self.player_frames[player_id]
    
    def _handle_server_shutdown(self, msg: dict):
        """Gestisce lo shutdown del server."""
        self._log("⚠️ Server in chiusura")
        self._disable_all_actions()
    
    def _handle_server_error(self, msg: dict):
        """Gestisce errori dal server."""
        error = msg.get("message", "Errore")
        self._log(f"⚠️ {error}")
    
    # =========================================================================
    # AGGIORNAMENTO DISPLAY
    # =========================================================================
    
    def _update_display(self):
        """Aggiorna il display."""
        if not self.game_state:
            return
        
        self._update_dealer_display()
        self._update_players_display()
        
        # Aggiorna info mazzo
        mazzo_stats = self.game_state.get("mazzo_stats", {})
        rimanenti = mazzo_stats.get("rimanenti", "--")
        totali = mazzo_stats.get("totali", "")
        if totali:
            self.deck_label.configure(text=f"🎴 Carte: {rimanenti} / {totali}")
        else:
            self.deck_label.configure(text=f"🎴 Carte nel mazzo: {rimanenti}")
        
        fase = self.game_state.get("fase", "")
        if fase and fase != self.fase_corrente:
            self.fase_corrente = fase
    
    def _update_dealer_display(self):
        """Aggiorna la visualizzazione del banco."""
        banco = self.game_state.get("banco", {})
        carte = banco.get("carte", [])
        punteggio = banco.get("punteggio", 0)
        carta_nascosta = banco.get("carta_nascosta", False)
        
        for widget in self.dealer_cards_frame.winfo_children():
            widget.destroy()
        
        for carta in carte:
            valore = carta.get("valore", "?")
            seme = carta.get("seme", "")
            
            if valore == "?" or seme == "nascosto":
                img = self.card_generator.get_back_image()
            else:
                img = self.card_generator.get_card_image(valore, seme)
            
            label = ctk.CTkLabel(self.dealer_cards_frame, image=img, text="")
            label.pack(side="left", padx=2)
        
        if carta_nascosta:
            self.dealer_score_label.configure(
                text=f"Punteggio: {punteggio}+?",
                text_color=COLORE_TESTO
            )
        elif banco.get("is_sballato"):
            self.dealer_score_label.configure(
                text=f"SBALLATO! ({punteggio})",
                text_color=COLORE_ERRORE
            )
        else:
            self.dealer_score_label.configure(
                text=f"Punteggio: {punteggio}",
                text_color=COLORE_TESTO
            )
    
    def _update_players_display(self):
        """Aggiorna la visualizzazione dei giocatori."""
        giocatori = self.game_state.get("giocatori", [])
        giocatore_corrente = self.game_state.get("giocatore_corrente")
        
        ids_attivi = set()
        
        for g in giocatori:
            player_id = g.get("id")
            ids_attivi.add(player_id)
            
            if player_id not in self.player_frames:
                frame = self._create_player_frame(player_id)
                self.player_frames[player_id] = frame
            
            self._update_player_frame(
                self.player_frames[player_id],
                g,
                is_current=(player_id == giocatore_corrente),
                is_self=(player_id == self.player_id)
            )
        
        for pid in list(self.player_frames.keys()):
            if pid not in ids_attivi:
                self.player_frames[pid].destroy()
                del self.player_frames[pid]
        
        # Forza refresh layout
        self.update_idletasks()
    
    def _create_player_frame(self, player_id: int) -> ctk.CTkFrame:
        """Crea un frame per un giocatore."""
        frame = ctk.CTkFrame(
            self.players_scroll,
            fg_color=COLORE_PANNELLO,
            corner_radius=12,
            width=300
        )
        frame.pack(side="left", padx=8, pady=5, fill="y")
        frame.pack_propagate(False)
        
        frame.player_id = player_id
        
        # Header
        frame.header = ctk.CTkFrame(frame, fg_color=COLORE_PANNELLO_CHIARO, corner_radius=8)
        frame.header.pack(fill="x", padx=5, pady=5)
        
        frame.name_label = ctk.CTkLabel(
            frame.header,
            text="",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        frame.name_label.pack(pady=5)
        
        frame.balance_label = ctk.CTkLabel(
            frame.header,
            text="",
            font=ctk.CTkFont(size=12)
        )
        frame.balance_label.pack(pady=(0, 5))
        
        # Area mani (scrollabile per supportare split multipli)
        frame.hands_scroll = ctk.CTkScrollableFrame(
            frame,
            fg_color="transparent",
            height=280
        )
        frame.hands_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        return frame
    
    def _update_player_frame(self, frame: ctk.CTkFrame, data: dict,
                             is_current: bool, is_self: bool):
        """Aggiorna il frame di un giocatore."""
        nickname = data.get("nickname", f"Giocatore {data.get('id')}")
        saldo = data.get("saldo", 0)
        mani = data.get("mani", [])
        mano_attiva = data.get("mano_attiva", 0)
        pp_result = data.get("perfect_pair_risultato")
        
        # Evidenziazione
        if is_current:
            frame.configure(border_width=3, border_color=COLORE_ORO)
        else:
            frame.configure(border_width=0)
        
        # Nome
        nome = f"⭐ {nickname}" if is_self else nickname
        if is_current:
            nome = f"🎯 {nome}"
        
        frame.name_label.configure(
            text=nome,
            text_color=COLORE_ORO if is_self else COLORE_TESTO
        )
        
        frame.balance_label.configure(text=f"€{saldo}")
        
        # Pulisci mani precedenti
        for widget in frame.hands_scroll.winfo_children():
            widget.destroy()
        
        # Mostra ogni mano
        for idx, mano in enumerate(mani):
            self._create_hand_display(
                frame.hands_scroll,
                mano,
                idx,
                is_active=(idx == mano_attiva and is_current),
                total_hands=len(mani)
            )
        
        # Perfect Pair
        if pp_result and pp_result[1] > 0:
            pp_frame = ctk.CTkFrame(frame.hands_scroll, fg_color=COLORE_SUCCESSO, corner_radius=6)
            pp_frame.pack(fill="x", pady=5, padx=2)
            ctk.CTkLabel(
                pp_frame,
                text=f"🎯 Perfect Pair: {pp_result[0].upper()} (x{pp_result[1]})",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="white"
            ).pack(pady=3)
    
    def _create_hand_display(self, parent: ctk.CTkFrame, mano: dict,
                             index: int, is_active: bool, total_hands: int):
        """Crea la visualizzazione completa di una mano (incluso split)."""
        # Frame della mano con bordo se attiva
        if is_active:
            hand_frame = ctk.CTkFrame(
                parent,
                fg_color=COLORE_TAVOLO_SCURO,
                corner_radius=10,
                border_width=2,
                border_color=COLORE_ORO
            )
        else:
            hand_frame = ctk.CTkFrame(
                parent,
                fg_color=COLORE_TAVOLO_SCURO,
                corner_radius=10
            )
        hand_frame.pack(fill="x", pady=5, padx=2)
        
        # Header della mano
        header_frame = ctk.CTkFrame(hand_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=8, pady=(8, 2))
        
        # Titolo mano (mostra numero se ci sono più mani)
        if total_hands > 1:
            hand_title = f"Mano {index + 1}"
            if is_active:
                hand_title = f"▶ {hand_title}"
        else:
            hand_title = "La tua mano"
            if is_active:
                hand_title = f"▶ {hand_title}"
        
        ctk.CTkLabel(
            header_frame,
            text=hand_title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORE_ORO if is_active else COLORE_TESTO
        ).pack(side="left")
        
        # Puntata
        puntata = mano.get("puntata", 0)
        is_doubled = mano.get("is_doubled", False)
        puntata_text = f"€{puntata}"
        if is_doubled:
            puntata_text += " (2x)"
        
        ctk.CTkLabel(
            header_frame,
            text=puntata_text,
            font=ctk.CTkFont(size=11),
            text_color=COLORE_ORO
        ).pack(side="right")
        
        # Frame carte
        cards_frame = ctk.CTkFrame(hand_frame, fg_color="transparent")
        cards_frame.pack(pady=8)
        
        # Mostra le carte
        carte = mano.get("carte", [])
        for carta in carte:
            valore = carta.get("valore", "?")
            seme = carta.get("seme", "")
            
            if valore and seme:
                img = self.card_generator.get_card_image(valore, seme)
                label = ctk.CTkLabel(cards_frame, image=img, text="")
                label.pack(side="left", padx=2)
        
        # Punteggio e stato
        punteggio = mano.get("punteggio", 0)
        is_sballato = mano.get("is_sballato", False)
        is_blackjack = mano.get("is_blackjack", False)
        is_stand = mano.get("is_stand", False)
        
        status_frame = ctk.CTkFrame(hand_frame, fg_color="transparent")
        status_frame.pack(fill="x", padx=8, pady=(0, 8))
        
        # Determina testo e colore del punteggio
        if is_blackjack:
            score_text = "🎰 BLACKJACK!"
            score_color = COLORE_ORO
        elif is_sballato:
            score_text = f"💥 SBALLATO ({punteggio})"
            score_color = COLORE_ERRORE
        elif is_stand:
            score_text = f"✋ {punteggio}"
            score_color = COLORE_ARGENTO
        else:
            score_text = f"Totale: {punteggio}"
            score_color = COLORE_TESTO
        
        ctk.CTkLabel(
            status_frame,
            text=score_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=score_color
        ).pack()
    
    def _update_action_buttons(self):
        """Aggiorna lo stato dei pulsanti azione."""
        button_map = {
            "hit": self.btn_hit,
            "stand": self.btn_stand,
            "double": self.btn_double,
            "split": self.btn_split
        }
        
        for action, button in button_map.items():
            if action in self.available_actions:
                button.configure(state="normal")
            else:
                button.configure(state="disabled")
    
    def _disable_all_actions(self):
        """Disabilita tutti i pulsanti azione."""
        self.available_actions = []
        self.btn_hit.configure(state="disabled")
        self.btn_stand.configure(state="disabled")
        self.btn_double.configure(state="disabled")
        self.btn_split.configure(state="disabled")
        self.status_game_label.configure(text="In attesa...")
    
    # =========================================================================
    # AZIONI UTENTE
    # =========================================================================
    
    def _send_action(self, action: str):
        """Invia un'azione al server."""
        if action not in self.available_actions:
            return
        
        # Avviso se si chiede carta con 17 o più
        if action == "hit":
            punteggio = 0
            for g in self.game_state.get("giocatori", []):
                if g.get("id") == self.player_id:
                    mani = g.get("mani", [])
                    mano_attiva = g.get("mano_attiva", 0)
                    if 0 <= mano_attiva < len(mani):
                        punteggio = mani[mano_attiva].get("punteggio", 0)
            
            if punteggio >= 17:
                if not self._show_hit_warning(punteggio):
                    return

        self.network.send({"type": "action", "value": action})
        self._disable_all_actions()
        
        action_names = {
            "hit": "CARTA",
            "stand": "STAI",
            "double": "RADDOPPIA",
            "split": "SPLIT"
        }
        self._log(f"▶️ {action_names.get(action, action)}")
    
    def _repeat_last_bet(self, double: bool = False):
        """Ripete l'ultima puntata effettuata."""
        if self.last_main_bet == 0:
            self._show_error_message("Nessuna puntata da ripetere", color=COLORE_WARNING)
            return
            
        main_bet = self.last_main_bet
        pp_bet = self.last_pp_bet
        
        if double:
            main_bet *= 2
            pp_bet *= 2
            
        total = main_bet + pp_bet
        if total > self.saldo:
            self._show_error_message("Saldo insufficiente!", color=COLORE_ERRORE)
            return
            
        # Imposta direttamente i valori nei selettori
        self.main_chip_selector.puntata_corrente = main_bet
        self.main_chip_selector.chip_stack = [main_bet]
        self.main_chip_selector._update_display()
        
        self.sidebet_chip_selector.puntata_corrente = pp_bet
        self.sidebet_chip_selector.chip_stack = [pp_bet] if pp_bet > 0 else []
        self.sidebet_chip_selector._update_display()
        
        # Sincronizza con il server
        self._on_main_bet_change(main_bet)
        self._log(f"🔁 Ripetuta puntata: €{main_bet}" + (f" + PP €{pp_bet}" if pp_bet > 0 else ""))

    def _show_results_overlay(self, vincita: int, puntata: int):
        """Mostra un overlay catchy con il risultato reale."""
        if self.results_overlay:
            self.results_overlay.destroy()
            
        if self.countdown_job:
            self.after_cancel(self.countdown_job)
            
        self.results_overlay = ctk.CTkFrame(
            self.game_frame,
            fg_color=("#1a1a2e", "#1a1a2e"),
            corner_radius=20,
            border_width=3,
            border_color=COLORE_ORO
        )
        self.results_overlay.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.6, relheight=0.4)
        
        # Logica Vincita/Pareggio/Sconfitta
        if vincita > puntata:
            text = f"🎉 HAI VINTO!\n€{vincita}"
            color = COLORE_SUCCESSO
            subtext = "La fortuna ti sorride! ✨"
            self.results_overlay.configure(border_color=COLORE_SUCCESSO)
        elif vincita == puntata and puntata > 0:
            text = "PAREGGIO 🤝"
            color = COLORE_ORO
            subtext = "Puntata restituita."
            self.results_overlay.configure(border_color=COLORE_ORO)
        else:
            text = "HAI PERSO! ❌"
            color = COLORE_ERRORE
            subtext = "Ritenta, la prossima sarà quella buona! 🍀"
            self.results_overlay.configure(border_color=COLORE_ERRORE)
            
        ctk.CTkLabel(
            self.results_overlay,
            text=text,
            font=ctk.CTkFont(size=40, weight="bold"),
            text_color=color
        ).pack(expand=True, pady=(20, 0))
        
        ctk.CTkLabel(
            self.results_overlay,
            text=subtext,
            font=ctk.CTkFont(size=18),
            text_color=COLORE_TESTO_SCURO
        ).pack(expand=True, pady=(0, 10))
        
        self.countdown_label = ctk.CTkLabel(
            self.results_overlay,
            text="Nuova mano in 6 secondi...",
            font=ctk.CTkFont(size=14, slant="italic"),
            text_color=COLORE_ORO
        )
        self.countdown_label.pack(pady=15)
        
        # Avvia il countdown reale
        self._update_countdown(6)

    def _update_countdown(self, seconds: int):
        """Aggiorna il testo del countdown ogni secondo."""
        if not self.results_overlay or not self.results_overlay.winfo_exists():
            return
        try:
            if seconds > 0:
                self.countdown_label.configure(text=f"Nuova mano in {seconds} secondi...")
                self.countdown_job = self.after(1000, lambda: self._update_countdown(seconds - 1))
            else:
                self._auto_new_hand()
        except Exception:
            pass

    def _auto_new_hand(self):
        """Nasconde overlay e richiede nuova mano automaticamente."""
        if self.results_overlay:
            self.results_overlay.destroy()
            self.results_overlay = None
        
        if self.countdown_job:
            self.after_cancel(self.countdown_job)
            self.countdown_job = None
            
        # Richiede automaticamente la nuova mano al server
        self.network.send({"type": "new_hand"})
        self._log("🎮 Nuova mano avviata automaticamente")

    def _on_main_bet_change(self, value: int):
        """Callback per cambio puntata principale."""
        # NON aggiornare last_main_bet qui: quello tiene l'ultima puntata *confermata*.
        # Aggiorna solo il massimo della side bet e sincronizza col server.
        remaining = self.saldo - value
        self.sidebet_chip_selector.set_max_bet(min(remaining, 100))
        self.network.send({"type": "place_bet", "value": value})
    
    def _on_sidebet_change(self, value: int):
        """Callback per cambio side bet."""
        self.last_pp_bet = value

    def _confirm_bet(self):
        """Conferma la puntata e avvia la mano."""
        puntata = self.main_chip_selector.get_bet()
        perfect_pair = self.sidebet_chip_selector.get_bet()
        
        # Validazione
        if puntata < 1:
            self._log("⚠️ Devi puntare almeno €1!")
            self._show_error_message("Puntata minima €1")
            return
        
        if puntata + perfect_pair > self.saldo:
            self._log("⚠️ Saldo insufficiente!")
            self._show_error_message("Saldo insufficiente")
            return
        
        # Invia conferma al server
        self.network.send({
            "type": "confirm_bet",
            "perfect_pair": perfect_pair
        })
    
    def _send_chat(self):
        """Invia un messaggio in chat."""
        testo = self.chat_entry.get().strip()
        if testo:
            self.network.send({"type": "chat", "message": testo})
            self.chat_entry.delete(0, "end")
    
    def _handle_chat_message(self, msg: dict):
        """Gestisce la ricezione di un messaggio chat."""
        nickname = msg.get("nickname", "Sistema")
        testo = msg.get("message", "")
        player_id = msg.get("player_id")
        
        timestamp = time.strftime("%H:%M")
        
        self.chat_text.configure(state="normal")
            
        if nickname == "Sistema":
            nick_tag = "nick_sistema"
        elif player_id == self.player_id:
            nick_tag = "nick_self"
        else:
            nick_tag = "nick_other"

        self.chat_text.insert("end", f"[{timestamp}] ", "time")
        self.chat_text.insert("end", f"{nickname}: ", nick_tag)
        self.chat_text.insert("end", f"{testo}\n")
        
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")
    
    def _request_new_hand(self):
        """Richiede una nuova mano."""
        self.network.send({"type": "new_hand"})
        self._log("🎮 Richiesta nuova mano...")
    
    def _show_error_message(self, message: str, color: str = None):
        """Mostra un messaggio di errore temporaneo."""
        text_color = color if color else COLORE_ERRORE
        error_label = ctk.CTkLabel(
            self.betting_frame,
            text=f"⚠️ {message}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=text_color
        )
        error_label.pack(pady=5)
        self.after(2000, error_label.destroy)
    
    # =========================================================================
    # UTILITY
    # =========================================================================
    
    def _log(self, message: str):
        """Aggiunge un messaggio al log (max 500 righe)."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        # Taglia il log se supera 500 righe
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > 500:
            self.log_text.delete("1.0", "50.0")
        self.log_text.see("end")

    def _show_hit_warning(self, punteggio: int) -> bool:
        """Mostra un avviso se si chiede carta con punteggio alto."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Sei sicuro?")
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        
        result = {"value": False}
        
        def _confirm(choice: bool):
            result["value"] = choice
            dialog.destroy()
            
        ctk.CTkLabel(
            dialog,
            text="⚠️ ATTENZIONE",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORE_WARNING
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            dialog,
            text=f"Hai un punteggio di {punteggio}.\nPescare un'altra carta è rischioso!",
            font=ctk.CTkFont(size=14),
            justify="center"
        ).pack(pady=10)
        
        ctk.CTkLabel(
            dialog,
            text="Vuoi davvero procedere?",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(0, 20))
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        ctk.CTkButton(
            btn_frame,
            text="SÌ, PESCA",
            width=120,
            fg_color=COLORE_ERRORE,
            command=lambda: _confirm(True)
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame,
            text="NO, FERMA",
            width=120,
            fg_color=COLORE_SUCCESSO,
            command=lambda: _confirm(False)
        ).pack(side="left", padx=10)
        
        # Centra
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 250) // 2
        dialog.geometry(f"+{x}+{y}")
        
        self.wait_window(dialog)
        return result["value"]


# =============================================================================
# DIALOGHI PERSONALIZZATI
# =============================================================================

class ConnectionDialog(ctk.CTkToplevel):
    """Dialogo per la connessione al server."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("Connessione al Server")
        self.geometry("500x320")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        
        self._build_ui()
        self._center_on_parent(parent)
    
    def _build_ui(self):
        """Costruisce l'interfaccia."""
        ctk.CTkLabel(
            self,
            text="🌐 Connessione al Server",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(25, 20))
        
        # Frame input
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(pady=10)
        
        ctk.CTkLabel(input_frame, text="Host:", font=ctk.CTkFont(size=14)).grid(row=0, column=0, padx=10, pady=10)
        self.host_entry = ctk.CTkEntry(input_frame, width=250, height=35, font=ctk.CTkFont(size=14))
        self.host_entry.insert(0, SERVER_HOST)
        self.host_entry.grid(row=0, column=1, padx=10, pady=10)
        
        ctk.CTkLabel(input_frame, text="Porta:", font=ctk.CTkFont(size=14)).grid(row=1, column=0, padx=10, pady=10)
        self.port_entry = ctk.CTkEntry(input_frame, width=250, height=35, font=ctk.CTkFont(size=14))
        self.port_entry.insert(0, str(SERVER_PORT))
        self.port_entry.grid(row=1, column=1, padx=10, pady=10)
        
        # Pulsanti
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(
            btn_frame,
            text="Connetti",
            width=160,
            height=55,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORE_SUCCESSO,
            command=self._connect
        ).pack(side="left", padx=15)
        
        ctk.CTkButton(
            btn_frame,
            text="Annulla",
            width=160,
            height=55,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORE_ERRORE,
            command=self._cancel
        ).pack(side="left", padx=15)
        
        self.host_entry.bind("<Return>", lambda e: self._connect())
        self.port_entry.bind("<Return>", lambda e: self._connect())
    
    def _connect(self):
        """Conferma la connessione."""
        try:
            host = self.host_entry.get().strip() or SERVER_HOST
            port = int(self.port_entry.get().strip() or SERVER_PORT)
            self.result = (host, port)
        except ValueError:
            self.result = (SERVER_HOST, SERVER_PORT)
        self.destroy()
    
    def _cancel(self):
        """Annulla e usa valori default."""
        self.result = None
        self.destroy()
    
    def _center_on_parent(self, parent):
        """Centra la finestra sul parent."""
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


class BalanceDialog(ctk.CTkToplevel):
    """Dialogo per la selezione del saldo iniziale."""
    
    def __init__(self, parent, min_val: int, max_val: int, default: int):
        super().__init__(parent)
        
        self.title("Saldo Iniziale")
        self.geometry("600x520")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.min_val = min_val
        self.max_val = max_val
        self.result = default
        
        self._build_ui(default)
        self._center_on_parent(parent)
    
    def _build_ui(self, default: int):
        """Costruisce l'interfaccia."""
        ctk.CTkLabel(
            self,
            text="💰 Scegli il tuo Saldo Iniziale",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORE_ORO
        ).pack(pady=(30, 15))
        
        ctk.CTkLabel(
            self,
            text="Seleziona quanto vuoi portare al tavolo",
            font=ctk.CTkFont(size=14),
            text_color=COLORE_TESTO_SCURO
        ).pack()
        
        # Display valore
        self.value_label = ctk.CTkLabel(
            self,
            text=f"€{default}",
            font=ctk.CTkFont(size=48, weight="bold"),
            text_color=COLORE_SUCCESSO
        )
        self.value_label.pack(pady=25)
        
        # Slider
        self.slider = ctk.CTkSlider(
            self,
            from_=self.min_val,
            to=self.max_val,
            width=450,
            number_of_steps=(self.max_val - self.min_val) // 50 if (self.max_val - self.min_val) > 50 else 1,
            command=self._on_slider_change
        )
        self.slider.set(default)
        self.slider.pack(pady=15)
        
        # Label min/max
        range_frame = ctk.CTkFrame(self, fg_color="transparent")
        range_frame.pack(fill="x", padx=75)
        
        ctk.CTkLabel(
            range_frame,
            text=f"Min: €{self.min_val}",
            font=ctk.CTkFont(size=12),
            text_color=COLORE_TESTO_SCURO
        ).pack(side="left")
        
        ctk.CTkLabel(
            range_frame,
            text=f"Max: €{self.max_val}",
            font=ctk.CTkFont(size=12),
            text_color=COLORE_TESTO_SCURO
        ).pack(side="right")
        
        # Pulsanti rapidi
        ctk.CTkLabel(self, text="Opzioni rapide:", font=ctk.CTkFont(size=12)).pack(pady=(20, 5))
        quick_frame = ctk.CTkFrame(self, fg_color="transparent")
        quick_frame.pack(pady=5)
        
        quick_values = [100, 500, 1000, 5000, 10000, 50000, 100000]
        for i, value in enumerate(quick_values):
            if self.min_val <= value <= self.max_val:
                ctk.CTkButton(
                    quick_frame,
                    text=f"€{value}",
                    width=80,
                    height=35,
                    font=ctk.CTkFont(size=12),
                    command=lambda v=value: self._set_value(v)
                ).grid(row=i//4, column=i%4, padx=5, pady=5)
        
        # Pulsante conferma
        ctk.CTkButton(
            self,
            text="✅ OK - CONFERMA",
            width=220,
            height=65,
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color=COLORE_SUCCESSO,
            command=self._confirm
        ).pack(pady=30)
    
    def _on_slider_change(self, value):
        """Gestisce il cambio dello slider."""
        # Arrotonda a multipli di 50
        rounded = int(round(value / 50) * 50)
        self.result = rounded
        self.value_label.configure(text=f"€{rounded}")
    
    def _set_value(self, value: int):
        """Imposta un valore specifico."""
        self.slider.set(value)
        self.result = value
        self.value_label.configure(text=f"€{value}")
    
    def _confirm(self):
        """Conferma la selezione."""
        self.destroy()
    
    def _center_on_parent(self, parent):
        """Centra la finestra."""
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


class InsuranceDialog(ctk.CTkToplevel):
    """Dialogo per l'assicurazione."""
    
    def __init__(self, parent, costo: int):
        super().__init__(parent)
        
        self.title("Assicurazione")
        self.geometry("500x380")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.result = False
        
        self._build_ui(costo)
        self._center_on_parent(parent)
    
    def _build_ui(self, costo: int):
        """Costruisce l'interfaccia."""
        ctk.CTkLabel(
            self,
            text="🛡️ ASSICURAZIONE",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORE_ORO
        ).pack(pady=(35, 15))
        
        ctk.CTkLabel(
            self,
            text="Il banco mostra un Asso!",
            font=ctk.CTkFont(size=16)
        ).pack()
        
        ctk.CTkLabel(
            self,
            text=f"Vuoi assicurarti per €{costo}?",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=20)
        
        ctk.CTkLabel(
            self,
            text="L'assicurazione paga 2:1 se il banco ha Blackjack",
            font=ctk.CTkFont(size=13),
            text_color=COLORE_TESTO_SCURO
        ).pack()
        
        # Pulsanti
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=30)
        
        ctk.CTkButton(
            btn_frame,
            text=f"✅ SÌ (€{costo})",
            width=180,
            height=60,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORE_SUCCESSO,
            command=self._accept
        ).pack(side="left", padx=15)
        
        ctk.CTkButton(
            btn_frame,
            text="❌ NO",
            width=180,
            height=60,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORE_ERRORE,
            command=self._decline
        ).pack(side="left", padx=15)
    
    def _accept(self):
        """Accetta l'assicurazione."""
        self.result = True
        self.destroy()
    
    def _decline(self):
        """Rifiuta l'assicurazione."""
        self.result = False
        self.destroy()
    
    def _center_on_parent(self, parent):
        """Centra la finestra."""
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    app = BlackjackGUI()
    app.mainloop()