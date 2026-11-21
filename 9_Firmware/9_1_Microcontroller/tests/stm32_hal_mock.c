/*******************************************************************************
 * stm32_hal_mock.c -- Spy/recording implementation of STM32 HAL stubs
 ******************************************************************************/
#include "stm32_hal_mock.h"
#include "ad_driver_mock.h"
#include <stdio.h>
#include <stdlib.h>

/* ========================= GPIO port instances ==================== */
GPIO_TypeDef gpio_a = { .id = 0xA };
GPIO_TypeDef gpio_b = { .id = 0xB };
GPIO_TypeDef gpio_c = { .id = 0xC };
GPIO_TypeDef gpio_d = { .id = 0xD };
GPIO_TypeDef gpio_e = { .id = 0xE };
GPIO_TypeDef gpio_f = { .id = 0xF };
GPIO_TypeDef gpio_g = { .id = 0x6 };  /* 0x6 for GPIOG -- avoids overlap */

/* ========================= Peripheral instances =================== */
SPI_HandleTypeDef  hspi1 = { .id = 1 };
SPI_HandleTypeDef  hspi4 = { .id = 4 };
I2C_HandleTypeDef  hi2c1 = { .id = 1 };
I2C_HandleTypeDef  hi2c2 = { .id = 2 };
UART_HandleTypeDef huart3 = { .id = 3 };
UART_HandleTypeDef huart5 = { .id = 5 };  /* GPS UART */
ADC_HandleTypeDef  hadc3 = { .id = 3 };
TIM_HandleTypeDef  htim3 = { .id = 3 };

/* ========================= Spy log ================================ */
SpyRecord spy_log[SPY_MAX_RECORDS];
int       spy_count = 0;

/* ========================= Mock tick (forward decl for spy_reset) == */
uint32_t mock_tick = 0;

/* ========================= Printf control ========================= */
int mock_printf_enabled = 0;

/* ========================= Mock UART TX capture =================== */
uint8_t  mock_uart_tx_buf[MOCK_UART_TX_BUF_SIZE];
uint16_t mock_uart_tx_len = 0;

/* ========================= Mock UART RX buffer ==================== */
#define MOCK_UART_RX_SLOTS 8

static struct {
    uint32_t uart_id;
    uint8_t  buf[MOCK_UART_RX_BUF_SIZE];
    uint16_t head;
    uint16_t tail;
} mock_uart_rx[MOCK_UART_RX_SLOTS];

void mock_uart_tx_clear(void)
{
    mock_uart_tx_len = 0;
    memset(mock_uart_tx_buf, 0, sizeof(mock_uart_tx_buf));
}

/* ========================= Mock GPIO read ========================= */
#define GPIO_READ_TABLE_SIZE 32
static struct {
    GPIO_TypeDef *port;
    uint16_t      pin;
    GPIO_PinState val;
} gpio_read_table[GPIO_READ_TABLE_SIZE];

/* ========================= ADAR1000 SPI1 + I2C1/I2C2 Sim State ==== */
MockSpiFrame mock_spi_frames[MOCK_SPI_MAX_FRAMES];
int          mock_spi_frame_count = 0;

static bool    s_adar_sim_enabled = false;
static uint8_t s_adar_cs_low_mask = 0; /* bit 0..3 = PA0..PA3 active low */
static const uint8_t kSimHwAddr[4] = {0U, 2U, 1U, 3U}; /* RADAR_Main_Board.sch */
static uint8_t s_adar_regs[4][0x500];
static float   s_adar_base_tx_p_dbm[4][4];
static int16_t s_adar_det_override[4][4];
static uint8_t s_adar_temp_raw[4];

/* I2C1 (bus 1) DAC5578 channels & I2C2 (bus 2) ADS7830 channels */
static uint8_t s_i2c_ads_ch[3][128][8];
static bool    s_i2c_ads_ack[3][128];
static uint8_t s_i2c_ads_selected_ch[3][128];
static uint8_t s_i2c_dac_ch[3][128][8];

