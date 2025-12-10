#include <stdio.h>
#include <string.h>
#include "driver/ledc.h"
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "esp_http_server.h"
#include "esp_adc/adc_oneshot.h"

// ===== Configurações de Hardware =====
#define PWM_GPIO        2
#define PWM_FREQ_HZ     1000
#define PWM_RES_BITS    10
#define PWM_TIMER       LEDC_TIMER_0
#define PWM_MODE        LEDC_LOW_SPEED_MODE
#define PWM_CHANNEL     LEDC_CHANNEL_0

// ===== Buffer e Amostragem =====
#define BUF_N       2000    
#define BATCH_SIZE  10      
#define TS          0.01f   

// Amostragem robusta (32 leituras)
#define ADC_SAMPLES 32   

typedef struct {
    float v;    
    float d;    
    float sp;   
} sample_t;

static sample_t rb[BUF_N];
static volatile uint32_t rb_head = 0;
static SemaphoreHandle_t rb_mutex = NULL;

static uint32_t duty_raw = 0;
static const char *TAG = "APP";

// ===== Variáveis de Controle =====
// NOVOS MODOS DEFINIDOS
enum { 
    MODE_MANUAL = 0, 
    MODE_DS_FILTER = 1,  // Sintese Direta c/ Filtro
    MODE_POLYNOMIAL = 2  // Controlador Polinomial
};

static int ctrl_mode = MODE_MANUAL;
static float setpoint = 1.0f;

// Histórico para equações de diferenças (Segunda Ordem)
static float uk_1 = 0, uk_2 = 0;
static float ek_1 = 0, ek_2 = 0;

// Variável estática para o filtro EMA na task de controle
static float voltage_filtered = 0.0f;
// Alpha 0.6: Filtro leve para não invalidar o modelo
const float alpha_ema = 0.6f; 

// DECLARAÇÃO DOS ARQUIVOS EXTERNOS
extern const uint8_t index_html_start[] asm("_binary_index_html_start");
extern const uint8_t index_html_end[]   asm("_binary_index_html_end");

// ==== ADC & PWM ====
static adc_oneshot_unit_handle_t adc1_handle;

void adc_init(void) {
    adc_oneshot_unit_init_cfg_t init_config = { .unit_id = ADC_UNIT_1 };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&init_config, &adc1_handle));
    adc_oneshot_chan_cfg_t config = { .atten = ADC_ATTEN_DB_11, .bitwidth = ADC_BITWIDTH_DEFAULT };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc1_handle, ADC_CHANNEL_3, &config));
}

void pwm_init(void) {
    ledc_timer_config_t tcfg = {
        .speed_mode = PWM_MODE, .duty_resolution = PWM_RES_BITS,
        .timer_num = PWM_TIMER, .freq_hz = PWM_FREQ_HZ, .clk_cfg = LEDC_AUTO_CLK
    };
    ESP_ERROR_CHECK(ledc_timer_config(&tcfg));
    ledc_channel_config_t ccfg = {
        .gpio_num = PWM_GPIO, .speed_mode = PWM_MODE, .channel = PWM_CHANNEL,
        .timer_sel = PWM_TIMER, .duty = 0, .hpoint = 0, .intr_type = LEDC_INTR_DISABLE
    };
    ESP_ERROR_CHECK(ledc_channel_config(&ccfg));
}

static inline void pwm_set_duty_percent(float duty_percent) {
    if (duty_percent < 0) duty_percent = 0;
    if (duty_percent > 100) duty_percent = 100;
    uint32_t max_duty = (1U << PWM_RES_BITS) - 1U;
    duty_raw = (uint32_t)((duty_percent * max_duty / 100.0f) + 0.5f);
    ESP_ERROR_CHECK(ledc_set_duty(PWM_MODE, PWM_CHANNEL, duty_raw));
    ESP_ERROR_CHECK(ledc_update_duty(PWM_MODE, PWM_CHANNEL));
}

static inline float pwm_get_duty_percent(void) {
    uint32_t max_duty = (1U << PWM_RES_BITS) - 1U;
    return 100.0f * ((float)duty_raw / (float)max_duty);
}

