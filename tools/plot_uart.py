#!/usr/bin/env python3
"""
Visualisation en direct des échantillons envoyés par le STM32 (accordeur).

Le firmware envoie 500 valeurs ADC (une par ligne, "1532\r\n"), puis fait
une pause d'environ 1 s. Le script s'appuie sur cette pause pour découper
les trames : quand plus rien n'arrive pendant TIMEOUT secondes, la trame
est terminée.

Installation :  pip3 install pyserial matplotlib numpy
Lancement   :  python3 plot_uart.py                  (port détecté tout seul)
               python3 plot_uart.py /dev/cu.usbmodem14303

Pendant l'affichage :
    s  -> sauvegarde la trame affichée dans captures/capture_XXX.csv
    q  -> quitte

Attention : ferme `screen` avant de lancer le script (le port ne peut être
ouvert que par un seul programme à la fois).
"""

import glob
import os
import sys
import time

import matplotlib.pyplot as plt
import numpy as np
import serial

# ---------------------------------------------------------------- réglages
BAUDRATE = 115200
FS = 8000            # Hz : 16 MHz / (PSC+1) / (ARR+1) = 16e6 / 2 / 1000
N_ATTENDU = 500      # NUM_SAMPLES dans main.c
TIMEOUT = 0.4        # s sans données = fin de trame (la pause fait 1 s)
ADC_MAX = 4095       # ADC 12 bits
VREF = 3.3           # V
MARGE_SAT = 20       # en dessous de 20 ou au-dessus de 4075 -> saturation
DOSSIER_CAPTURES = "captures"


def trouver_port():
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    if not ports:
        sys.exit("Aucun /dev/cu.usbmodem* trouvé. Carte branchée ? "
                 "Sinon passe le port en argument.")
    if len(ports) > 1:
        print("Plusieurs ports trouvés, j'utilise", ports[0], ":", ports)
    return ports[0]


class LecteurTrames:
    """Lit le port sans bloquer. poll() renvoie une trame (liste d'int) quand
    plus rien n'est arrivé depuis TIMEOUT s, sinon None. Comme poll() ne
    bloque jamais, la fenêtre reste réactive (touches s / q)."""

    def __init__(self, ser):
        self.ser = ser
        self.tampon = b""
        self.valeurs = []
        self.dernier_octet = time.time()

    def poll(self):
        n = self.ser.in_waiting
        if n:
            self.tampon += self.ser.read(n)
            self.dernier_octet = time.time()
            *lignes, self.tampon = self.tampon.split(b"\n")
            for ligne in lignes:
                try:
                    self.valeurs.append(int(ligne.strip()))
                except ValueError:
                    pass                 # ligne corrompue / texte : ignorée
            return None
        if self.valeurs and time.time() - self.dernier_octet > TIMEOUT:
            trame, self.valeurs, self.tampon = self.valeurs, [], b""
            return trame                 # silence -> trame terminée
        return None


def sauvegarder(donnees):
    os.makedirs(DOSSIER_CAPTURES, exist_ok=True)
    i = 0
    while os.path.exists(os.path.join(DOSSIER_CAPTURES, f"capture_{i:03d}.csv")):
        i += 1
    chemin = os.path.join(DOSSIER_CAPTURES, f"capture_{i:03d}.csv")
    np.savetxt(chemin, donnees, fmt="%d", header=f"fs={FS}", comments="# ")
    print("Sauvegardé :", chemin)


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else trouver_port()
    ser = serial.Serial(port, BAUDRATE, timeout=TIMEOUT)
    ser.reset_input_buffer()
    print(f"Ouvert {port} à {BAUDRATE} bauds. Joue une corde !")

    etat = {"derniere": None, "quitter": False}

    def touche(evt):
        if evt.key == "s" and etat["derniere"] is not None:
            sauvegarder(etat["derniere"])
        elif evt.key == "q":
            etat["quitter"] = True

    # Par défaut, matplotlib associe "s" à "Enregistrer la figure" : on la
    # libère pour notre sauvegarde CSV (ctrl+s / cmd+s restent disponibles).
    for raccourci in ("s",):
        if raccourci in plt.rcParams["keymap.save"]:
            plt.rcParams["keymap.save"].remove(raccourci)

    plt.ion()
    fig, ax = plt.subplots(figsize=(11, 5))
    fig.canvas.mpl_connect("key_press_event", touche)
    fig.canvas.mpl_connect("close_event", lambda e: etat.update(quitter=True))
    ligne, = ax.plot([], [], lw=1, color="#2a6fdb")
    ligne_moy = ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.axhline(0, color="red", lw=0.6, alpha=0.5)
    ax.axhline(ADC_MAX, color="red", lw=0.6, alpha=0.5)
    ax.set_xlabel("temps (ms)")
    ax.set_ylabel("valeur ADC (0–4095)")
    ax.set_ylim(-100, ADC_MAX + 100)
    ax.grid(alpha=0.3)
    secax = ax.secondary_yaxis("right",
                               functions=(lambda v: v * VREF / ADC_MAX,
                                          lambda u: u * ADC_MAX / VREF))
    secax.set_ylabel("tension (V)")

    lecteur = LecteurTrames(ser)
    try:
        while not etat["quitter"]:
            plt.pause(0.05)              # traite les touches / le redessin
            donnees = lecteur.poll()
            if donnees is None:
                continue

            n = len(donnees)
            if n != N_ATTENDU:
                print(f"Trame incomplète ({n} valeurs), ignorée")
                plt.pause(0.01)
                continue

            x = np.array(donnees)
            etat["derniere"] = x
            t_ms = np.arange(n) / FS * 1000
            moy = x.mean()
            crete = x.max() - x.min()
            satures = np.sum((x < MARGE_SAT) | (x > ADC_MAX - MARGE_SAT))

            ligne.set_data(t_ms, x)
            ligne_moy.set_ydata([moy, moy])
            ax.set_xlim(0, t_ms[-1])
            titre = (f"min {x.min()}   max {x.max()}   moyenne {moy:.0f}   "
                     f"crête-à-crête {crete} ({crete * VREF / ADC_MAX:.2f} V)")
            if satures:
                titre += f"   ⚠ {satures} échantillons saturés"
            ax.set_title(titre, color="red" if satures else "black")
            print(titre)
            plt.pause(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()


if __name__ == "__main__":
    main()
