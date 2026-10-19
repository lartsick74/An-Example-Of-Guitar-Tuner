#  Algo pseudo code
# // Entrée : x[0..N-1] centré, Fs = 8000
# fmin = 70 Hz, fmax = 400 Hz
# tauMin = Fs / fmax          // ≈ 20
# tauMax = Fs / fmin          // ≈ 114
# W = N - tauMax              // ≈ 386 avec N = 500

# // 1. Fonction de différence
# pour tau de 1 à tauMax :
#     d[tau] = 0
#     pour j de 0 à W-1 :
#         e = x[j] - x[j + tau]
#         d[tau] += e * e

# // 2. Différence normalisée cumulée (évite de choisir tau = 0)
# dn[0] = 1 ; somme = 0
# pour tau de 1 à tauMax :
#     somme += d[tau]
#     dn[tau] = (somme > 0) ? d[tau] * tau / somme : 1

# // 3. Premier creux sous un seuil (et non le minimum global :
# //    c'est ce qui évite les erreurs d'octave)
# SEUIL = 0.15
# tauBest = -1
# pour tau de tauMin à tauMax-1 :
#     si dn[tau] < SEUIL :
#         tant que tau+1 < tauMax et dn[tau+1] < dn[tau] : tau++
#         tauBest = tau ; sortir
# si tauBest == -1 : pas de note fiable → retour

# // 4. Interpolation parabolique (indispensable !)
# a = dn[tauBest-1] ; b = dn[tauBest] ; c = dn[tauBest+1]
# delta = (a - c) / (2 * (a - 2*b + c))
# frequence = Fs / (tauBest + delta)

import glob
import os
import sys
import time

import matplotlib.pyplot as plt
import numpy as np

class NoPitchFound(Exception):
    """Aucun creux sous le seuil : pas de note fiable."""


# 1. fonction des differences
def difference(tauMax, W, x):
    d = np.zeros(tauMax + 1)        # tableau numpy de tauMax+1 zéros
    for tau in range(1, tauMax + 1):
    #     pour j de 0 à W-1 :
        for j in range(W):
            e = x[j] - x[j + tau]
            d[tau] += e * e

    return d

# 2. Différence normalisée cumulée (évite de choisir tau = 0)
def normalised_cumaltive_difference(tauMax, d) :
    dn = np.ones(tauMax + 1)      # dn[0] = 1 déjà fait

    somme = 0
    for tau in range (1,tauMax) :
        somme += d[tau]
        dn[tau] = d[tau] * tau / somme  if (somme > 0) else 1

    return dn

# // 3. Premier creux sous un seuil (et non le minimum global :
# //    c'est ce qui évite les erreurs d'octave)
def first_hole_below_threshold(SEUIL, tauMin,tauMax, dn):
    tauBest = -1
    for tau in range(tauMin ,tauMax-1) :
        if dn[tau] < SEUIL :
            while (tau+1 < tauMax and dn[tau+1] < dn[tau]) : 
                tau = tau +1
                
            tauBest = tau

            return tauBest

        
    
    raise NoPitchFound(f"aucun dn[tau] < {SEUIL} entre {tauMin} et {tauMax}")

    
# // 4. Interpolation parabolique (indispensable !)
def parabolic_interpolation(Fs, tauBest,dn):
    a = dn[tauBest-1]
    b = dn[tauBest]
    c = dn[tauBest+1]
    delta = (a - c) / (2 * (a - 2*b + c))
    frequence = Fs / (tauBest + delta)

    return frequence


def main():
    #Freq d'echantillonnage en Hz
    FS = 8000
    FMIN = 70
    FMAX = 400

    tauMin = int(FS / FMAX)         #  ≈ 20
    tauMax = int(FS / FMIN)         #  ≈ 114

    #On charge le csv de capture de la note de LA 440Hz
    x = np.loadtxt("tools/captures/capture_001_guitare.csv")
    x = x - x.mean()

    #On retire la moyenne
    N = len(x)
    W = N - tauMax              # ≈ 386 avec N = 500

    d = difference(tauMax, W, x)
    dn = normalised_cumaltive_difference(tauMax,d)
    SEUIL = 0.15
    try:
        tauBest = first_hole_below_threshold(SEUIL, tauMin, tauMax, dn)
    except NoPitchFound as e:
        print("Pas de note :", e)
        sys.exit(1)   # ou `continue` si tu traites plusieurs captures dans une boucle

    frequence = parabolic_interpolation(FS, tauBest,dn)

    print("Frequence trouvée :", frequence, " Hz")

if __name__ == "__main__":
    main()