// ===== ALGORITMO DE CONTROLE =====
float run_controller(float pv_voltage) {
    float u = 0;
    float error = setpoint - pv_voltage;

    if (ctrl_mode == MODE_DS_FILTER) {
        // CONTROLADOR 1: Síntese Direta com Filtro (Discretizado via Tustin)
        // u[k] = 1.1772*u[k-1] - 0.1772*u[k-2] + 16.6524*e[k] + 4.3702*e[k-1] - 12.2822*e[k-2]
        
        u = 1.177163f * uk_1 - 0.177163f * uk_2 
            + 16.652443f * error + 4.370218f * ek_1 - 12.282225f * ek_2;
    } 
    else if (ctrl_mode == MODE_POLYNOMIAL) {
        // CONTROLADOR 2: Polinomial (Discretizado via Tustin)
        // u[k] = 0.7702*u[k-1] + 0.2298*u[k-2] + 50.2935*e[k] + 19.8654*e[k-1] - 30.4281*e[k-2]
        
        u = 0.770197f * uk_1 + 0.229803f * uk_2 
            + 50.293493f * error + 19.865382f * ek_1 - 30.428111f * ek_2;
    }

    // SATURAÇÃO + ANTI-WINDUP (Clamping)
    // Se saturar, limitamos 'u' ANTES de salvar no histórico 'uk_1'.
    // Isso impede que os valores passados cresçam indefinidamente.
    if (u > 100.0f) u = 100.0f;
    if (u < 0.0f) u = 0.0f;

    // Atualiza histórico (Shift registers)
    uk_2 = uk_1; uk_1 = u;
    ek_2 = ek_1; ek_1 = error;

    return u;
}

// ===== HANDLERS HTTP (Omitindo repeticoes para economizar espaco, igual ao anterior) =====
// ... (Mantenha root_get_handler, data_get_handler igual ao anterior) ...

// Apenas copiei as funcoes para manter o codigo compilavel e completo
esp_err_t root_get_handler(httpd_req_t *req) {
    const size_t index_html_size = (index_html_end - index_html_start);
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, (const char *)index_html_start, index_html_size);
}

esp_err_t data_get_handler(httpd_req_t *req) {
    float v_local[BATCH_SIZE], d_local[BATCH_SIZE], sp_local[BATCH_SIZE];
    if (xSemaphoreTake(rb_mutex, pdMS_TO_TICKS(50)) != pdTRUE) {
        httpd_resp_sendstr(req, "{ \"samples\": [] }");
        return ESP_OK;
    }
    uint32_t start = (rb_head + BUF_N - BATCH_SIZE) % BUF_N;
    for (int i = 0; i < BATCH_SIZE; i++) {
        uint32_t idx = (start + i) % BUF_N;
        v_local[i] = rb[idx].v;
        d_local[i] = rb[idx].d;
        sp_local[i] = rb[idx].sp;
    }
    xSemaphoreGive(rb_mutex);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr_chunk(req, "{ \"samples\": [");
    for (int i = 0; i < BATCH_SIZE; i++) {
        char buf[100];
        snprintf(buf, sizeof(buf), "{\"v\":%.3f,\"d\":%.1f,\"sp\":%.2f}%s",
                 v_local[i], d_local[i], sp_local[i], (i < BATCH_SIZE - 1) ? "," : "");
        httpd_resp_sendstr_chunk(req, buf);
    }
    httpd_resp_sendstr_chunk(req, "] }");
    httpd_resp_sendstr_chunk(req, NULL);
    return ESP_OK;
}