void mock_adar_sim_reset(void)
{
    mock_spi_frame_count = 0;
    memset(mock_spi_frames, 0, sizeof(mock_spi_frames));
    s_adar_cs_low_mask = 0;
    memset(s_adar_regs, 0, sizeof(s_adar_regs));
    for (int d = 0; d < 4; ++d) {
        s_adar_temp_raw[d] = 150U; /* 25.0 C -> (150 * 0.5) - 50 = 25 C */
        for (int c = 0; c < 4; ++c) {
            s_adar_base_tx_p_dbm[d][c] = 8.0f;
            s_adar_det_override[d][c] = -1;
        }
    }
    memset(s_i2c_ads_ch, 0, sizeof(s_i2c_ads_ch));
    memset(s_i2c_ads_selected_ch, 0, sizeof(s_i2c_ads_selected_ch));
    memset(s_i2c_dac_ch, 0, sizeof(s_i2c_dac_ch));
    for (int b = 0; b < 3; ++b) {
        for (int a = 0; a < 128; ++a) {
            s_i2c_ads_ack[b][a] = false;
        }
    }
    /* Default MainBoard I2C slaves ACK:
     *   I2C1: U7@0x48, U69@0x49 (DAC5578)
     *   I2C2: U10@0x48, U89@0x49, U88@0x4A (ADS7830) */
    s_i2c_ads_ack[1][0x48] = true;
    s_i2c_ads_ack[1][0x49] = true;
    s_i2c_ads_ack[2][0x48] = true;
    s_i2c_ads_ack[2][0x49] = true;
    s_i2c_ads_ack[2][0x4A] = true;
    for (int ch = 0; ch < 8; ++ch) {
        s_i2c_ads_ch[2][0x48][ch] = 32U; /* ~1.66 A nominal GaN PA Idq (0.42V @ G=50, R=5mOhm) */
        s_i2c_ads_ch[2][0x4A][ch] = 32U;
        s_i2c_ads_ch[2][0x49][ch] = 58U; /* ~37.5 C board temp */
    }
}

void mock_adar_sim_enable(bool enable) { s_adar_sim_enabled = enable; }

uint8_t mock_adar_sim_get_reg(uint8_t dev_idx, uint16_t reg_addr)
{
    if (dev_idx >= 4U || reg_addr >= 0x500U) return 0U;
    return s_adar_regs[dev_idx][reg_addr];
}

void mock_adar_sim_set_reg(uint8_t dev_idx, uint16_t reg_addr, uint8_t val)
{
    if (dev_idx >= 4U || reg_addr >= 0x500U) return;
    s_adar_regs[dev_idx][reg_addr] = val;
}

void mock_adar_sim_set_base_tx_power_dbm(uint8_t dev_idx, uint8_t ch_1based, float power_dbm)
{
    if (dev_idx >= 4U || ch_1based < 1U || ch_1based > 4U) return;
    s_adar_base_tx_p_dbm[dev_idx][ch_1based - 1U] = power_dbm;
}

void mock_adar_sim_set_det_override(uint8_t dev_idx, uint8_t ch_1based, int16_t raw_code_or_neg1)
{
    if (dev_idx >= 4U || ch_1based < 1U || ch_1based > 4U) return;
    s_adar_det_override[dev_idx][ch_1based - 1U] = raw_code_or_neg1;
}

void mock_adar_sim_set_temp_raw(uint8_t dev_idx, uint8_t raw_code)
{
    if (dev_idx >= 4U) return;
    s_adar_temp_raw[dev_idx] = raw_code;
}

void mock_i2c_ads7830_set_channel(uint8_t bus_id, uint8_t addr_7bit, uint8_t ch, uint8_t raw_val)
{
    if (bus_id < 3U && addr_7bit < 128U && ch < 8U) {
        s_i2c_ads_ch[bus_id][addr_7bit][ch] = raw_val;
    }
}

void mock_i2c_ads7830_set_ack(uint8_t bus_id, uint8_t addr_7bit, bool ack)
{
    if (bus_id < 3U && addr_7bit < 128U) {
        s_i2c_ads_ack[bus_id][addr_7bit] = ack;
    }
}

