# ESP32 Motor Lab - Controle Digital

Projeto baseado no microcontrolador **ESP32**, desenvolvido para **acionamento, monitoramento e controle de velocidade de motor DC**.  
O sistema utiliza **PWM** para atuação e **ADC** para leitura do tacogerador, permitindo a operação tanto em malha aberta quanto em **malha fechada** através de uma **interface web** interativa.

---

## 🚀 Funcionalidades

- **Controle Digital de Velocidade**:
  - **Malha Aberta**: Ajuste direto de Duty Cycle.
  - **Malha Fechada**: Seleção de **Setpoint** (Tensão Desejada).
- **Estratégias de Controle Embarcadas**:
  - 🟢 **PI (Síntese Direta)**: Com filtro de referência.
  - 🔵 **Polinomial (RST)**: Alocação de polos via Equação Diofantina.
- **Tratamento de Sinal e Atuador**:
  - Filtro digital para leitura do sensor.
  - Rotina de **Anti-windup** (Clamping) para saturação do PWM.
- **Interface Web**:
  - Visualização gráfica em tempo real.
  - Seleção dinâmica entre controladores.
- **Análise de Dados**:
  - Exportação de dados via CSV.
  - Scripts em Python para geração de gráficos.

---

## 📂 Estrutura do Repositório

Além do firmware do ESP32, este repositório contém os dados experimentais e ferramentas de análise utilizados no relatório técnico:

- **`/data`**: Arquivos `.csv` contendo os dados brutos coletados da planta (Malha Aberta, Resposta do PI e Resposta do Polinomial).
- **`/analysis`**: Scripts em **Python** (`.py`) utilizados para processar os CSVs, calcular métricas (tempo de subida, overshoot) e gerar os plots comparativos.
- **`/src`**: Código fonte do firmware (ESP-IDF).

---

## ⚙️ Requisitos

- **ESP-IDF v5.x** configurado  
- **ESP32 DevKit V1** - **Python 3.x** (para rodar os scripts de análise, bibliotecas: `pandas`, `matplotlib`, `scipy`)
- **Circuitos externos adequados**:
  - **Circuito de acionamento** (ex.: optoacoplador para isolamento lógico);
  - **Circuito de potência** (ex.: MOSFETs/Ponte H para chaveamento da carga);
  - **Circuito de adequação de entrada** (ex.: divisor resistivo para leitura de tensão no ADC);
- **Fonte de alimentação estável** (de acordo com as especificações do motor e do circuito de potência);
- Navegador para acesso à interface web.

> ⚠️ **Aviso Importante:** > Este código foi desenvolvido com fins **didáticos e de demonstração**.  
> O sistema depende de circuitos externos de **acionamento, potência e adequação de sinal**, que podem variar conforme o projeto e os componentes utilizados.  
> 
> A ligação direta de motores, fontes ou sensores ao ESP32 **pode causar danos permanentes** se não houver o devido isolamento e dimensionamento elétrico.  
> 
> O autor **não se responsabiliza por danos ou mau funcionamento** decorrentes de implementações incorretas, modificações no código ou uso inadequado do hardware.  
> Use o projeto **como base de estudo** e **adapte os circuitos de forma segura** às suas necessidades específicas.

---

## 🔧 Como usar

### 1. Firmware (ESP32)

1. Clone o repositório:
   ```bash
    git clone [https://github.com/pedrotaviog/trabalho-final-lab-SCI.git]
    cd trabalho-final-lab-SCI/esp32_motor_lab
   ```

2. Compile e grave no ESP32:
    ```bash
    idf.py fullclean
    idf.py set-target esp32
    idf.py build
    idf.py -p [SUA PORTA COM] flash
    idf.py flash monitor
    ```

💡 Substitua [SUA PORTA COM] pela porta serial do seu dispositivo (ex.: COM3 no Windows ou /dev/ttyUSB0 no Linux/macOS).

3. Conecte-se à rede Wi-Fi gerada pelo ESP32:

- SSID: ESP32_AP

- Senha: 12345678

4. Acesse a interface no navegador (http://192.168.4.1/).

- No painel, selecione o Modo de Controle (Malha Aberta, PI ou Polinomial).

- Defina o Setpoint (Tensão Alvo) ou Duty Cycle.

-Visualize a resposta em tempo real.