esp_err_t set_get_handler(httpd_req_t *req) {
    char buf[128];
    if (httpd_req_get_url_query_str(req, buf, sizeof(buf)) == ESP_OK) {
        char param[32];
        if (httpd_query_key_value(buf, "mode", param, sizeof(param)) == ESP_OK) {
            int new_mode = atoi(param);
            if (ctrl_mode == MODE_MANUAL && new_mode != MODE_MANUAL) {
                // Bumpless transfer: Inicializa o integrador com o duty atual
                // Zera histórico de erro e define u[k-1] e u[k-2] como o duty atual
                float current_duty = pwm_get_duty_percent();
                uk_1 = uk_2 = current_duty;
                // Importante: Zerar o erro passado assume que estavamos em regime permanente no setpoint
                // Melhor: assumir erro zero para iniciar suave
                ek_1 = ek_2 = 0; 
            }
            ctrl_mode = new_mode;
        }
        if (httpd_query_key_value(buf, "sp", param, sizeof(param)) == ESP_OK) {
            setpoint = atof(param);
        }
        if (ctrl_mode == MODE_MANUAL && httpd_query_key_value(buf, "duty", param, sizeof(param)) == ESP_OK) {
            pwm_set_duty_percent(atof(param));
        }
    }
    char resp[64];
    snprintf(resp, sizeof(resp), "{ \"duty\": %.1f, \"mode\": %d }", pwm_get_duty_percent(), ctrl_mode);
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
}

httpd_handle_t start_webserver(void) {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    httpd_handle_t server = NULL;
    if (httpd_start(&server, &config) == ESP_OK) {
        httpd_uri_t u1 = { .uri = "/", .method = HTTP_GET, .handler = root_get_handler };
        httpd_uri_t u2 = { .uri = "/data", .method = HTTP_GET, .handler = data_get_handler };
        httpd_uri_t u3 = { .uri = "/set", .method = HTTP_GET, .handler = set_get_handler };
        httpd_register_uri_handler(server, &u1);
        httpd_register_uri_handler(server, &u2);
        httpd_register_uri_handler(server, &u3);
    }
    return server;
}

void wifi_init_softap(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    wifi_config_t ap_config = {
        .ap = { 
            .ssid = "ESP32_AP", 
            .ssid_len = strlen("ESP32_AP"), 
            .channel = 1, 
            .password = "12345678", 
            .max_connection = 4, 
            .authmode = WIFI_AUTH_WPA_WPA2_PSK 
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_config));
    ESP_ERROR_CHECK(esp_wifi_start());
}

void task_control(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(10); 

    while (1) {
        // 1. OVERSAMPLING DE HARDWARE
        uint32_t adc_accum = 0;
        for (int i = 0; i < ADC_SAMPLES; i++) {
            int raw;
            ESP_ERROR_CHECK(adc_oneshot_read(adc1_handle, ADC_CHANNEL_3, &raw));
            adc_accum += raw;
        }
        float adc_avg = (float)adc_accum / (float)ADC_SAMPLES;
        float voltage_raw = adc_avg * 3.3f / 4095.0f; 

        // 2. FILTRO EMA 
        if (voltage_filtered == 0.0f) voltage_filtered = voltage_raw;
        voltage_filtered = alpha_ema * voltage_raw + (1.0f - alpha_ema) * voltage_filtered;

        // 3. CONTROLE
        if (ctrl_mode != MODE_MANUAL) {
            float u = run_controller(voltage_filtered);
            pwm_set_duty_percent(u);
        } else {
            // Em manual, atualizamos as variáveis para bumpless transfer
            float current_duty = pwm_get_duty_percent();
            uk_1 = uk_2 = current_duty;
            ek_1 = ek_2 = (setpoint - voltage_filtered);
            // Se houver ajuste manual, o filtro acompanha imediatamente
        }
        
        float duty = pwm_get_duty_percent();
        
        // 4. BUFFERIZAÇÃO
        if (xSemaphoreTake(rb_mutex, 0) == pdTRUE) {
            rb[rb_head].v = voltage_filtered; 
            rb[rb_head].d = duty;
            rb[rb_head].sp = setpoint;
            rb_head = (rb_head + 1) % BUF_N;
            xSemaphoreGive(rb_mutex);
        }

        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}

void task_server(void *pv) { start_webserver(); vTaskDelete(NULL); }

void app_main(void) {
    ESP_ERROR_CHECK(nvs_flash_init());
    wifi_init_softap();
    adc_init();
    pwm_init();
    pwm_set_duty_percent(40.0f);
    rb_mutex = xSemaphoreCreateMutex();
    
    xTaskCreatePinnedToCore(task_control, "CTRL", 4096, NULL, 5, NULL, 1);
    xTaskCreatePinnedToCore(task_server, "WEB", 4096, NULL, 6, NULL, 0);
}