uint8_t mock_i2c_dac5578_get_channel(uint8_t bus_id, uint8_t addr_7bit, uint8_t ch)
{
    if (bus_id < 3U && addr_7bit < 128U && ch < 8U) {
        return s_i2c_dac_ch[bus_id][addr_7bit][ch];
    }
    return 0U;
}

void spy_reset(void)
{
    spy_count = 0;
    memset(spy_log, 0, sizeof(spy_log));
    mock_tick = 0;
    mock_printf_enabled = 0;
    memset(gpio_read_table, 0, sizeof(gpio_read_table));
    memset(mock_uart_rx, 0, sizeof(mock_uart_rx));
    mock_uart_tx_len = 0;
    memset(mock_uart_tx_buf, 0, sizeof(mock_uart_tx_buf));
    mock_adar_sim_reset();
}

const SpyRecord *spy_get(int index)
{
    if (index < 0 || index >= spy_count) return NULL;
    return &spy_log[index];
}

int spy_count_type(SpyCallType type)
{
    int count = 0;
    for (int i = 0; i < spy_count; i++) {
        if (spy_log[i].type == type) count++;
    }
    return count;
}

int spy_find_nth(SpyCallType type, int n)
{
    int found = 0;
    for (int i = 0; i < spy_count; i++) {
        if (spy_log[i].type == type) {
            if (found == n) return i;
            found++;
        }
    }
    return -1;
}

static void spy_push(SpyRecord rec)
{
    if (spy_count < SPY_MAX_RECORDS) {
        spy_log[spy_count++] = rec;
    }
}

/* ========================= Mock tick API ========================== */

void mock_set_tick(uint32_t tick)   { mock_tick = tick; }
void mock_advance_tick(uint32_t d)  { mock_tick += d; }

/* ========================= Mock GPIO read API ===================== */

void mock_gpio_set_read(GPIO_TypeDef *port, uint16_t pin, GPIO_PinState val)
{
    for (int i = 0; i < GPIO_READ_TABLE_SIZE; i++) {
        if (gpio_read_table[i].port == port && gpio_read_table[i].pin == pin) {
            gpio_read_table[i].val = val;
            return;
        }
        if (gpio_read_table[i].port == NULL) {
            gpio_read_table[i].port = port;
            gpio_read_table[i].pin  = pin;
            gpio_read_table[i].val  = val;
            return;
        }
    }
}

/* ========================= HAL Implementations ==================== */

void HAL_GPIO_WritePin(GPIO_TypeDef *GPIOx, uint16_t GPIO_Pin, GPIO_PinState PinState)
{
    if (GPIOx == GPIOA) {
        for (uint8_t d = 0; d < 4U; ++d) {
            uint16_t cs_mask = (uint16_t)(1U << d);
            if ((GPIO_Pin & cs_mask) != 0U) {
                if (PinState == GPIO_PIN_RESET) {
                    s_adar_cs_low_mask |= (uint8_t)(1U << d);
                } else {
                    s_adar_cs_low_mask &= (uint8_t)~(1U << d);
                }
            }
        }
    }
    spy_push((SpyRecord){
        .type  = SPY_GPIO_WRITE,
        .port  = GPIOx,
        .pin   = GPIO_Pin,
        .value = (uint32_t)PinState,
        .extra = NULL
    });
}

GPIO_PinState HAL_GPIO_ReadPin(GPIO_TypeDef *GPIOx, uint16_t GPIO_Pin)
{
    GPIO_PinState result = GPIO_PIN_RESET;
    for (int i = 0; i < GPIO_READ_TABLE_SIZE; i++) {
        if (gpio_read_table[i].port == GPIOx && gpio_read_table[i].pin == GPIO_Pin) {
            result = gpio_read_table[i].val;
            break;
        }
    }
    spy_push((SpyRecord){
        .type  = SPY_GPIO_READ,
        .port  = GPIOx,
        .pin   = GPIO_Pin,
        .value = (uint32_t)result,
        .extra = NULL
    });
    return result;
}

