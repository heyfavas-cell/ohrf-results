# Held-out result (decided once, on the frozen run names)

- circuits with every arm: 145 of 145 planned
- compute (hours): {'held_out': 19.575, 'total': 19.575}
- outcome: null
- Q (cand@300 vs GUOQ@300): {'ratio': 1.032364, 'ci95': (1.021317, 1.042799), 'gain': -0.032364, 'gain_lower': -0.042799, 'n': 145}
- T (cand@15 vs GUOQ@300): {'ratio': 1.050212, 'ci95': (1.04025, 1.059597), 'gain': -0.050212, 'gain_lower': -0.059597, 'n': 145}
- S (cand vs S*): long {'ratio': 0.948082, 'ci95': (0.932678, 0.962612), 'gain': 0.051918, 'gain_lower': 0.037388, 'n': 145}; short {'ratio': 0.964473, 'ci95': (0.950914, 0.977162), 'gain': 0.035527, 'gain_lower': 0.022838, 'n': 145}
- S* alone vs GUOQ@300: {'ratio': 1.088897, 'ci95': (1.078958, 1.099336), 'gain': -0.088897, 'gain_lower': -0.099336, 'n': 145}; at 15 s: {'ratio': 1.088897, 'ci95': (1.078958, 1.099336), 'gain': -0.088897, 'gain_lower': -0.099336, 'n': 145}
- pass_q False, pass_t False
- s on this sample 0.0639; smallest gain it finds 0.014751
- verified shares: {'guoq@15': 0.9931, 'guoq@300': 0.9931, 'cand@15': 0.9931, 'cand@300': 0.9448, 'star@15': 1.0, 'star@300': 1.0}; below the 80% floor: False
- guoq@15 verified by size: {6: '15/15', 8: '16/16', 10: '17/17', 12: '17/17', 14: '17/17', 16: '15/15', 18: '16/16', 20: '16/16', 22: '15/16'}
- guoq@300 verified by size: {6: '15/15', 8: '16/16', 10: '17/17', 12: '17/17', 14: '17/17', 16: '15/15', 18: '16/16', 20: '15/16', 22: '16/16'}
- cand@15 verified by size: {6: '15/15', 8: '16/16', 10: '17/17', 12: '17/17', 14: '16/17', 16: '15/15', 18: '16/16', 20: '16/16', 22: '16/16'}
- cand@300 verified by size: {6: '15/15', 8: '16/16', 10: '16/17', 12: '15/17', 14: '16/17', 16: '14/15', 18: '14/16', 20: '16/16', 22: '15/16'}
- star verified by size: {6: '15/15', 8: '16/16', 10: '17/17', 12: '17/17', 14: '17/17', 16: '15/15', 18: '16/16', 20: '16/16', 22: '16/16'}
- verified-only sensitivity row (136 circuits with every arm verified): outcome null; Q {'ratio': 1.029838, 'ci95': (1.018683, 1.040536), 'gain': -0.029838, 'gain_lower': -0.040536, 'n': 136}; T {'ratio': 1.04888, 'ci95': (1.038789, 1.058706), 'gain': -0.04888, 'gain_lower': -0.058706, 'n': 136}
- leads: 0
