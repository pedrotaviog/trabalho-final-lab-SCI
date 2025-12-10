import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# CONFIGURAÇÕES VISUAIS 
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'serif'   
plt.rcParams['font.size'] = 22          
plt.rcParams['axes.labelsize'] = 26    
plt.rcParams['axes.titlesize'] = 28    
plt.rcParams['xtick.labelsize'] = 22   
plt.rcParams['ytick.labelsize'] = 22    
plt.rcParams['legend.fontsize'] = 22    
plt.rcParams['lines.linewidth'] = 3.5   
plt.rcParams['figure.autolayout'] = True 

# Arquivos 
FILE_VALIDACAO      = '1_prova_modelo.csv'
FILE_SD_DEGRAU      = '2_degrau_sd.csv'
FILE_POLY_DEGRAU    = '3_degrau_poly.csv'
FILE_SD_DISTURBIO   = '4_perturbaoes_sd.csv'
FILE_POLY_DISTURBIO = '5_perturbacoes_poly.csv'

# 1. VALIDAÇÃO DO MODELO
def plot_validacao():
    print("Plotando Fig 1: Validação...")
    try:
        df = pd.read_csv(FILE_VALIDACAO)
        t = df['Tempo (s)'].values
        u = df['Duty (%)'].values
        y = df['Tensao (V)'].values

        # Modelo FOPDT
        K = 0.0406
        tau = 0.0104
        Ts = 0.01
        
        # Bias Ajustado
        u_base = np.mean(u[:50])
        y_base = np.mean(y[:50])
        C = y_base - K * u_base

        # Simulação
        alpha = np.exp(-Ts / tau)
        y_sim = np.zeros_like(y)
        y_sim[0] = y[0]

        for k in range(1, len(y)):
            y_target = K * u[k-1] + C
            if y_target < 0: y_target = 0
            y_sim[k] = alpha * y_sim[k-1] + (1 - alpha) * y_target

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 14), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        
        ax1.plot(t, y, 'b', label='Real (Filtrado)', alpha=0.7)
        ax1.plot(t, y_sim, 'r--', label='Modelo Simulado')
        ax1.set_ylabel('Tensão (V)', fontweight='bold')
        ax1.set_title('Validação do Modelo', fontweight='bold')
        ax1.legend(loc='upper left', frameon=True, framealpha=1)
        ax1.grid(True, linestyle='--', linewidth=1)

        ax2.plot(t, u, 'g', label='Degrau (Entrada)')
        ax2.set_ylabel('Duty (%)', fontweight='bold')
        ax2.set_xlabel('Tempo (s)', fontweight='bold')
        ax2.legend(loc='upper left', frameon=True, framealpha=1)
        ax2.grid(True, linestyle='--', linewidth=1)

        plt.show() # Apenas exibe
    except Exception as e:
        print(f"Erro Fig 1: {e}")

# 2. COMPARATIVO DEGRAU (SD vs POLY)
def plot_comparativo():
    print("Plotando Fig 2: Comparativo...")
    try:
        df_sd = pd.read_csv(FILE_SD_DEGRAU)
        df_poly = pd.read_csv(FILE_POLY_DEGRAU)

        def get_data(df):
            sp = df['Setpoint (V)'].values
            # Detecta degrau
            indices = np.where(np.abs(np.diff(sp)) > 0.1)[0]
            if len(indices) == 0: return None
            idx = indices[0]
            
            # Recorta janela (-0.5s a +1.5s)
            start = max(0, idx - 50)
            end = min(len(df), idx + 150)
            
            t = df['Tempo (s)'].values[start:end]
            t = t - t[50] # Zera tempo
            y = df['Tensao (V)'].values[start:end]
            u = df['Duty (%)'].values[start:end]
            sp_seg = df['Setpoint (V)'].values[start:end]
            return t, y, u, sp_seg

        res_sd = get_data(df_sd)
        res_poly = get_data(df_poly)

        if res_sd and res_poly:
            t_sd, y_sd, u_sd, sp_sd = res_sd
            t_poly, y_poly, u_poly, sp_poly = res_poly

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 14), sharex=True)

            ax1.plot(t_sd, y_sd, 'b', label='Síntese Direta')
            ax1.plot(t_poly, y_poly, 'r', label='Polinomial')
            ax1.plot(t_sd, sp_sd, 'g--', label='Setpoint', alpha=0.8)
            ax1.set_ylabel('Tensão (V)', fontweight='bold')
            ax1.set_title('Resposta ao Degrau', fontweight='bold')
            ax1.legend(loc='best', frameon=True, framealpha=1)
            ax1.grid(True, linestyle='--', linewidth=1)

            ax2.plot(t_sd, u_sd, 'b', label='Esforço SD', alpha=0.6)
            ax2.plot(t_poly, u_poly, 'r', label='Esforço Poly', alpha=0.6)
            ax2.axhline(100, color='k', linestyle=':', label='Saturação')
            ax2.set_ylabel('Duty (%)', fontweight='bold')
            ax2.set_xlabel('Tempo (s)', fontweight='bold')
            ax2.legend(loc='lower right', frameon=True, framealpha=1)
            ax2.grid(True, linestyle='--', linewidth=1)

            plt.show()
    except Exception as e:
        print(f"Erro Fig 2: {e}")

# 3. PERTURBAÇÃO (GENÉRICO)
def plot_perturbacao(filename, title_text, color_line):
    print(f"Plotando Fig: {title_text}...")
    try:
        df = pd.read_csv(filename)
        t = df['Tempo (s)'].values
        y = df['Tensao (V)'].values
        u = df['Duty (%)'].values
        sp = df['Setpoint (V)'].values

        # Suavização para visualização limpa
        w = 15
        y_s = pd.Series(y).rolling(w, center=True).mean()
        u_s = pd.Series(u).rolling(w, center=True).mean()

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 14), sharex=True)

        ax1.plot(t, y, 'gray', alpha=0.3)
        ax1.plot(t, y_s, color=color_line, label='Tensão (Filtrada)')
        ax1.plot(t, sp, 'g--', label='Setpoint')
        ax1.set_ylabel('Tensão (V)', fontweight='bold')
        ax1.set_title(f'Rejeição de Carga ({title_text})', fontweight='bold')
        ax1.legend(loc='best', frameon=True, framealpha=1)
        ax1.grid(True, linestyle='--', linewidth=1)

        ax2.plot(t, u, 'gray', alpha=0.3)
        ax2.plot(t, u_s, 'r', label='Controle')
        ax2.axhline(100, color='k', linestyle=':', label='Saturação')
        ax2.set_ylabel('Duty (%)', fontweight='bold')
        ax2.set_xlabel('Tempo (s)', fontweight='bold')
        ax2.legend(loc='best', frameon=True, framealpha=1)
        ax2.grid(True, linestyle='--', linewidth=1)

        plt.show()
    except Exception as e:
        print(f"Erro Fig Perturbação: {e}")

if __name__ == "__main__":
    plot_validacao()
    plot_comparativo()
    plot_perturbacao(FILE_SD_DISTURBIO, 'Síntese Direta', 'b')
    plot_perturbacao(FILE_POLY_DISTURBIO, 'Polinomial', 'r')