void HAL_GPIO_TogglePin(GPIO_TypeDef *GPIOx, uint16_t GPIO_Pin)
{
    spy_push((SpyRecord){
        .type  = SPY_GPIO_TOGGLE,
        .port  = GPIOx,
        .pin   = GPIO_Pin,
        .value = 0,
        .extra = NULL
    });
}

uint32_t HAL_GetTick(void)
{
    spy_push((SpyRecord){
        .type  = SPY_HAL_GET_TICK,
        .port  = NULL,
        .pin   = 0,
        .value = mock_tick,
        .extra = NULL
    });
    return mock_tick;
}

void HAL_Delay(uint32_t Delay)
{
    spy_push((SpyRecord){
        .type  = SPY_HAL_DELAY,
        .port  = NULL,
        .pin   = 0,
        .value = Delay,
        .extra = NULL
    });
    mock_tick += Delay;
}

HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *huart, const uint8_t *pData,
                                     uint16_t Size, uint32_t Timeout)
{
    spy_push((SpyRecord){
        .type  = SPY_UART_TX,
        .port  = NULL,
        .pin   = Size,
        .value = Timeout,
        .extra = huart
    });
    /* Capture TX data for test inspection */
    for (uint16_t i = 0; i < Size && mock_uart_tx_len < MOCK_UART_TX_BUF_SIZE; i++) {
        mock_uart_tx_buf[mock_uart_tx_len++] = pData[i];
    }
    return HAL_OK;
}

/* ========================= Mock UART RX helpers ====================== */

/* find_rx_slot, mock_uart_rx_load, etc. use the mock_uart_rx declared above */

static int find_rx_slot(UART_HandleTypeDef *huart)
{
    if (huart == NULL) return -1;
    /* Find existing slot */
    for (int i = 0; i < MOCK_UART_RX_SLOTS; i++) {
        if (mock_uart_rx[i].uart_id == huart->id && mock_uart_rx[i].head != mock_uart_rx[i].tail) {
            return i;
        }
        if (mock_uart_rx[i].uart_id == huart->id) {
            return i;
        }
    }
    /* Find empty slot */
    for (int i = 0; i < MOCK_UART_RX_SLOTS; i++) {
        if (mock_uart_rx[i].uart_id == 0) {
            mock_uart_rx[i].uart_id = huart->id;
            return i;
        }
    }
    return -1;
}

void mock_uart_rx_load(UART_HandleTypeDef *huart, const uint8_t *data, uint16_t len)
{
    int slot = find_rx_slot(huart);
    if (slot < 0) return;
    mock_uart_rx[slot].uart_id = huart->id;
    for (uint16_t i = 0; i < len; i++) {
        uint16_t next = (mock_uart_rx[slot].head + 1) % MOCK_UART_RX_BUF_SIZE;
        if (next == mock_uart_rx[slot].tail) break;  /* Buffer full */
        mock_uart_rx[slot].buf[mock_uart_rx[slot].head] = data[i];
        mock_uart_rx[slot].head = next;
    }
}

void mock_uart_rx_clear(UART_HandleTypeDef *huart)
{
    int slot = find_rx_slot(huart);
    if (slot < 0) return;
    mock_uart_rx[slot].head = 0;
    mock_uart_rx[slot].tail = 0;
}

HAL_StatusTypeDef HAL_UART_Receive(UART_HandleTypeDef *huart, uint8_t *pData,
                                    uint16_t Size, uint32_t Timeout)
{
    (void)Timeout;
    int slot = find_rx_slot(huart);
    if (slot < 0) return HAL_TIMEOUT;

    for (uint16_t i = 0; i < Size; i++) {
        if (mock_uart_rx[slot].head == mock_uart_rx[slot].tail) {
            return HAL_TIMEOUT;  /* No more data */
        }
        pData[i] = mock_uart_rx[slot].buf[mock_uart_rx[slot].tail];
        mock_uart_rx[slot].tail = (mock_uart_rx[slot].tail + 1) % MOCK_UART_RX_BUF_SIZE;
    }

    spy_push((SpyRecord){
        .type  = SPY_UART_RX,
        .port  = NULL,
        .pin   = Size,
        .value = Timeout,
        .extra = huart
    });

    return HAL_OK;
}

