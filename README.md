# 🃏 Blackjack

Progetto scolastico di Blackjack sviluppato in Python con architettura client-server. Il sistema permette a più giocatori di partecipare a una partita tramite rete locale (LAN), con gestione centralizzata della logica di gioco.

---

## 📜 Descrizione

Questo progetto implementa il classico gioco di carte Blackjack (21) utilizzando una struttura client-server:

* Il **server** gestisce:

  * il mazzo di carte
  * la logica di gioco
  * i turni dei giocatori
* I **client** permettono ai giocatori di interagire con il gioco tramite interfaccia a riga di comando

---

## ✨ Caratteristiche principali

* 🎮 Modalità multiplayer via LAN
* 💻 Interfaccia CLI (terminale)
* 🧠 Logica completa del Blackjack:

  * Blackjack (Asso + 10/figura)
  * Vittoria automatica del banco con Blackjack
  * Split (solo su coppie identiche)
  * Side bet (puntate opzionali)
  * Pareggio ("push")
* 🔄 Gestione turni tra più giocatori
* 🌐 Comunicazione tramite socket TCP

---

## 🧩 Architettura

Il progetto utilizza socket TCP per la comunicazione client-server.

### Server

* Gestione del mazzo
* Applicazione delle regole
* Coordinamento dei turni
* Gestione connessioni multiple

### Client

* Interfaccia utente testuale
* Invio comandi (hit, stand, split)
* Ricezione aggiornamenti dal server

---

## 🌐 Dettagli di rete

* **Protocollo:** TCP
* **Modalità:** LAN
* **Binding server:** `0.0.0.0` (accessibile da tutta la rete locale)
* **IP di esempio:** `192.168.1.10`
* **Loopback:** `127.0.0.1` (stessa macchina)

---

## 🚀 Installazione

1. **Clona la repository:**

   ```bash
   git clone https://github.com/davT46/BlackjackGit.git
   cd BlackjackGit
   ```

2. **Installa le dipendenze:**

   ```bash
   pip install -r requirements.txt
   ```

---

## 🕹️ Come giocare

Il gioco è composto da due componenti:

### 1️⃣ Avviare il server (Banco)

Esegui il server sulla macchina principale:

```bash
python server.py
```

---

### 2️⃣ Avviare il client (Giocatore)

Esegui il client:

```bash
python client.py
```

Inserisci l’indirizzo IP del server quando richiesto.

---

## 💡 Esempio di partita

```
Giocatore: 10 + 7 → 17
Banco:     9 + 8 → 17

Risultato: Push
```

---

## 📂 Struttura del progetto

* `server.py` → Gestione logica di gioco e connessioni
* `client.py` → Interfaccia utente e comunicazione
* `logic.py` → Classi e funzioni del gioco (carte, punteggi, mazzo)
* `requirements.txt` → Dipendenze Python

---

## 🎮 Regole del gioco

* Obiettivo: raggiungere 21 o avvicinarsi senza superarlo
* Il banco pesca fino ad almeno 17
* Blackjack batte qualsiasi altro 21
* Split possibile solo con carte identiche
* Side bet opzionali
* In caso di pareggio → puntata restituita (push)

---

## ⚠️ Problemi comuni

* ❌ Connessione fallita → controlla IP server
* 🔥 Porta bloccata → verifica firewall
* 📴 Server non avviato → avvia `server.py` prima del client

---

## 🧠 Note tecniche

Questo progetto dimostra l'utilizzo di:

* Programmazione client-server
* Socket networking in Python
* Gestione dello stato di gioco
* Sincronizzazione tra più utenti

---

## 📌 Possibili miglioramenti

* Interfaccia grafica (Tkinter / PyQt)
* Supporto online (non solo LAN)
* Sistema di autenticazione utenti
* Logging delle partite
* Miglior gestione degli errori

---

## 📄 Licenza
Uso educativo.
