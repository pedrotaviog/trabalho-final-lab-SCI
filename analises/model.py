import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'serif'   
plt.rcParams['font.size'] = 22         
plt.rcParams['axes.labelsize'] = 26     
plt.rcParams['axes.titlesize'] = 28     
plt.rcParams['xtick.labelsize'] = 22   
plt.rcParams['ytick.labelsize'] = 22    
plt.rcParams['legend.fontsize'] = 13.5    
plt.rcParams['lines.linewidth'] = 3.5   
plt.rcParams['figure.autolayout'] = True 
plt.rcParams['font.weight'] = 'bold'        
plt.rcParams['axes.labelweight'] = 'bold'   
plt.rcParams['axes.titleweight'] = 'bold'

# 1. CARREGAMENTO E PREPARAÇÃO DOS DADOS
filename = 'dados_planta.csv'
df = pd.read_csv(filename)

# Extrair vetores
t = df['Tempo (s)'].values
u = df['Duty (%)'].values
y = df['Tensao (V)'].values
Ts = 0.01  # Tempo de amostragem (10ms)

#
# 2. IDENTIFICAÇÃO MODELO 1: FOPDT 

indices_mudanca = np.where(np.diff(u, prepend=u[0]) != 0)[0]
# Adiciona o início (0) e o fim para criar os intervalos
indices_limites = np.concatenate(([0], indices_mudanca, [len(u)]))

medias_u = []
medias_y = []

# Calcular médias por patamar (ignorando transitórios iniciais de cada degrau)
print("--- Analise de Patamares FOPDT ---")
for i in range(len(indices_limites) - 1):
    inicio = indices_limites[i]
    fim = indices_limites[i+1]
    
    # Pegamos apenas a segunda metade do intervalo para garantir regime estacionário
    meio = inicio + (fim - inicio) // 2
    
    u_medio = np.mean(u[meio:fim])
    y_medio = np.mean(y[meio:fim])
    
    medias_u.append(u_medio)
    medias_y.append(y_medio)
    print(f"Patamar {i+1}: Duty={u_medio:.1f}%, Tensao={y_medio:.3f}V")

# Calcular Ganhos Incrementais (Delta Y / Delta U)
ganhos_k = []
for i in range(len(medias_u) - 1):
    delta_y = medias_y[i+1] - medias_y[i]
    delta_u = medias_u[i+1] - medias_u[i]
    if abs(delta_u) > 0:
        ganhos_k.append(delta_y / delta_u)

K_medio = np.mean(ganhos_k)
# Calcular Offset (y = K*u + C  ->  C = y - K*u)
C_offsets = [my - K_medio * mu for my, mu in zip(medias_y, medias_u)]
C_medio = np.mean(C_offsets)

print(f"\nPARAMETROS FOPDT INICIAIS:")
print(f"Ganho Estatico (K): {K_medio:.5f}")
print(f"Bias/Offset (C): {C_medio:.5f}")

# Otimizar Tau (Constante de Tempo) simulando a resposta
# Função que simula o sistema de 1ª ordem dado um Tau
def simular_fopdt_otimizacao(t_array, tau):
    # Modelo discretizado: y[k] = alpha*y[k-1] + (1-alpha)*(K*u[k-1] + C)
    y_sim = np.zeros_like(y)
    y_sim[0] = y[0]
    
    alpha = np.exp(-Ts / tau)
    # Termo forçante combinado (Input + Bias)
    # Se y_infinito = K*u + C, então a eq de diferenças é:
    # y[k] = alpha*y[k-1] + (1-alpha)*y_infinito
    
    for k in range(1, len(y)):
        y_target = K_medio * u[k-1] + C_medio
        y_sim[k] = alpha * y_sim[k-1] + (1 - alpha) * y_target
        
    return y_sim

# Rodar otimização (encontrar Tau que minimiza o erro entre simulação e dados reais)
# Chute inicial para Tau = 0.1s
popt, _ = curve_fit(simular_fopdt_otimizacao, t, y, p0=[0.1], bounds=(0.001, 2.0))
tau_final = popt[0]

print(f"Constante de Tempo Otimizada (Tau): {tau_final:.5f} s")
print(f"Atraso (Theta): ~0 s (Considerado desprezivel/absorvido)")


# 3. IDENTIFICAÇÃO MODELO 2: ARX (Numérico)
N = len(y)
Y_vec = y[1:N]  # Vetor saída de k=1 até fim

# Matriz de Regressores [y[k-1], u[k-1], 1]
# O "1" serve para calcular o viés (bias) d
Phi_mat = np.column_stack((y[0:N-1], u[0:N-1], np.ones(N-1)))

# Mínimos Quadrados: Theta = (Phi^T * Phi)^-1 * Phi^T * Y
theta_arx, residuals, rank, s = np.linalg.lstsq(Phi_mat, Y_vec, rcond=None)

a1_arx_neg = theta_arx[0] 
a_pred = theta_arx[0]
b_pred = theta_arx[1]
d_pred = theta_arx[2]

print(f"\nPARAMETROS ARX (Discreto):")
print(f"y[k] = {a_pred:.5f}*y[k-1] + {b_pred:.5f}*u[k-1] + {d_pred:.5f}")

# Conversão para Função de Transferência Discreta H(z)
# H(z) = b_pred / (z - a_pred)
print(f"FT Discreta Aprox: H(z) = {b_pred:.5f} / (z - {a_pred:.5f})")



# 4. VALIDAÇÃO E GRÁFICOS
# Simulação Final dos Dois Modelos
y_fopdt = simular_fopdt_otimizacao(t, tau_final) # Já temos essa função pronta
y_arx = np.zeros_like(y)
y_arx[0] = y[0]

for k in range(1, N):
    y_arx[k] = a_pred * y_arx[k-1] + b_pred * u[k-1] + d_pred

# Cálculo de Métricas (FIT %)
def calc_fit(y_real, y_model):
    num = np.linalg.norm(y_real - y_model)
    den = np.linalg.norm(y_real - np.mean(y_real))
    return 100 * (1 - num/den)

fit_fopdt = calc_fit(y, y_fopdt)
fit_arx = calc_fit(y, y_arx)

# Plotagem
plt.figure(figsize=(12, 12))

# Subplot 1: Dados e Modelos
plt.subplot(2, 1, 1)
plt.plot(t, y, 'k', label='Dados Reais (Ruidoso)', alpha=0.3, linewidth=2)
plt.plot(t, y_fopdt, 'r', label=f'FOPDT (Fit: {fit_fopdt:.1f}%)', linewidth=3.5)
plt.plot(t, y_arx, 'b--', label=f'ARX (Fit: {fit_arx:.1f}%)', linewidth=3.5)
plt.title('Identificacao e Validacao dos Modelos')
plt.ylabel('Tensao (V)')
plt.legend()
plt.grid(True)

# Subplot 2: Entrada (Duty)
plt.subplot(2, 1, 2)
plt.plot(t, u, 'g', label='Entrada (Duty %)')
plt.ylabel('Duty Cycle (%)')
plt.xlabel('Tempo (s)')
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.show()

# Resumo Final no Console
print("\n=== RESUMO ===")
print("MODELO 1 (FOPDT - Continuo):")
print(f"  G(s) = {K_medio:.4f} / ({tau_final:.4f}s + 1)")
print(f"  Obs: Existe um Offset de {C_medio:.2f}V (Zona Morta/Bias)")
print("\nMODELO 2 (ARX - Discreto):")
print(f"  y[k] = {a_pred:.4f}y[k-1] + {b_pred:.4f}u[k-1] + {d_pred:.4f}")