/* ========================= no_os delay stubs ====================== */

void no_os_udelay(uint32_t usecs)
{
    spy_push((SpyRecord){
        .type  = SPY_NO_OS_UDELAY,
        .port  = NULL,
        .pin   = 0,
        .value = usecs,
        .extra = NULL
    });
}

void no_os_mdelay(uint32_t msecs)
{
    spy_push((SpyRecord){
        .type  = SPY_HAL_DELAY,
        .port  = NULL,
        .pin   = 0,
        .value = msecs,
        .extra = NULL
    });
    mock_tick += msecs;
}

/* ========================= ADS7830 stub =========================== */

uint8_t ADS7830_Measure_SingleEnded(ADC_HandleTypeDef *hadc, uint8_t channel)
{
    spy_push((SpyRecord){
        .type  = SPY_ADS7830_MEASURE,
        .port  = NULL,
        .pin   = channel,
        .value = 100,  /* stub: always return 100 (~64.7 C) */
        .extra = hadc
    });
    return 100;
}

/* ========================= TIM PWM stubs ========================== */

HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *htim, uint32_t Channel)
{
    spy_push((SpyRecord){
        .type  = SPY_TIM_PWM_START,
        .port  = NULL,
        .pin   = (uint16_t)Channel,
        .value = htim->id,
        .extra = htim
    });
    return HAL_OK;
}

HAL_StatusTypeDef HAL_TIM_PWM_Stop(TIM_HandleTypeDef *htim, uint32_t Channel)
{
    spy_push((SpyRecord){
        .type  = SPY_TIM_PWM_STOP,
        .port  = NULL,
        .pin   = (uint16_t)Channel,
        .value = htim->id,
        .extra = htim
    });
    return HAL_OK;
}

void mock_tim_set_compare(TIM_HandleTypeDef *htim, uint32_t Channel, uint32_t Compare)
{
    spy_push((SpyRecord){
        .type  = SPY_TIM_SET_COMPARE,
        .port  = NULL,
        .pin   = (uint16_t)Channel,
        .value = Compare,
        .extra = htim
    });
}

/* ========================= SPI & I2C stubs ======================== */

static int8_t get_asserted_adar_cs_dev(void)
{
    for (uint8_t d = 0; d < 4U; ++d) {
        if ((s_adar_cs_low_mask & (uint8_t)(1U << d)) != 0U) {
            return (int8_t)d;
        }
    }
    return -1;
}

static uint8_t compute_adar_det_adc(uint8_t dev, uint8_t ch_1based)
{
    uint8_t ch0 = (uint8_t)(ch_1based - 1U);
    if (s_adar_det_override[dev][ch0] >= 0) {
        int16_t ov = s_adar_det_override[dev][ch0];
        return (ov > 255) ? 255U : (uint8_t)ov;
    }

    /* Check 0x030 MISC_ENABLES:
     *   Bit 5 (BIAS_EN) MUST be 0 (active-low enabled)
     *   Bit (4 - ch_1based) (CHx_DET_EN) MUST be 1
     *   PA_BIASx_ON (0x029 + ch0) must not be pinched off at 0x5D */
    uint8_t misc = s_adar_regs[dev][0x030];
    uint8_t det_en_bit = (uint8_t)(1U << (4U - ch_1based));
    uint8_t pa_bias_on = s_adar_regs[dev][0x029U + ch0];
    if ((misc & (1U << 5U)) != 0U || (misc & det_en_bit) == 0U || pa_bias_on == 0x5DU) {
        return 4U; /* Noise floor when detector disabled or PA pinched off */
    }

    uint8_t tx_gain_reg = s_adar_regs[dev][0x01CU + ch0];
    uint8_t vga_code = (uint8_t)(tx_gain_reg & 0x7FU);
    float attn_db = ((tx_gain_reg & 0x80U) != 0U) ? 0.0f : -15.0f;
    float p_dbm = s_adar_base_tx_p_dbm[dev][ch0] - (float)(127 - (int)vga_code) * 0.5f + attn_db;
    float raw_f = 60.0f + p_dbm * 6.0f;
    if (raw_f < 0.0f) return 0U;
    if (raw_f > 255.0f) return 255U;
    return (uint8_t)(raw_f + 0.5f);
}

static void handle_adar1000_spi1_frame(const uint8_t *tx, uint8_t *rx, uint16_t size)
{
    int8_t cs_dev = get_asserted_adar_cs_dev();
    if (mock_spi_frame_count < MOCK_SPI_MAX_FRAMES) {
        MockSpiFrame *f = &mock_spi_frames[mock_spi_frame_count++];
        f->hspi_id = 1U;
        f->asserted_cs_dev = cs_dev;
        f->size = size;
        memset(f->tx, 0, sizeof(f->tx));
        memset(f->rx, 0, sizeof(f->rx));
        for (uint16_t i = 0; i < size && i < 4U; ++i) {
            f->tx[i] = tx ? tx[i] : 0U;
        }
    }

    if (!s_adar_sim_enabled || cs_dev < 0 || size != 3U || tx == NULL) {
        return;
    }

    uint8_t is_read   = (uint8_t)((tx[0] & 0x80U) != 0U);
    uint8_t is_bcast  = (uint8_t)((tx[0] & 0x78U) == 0x08U);
    uint8_t hdr_addr  = (uint8_t)((tx[0] >> 5U) & 0x03U);
    uint16_t reg_addr = (uint16_t)(((uint16_t)(tx[0] & 0x1FU) << 8U) | tx[1]);
    uint8_t data      = tx[2];

    if (reg_addr >= 0x500U) {
        return;
    }

    /* Hardware chip address check: ADAR1000 ignores non-broadcast frames whose
     * AD1:AD0 bits [14:13] do not match its physical ADDR1:ADDR0 pins! */
    if (!is_bcast && hdr_addr != kSimHwAddr[(uint8_t)cs_dev]) {
        if (rx != NULL) {
            rx[0] = 0U; rx[1] = 0U; rx[2] = 0U;
        }
        return;
    }

    if (is_read) {
        uint8_t val = s_adar_regs[(uint8_t)cs_dev][reg_addr];
        if (rx != NULL) {
            rx[0] = 0U;
            rx[1] = 0U;
            rx[2] = val;
        }
        if (mock_spi_frame_count > 0) {
            mock_spi_frames[mock_spi_frame_count - 1].rx[2] = val;
        }
    } else {
        /* Write */
        uint8_t d_start = is_bcast ? 0U : (uint8_t)cs_dev;
        uint8_t d_end   = is_bcast ? 4U : (uint8_t)(cs_dev + 1);
        for (uint8_t d = d_start; d < d_end; ++d) {
            if (reg_addr == 0x000U && (data & 0x81U) == 0x81U) {
                /* Soft reset clears register file */
                memset(s_adar_regs[d], 0, sizeof(s_adar_regs[d]));
                continue;
            }
            s_adar_regs[d][reg_addr] = data;

            /* 0x032 ADC_CTRL: if ST_CONV (bit 4) triggered while ADC_EN (bit 6) & CLK_EN (bit 5) set */
            if (reg_addr == 0x032U && (data & 0x70U) == 0x70U) {
                uint8_t mux = (uint8_t)((data >> 1U) & 0x07U);
                uint8_t adc_out = 0U;
                if (mux == 0U) {
                    adc_out = s_adar_temp_raw[d];
                } else if (mux >= 1U && mux <= 4U) {
                    adc_out = compute_adar_det_adc(d, mux);
                }
                s_adar_regs[d][0x033U] = adc_out;
                /* ST_CONV self-clears and ADC_EOC (bit 0) asserts high */
                s_adar_regs[d][0x032U] = (uint8_t)((data & (uint8_t)~0x10U) | 0x01U);
            }
        }
    }
}

HAL_StatusTypeDef HAL_SPI_TransmitReceive(SPI_HandleTypeDef *hspi, uint8_t *pTxData, uint8_t *pRxData, uint16_t Size, uint32_t Timeout)
{
    if (hspi != NULL && hspi->id == 1U) {
        handle_adar1000_spi1_frame(pTxData, pRxData, Size);
    }
    spy_push((SpyRecord){
        .type  = SPY_SPI_TRANSMIT_RECEIVE,
        .port  = NULL,
        .pin   = Size,
        .value = Timeout,
        .extra = hspi
    });
    return HAL_OK;
}

HAL_StatusTypeDef HAL_SPI_Transmit(SPI_HandleTypeDef *hspi, uint8_t *pData, uint16_t Size, uint32_t Timeout)
{
    if (hspi != NULL && hspi->id == 1U) {
        handle_adar1000_spi1_frame(pData, NULL, Size);
    }
    spy_push((SpyRecord){
        .type  = SPY_SPI_TRANSMIT,
        .port  = NULL,
        .pin   = Size,
        .value = Timeout,
        .extra = hspi
    });
    return HAL_OK;
}

HAL_StatusTypeDef HAL_I2C_Master_Transmit(I2C_HandleTypeDef *hi2c, uint16_t DevAddress, uint8_t *pData, uint16_t Size, uint32_t Timeout)
{
    (void)Timeout;
    if (hi2c == NULL || pData == NULL || Size == 0U) {
        return HAL_ERROR;
    }
    uint8_t bus_id = (uint8_t)hi2c->id;
    uint8_t addr7  = (uint8_t)(DevAddress >> 1U);
    if (bus_id >= 3U || addr7 >= 128U || !s_i2c_ads_ack[bus_id][addr7]) {
        return HAL_ERROR;
    }

    if (bus_id == 2U && Size == 1U) {
        /* ADS7830 command byte: bits [6:4] = channel index */
        s_i2c_ads_selected_ch[bus_id][addr7] = (uint8_t)((pData[0] >> 4U) & 0x07U);
    } else if (bus_id == 1U && Size == 3U) {
        /* DAC5578 write/update command: cmd in pData[0], 8-bit code in pData[2] */
        uint8_t cmd_hi = (uint8_t)((pData[0] >> 4U) & 0x0FU);
        uint8_t ch     = (uint8_t)(pData[0] & 0x07U);
        if (cmd_hi == 0x0U || cmd_hi == 0x2U) {
            s_i2c_dac_ch[bus_id][addr7][ch] = pData[2];
        } else if (cmd_hi == 0x3U) {
            for (uint8_t c = 0; c < 8U; ++c) {
                s_i2c_dac_ch[bus_id][addr7][c] = pData[2];
            }
        }
    }
    return HAL_OK;
}

HAL_StatusTypeDef HAL_I2C_Master_Receive(I2C_HandleTypeDef *hi2c, uint16_t DevAddress, uint8_t *pData, uint16_t Size, uint32_t Timeout)
{
    (void)Timeout;
    if (hi2c == NULL || pData == NULL || Size == 0U) {
        return HAL_ERROR;
    }
    uint8_t bus_id = (uint8_t)hi2c->id;
    uint8_t addr7  = (uint8_t)(DevAddress >> 1U);
    if (bus_id >= 3U || addr7 >= 128U || !s_i2c_ads_ack[bus_id][addr7]) {
        return HAL_ERROR;
    }

    if (bus_id == 2U && Size == 1U) {
        uint8_t ch = s_i2c_ads_selected_ch[bus_id][addr7];
        pData[0] = s_i2c_ads_ch[bus_id][addr7][ch];
    } else {
        memset(pData, 0, Size);
    }
    return HAL_OK;
}

/* Stub for platform_noos_stm32.c GPIO functions */
void hal_set_gpio_by_index(uint8_t idx, uint8_t value) {
    (void)idx; (void)value;
}

/* ========================= Mock stm32_spi_ops ===================== */

/* Stub SPI platform ops -- real adf4382a_manager.c references &stm32_spi_ops.
 * In tests, adf4382_init() is mocked so no_os_spi_init() is never called.
 * We provide a non-NULL struct so tests can assert platform_ops != NULL. */
static int mock_spi_init_stub(void) { return 0; }

const struct no_os_spi_platform_ops stm32_spi_ops = {
    .init = mock_spi_init_stub,
};
