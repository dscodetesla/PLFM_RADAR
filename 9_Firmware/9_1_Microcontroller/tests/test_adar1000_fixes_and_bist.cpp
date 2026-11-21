// test_adar1000_fixes_and_bist.cpp -- Comprehensive C++ regression suite for:
//   - Bug 1: 0x030 MISC_ENABLES Bit 5 (BIAS_EN) active-low (0 = bias DACs enabled)
//   - Bug 2: Hardware SPI chip addresses ADDR1:ADDR0 = {0, 2, 1, 3} per RADAR_Main_Board.sch
//   - Bug 3: Safe 1-based channel indexing (1..4 -> channel - 1) across all Gain/Phase/PA Bias APIs
//   - Bug 4: ADAR1000_PcbPhaseLut.h (6-bit & 7-bit LUTs), non-linear ADTR1107 quadrant routing,
//            I2C1/I2C2 bus separation (U7@0x48, U69@0x49 vs U10@0x48, U88@0x4A, U89@0x49),
//            and ADAR1000_BIST (CPLR_OUT -> DET1..4 + Idq + closed-loop TX power equalization).

#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>

#include "stm32_hal_mock.h"
#include "ADAR1000_Manager.h"
#include "ADAR1000_PcbPhaseLut.h"
#include "ADAR1000_BIST.h"

uint8_t GUI_start_flag_received = 0;
uint8_t USB_Buffer[64] = {0};
extern "C" void Error_Handler(void) {}

static int g_passed = 0;
static int g_total  = 0;

#define RUN_TEST(fn)                                                           \
    do {                                                                        \
        g_total++;                                                              \
        std::printf("  [%2d] %-58s ", g_total, #fn);                            \
        fn();                                                                   \
        g_passed++;                                                             \
        std::printf("PASS\n");                                                  \
    } while (0)

// ---------------------------------------------------------------------------
// Suite 1: Bug 1 -- 0x030 MISC_ENABLES Bit 5 (BIAS_EN) active-low verification
// ---------------------------------------------------------------------------
static void test_bug1_bias_en_active_low_tx_and_rx()
{
    spy_reset();
    mock_adar_sim_enable(true);

    ADAR1000Manager mgr;

    // Pollute Bit 5 (0x20 = disabled) in simulated register bank before init/mode switch
    for (uint8_t dev = 0; dev < 4U; ++dev) {
        mock_adar_sim_set_reg(dev, REG_MISC_ENABLES, 0x25U);
    }

    // Switch to TX mode -> must clear Bit 5 to 0 while preserving detector bits
    mgr.setADTR1107Mode(ADAR1000Manager::BeamDirection::TX);
    for (uint8_t dev = 0; dev < 4U; ++dev) {
        const uint8_t misc_tx = mock_adar_sim_get_reg(dev, REG_MISC_ENABLES);
        assert((misc_tx & MISC_ENABLES_BIAS_EN_MASK) == 0U);
        assert((misc_tx & 0x05U) == 0x05U);
        const uint8_t sw_tx = mock_adar_sim_get_reg(dev, REG_SW_CONTROL);
        assert((sw_tx & (1U << 2U)) != 0U);
    }

    // Pollute Bit 5 again and switch to RX mode -> must clear Bit 5 to 0 and set Bit 4 (LNA_BIAS_OUT_EN)
    for (uint8_t dev = 0; dev < 4U; ++dev) {
        mock_adar_sim_set_reg(dev, REG_MISC_ENABLES, 0x20U);
    }
    mgr.setADTR1107Mode(ADAR1000Manager::BeamDirection::RX);
    for (uint8_t dev = 0; dev < 4U; ++dev) {
        const uint8_t misc_rx = mock_adar_sim_get_reg(dev, REG_MISC_ENABLES);
        assert((misc_rx & MISC_ENABLES_BIAS_EN_MASK) == 0U);
        assert((misc_rx & MISC_ENABLES_LNA_BIAS_OUT_EN) != 0U);
    }

    // Also verify initializeSingleDevice leaves BIAS_EN == 0
    assert(mgr.initializeAllDevices());
    for (uint8_t dev = 0; dev < 4U; ++dev) {
        const uint8_t misc_init = mock_adar_sim_get_reg(dev, REG_MISC_ENABLES);
        assert((misc_init & MISC_ENABLES_BIAS_EN_MASK) == 0U);
    }
}

// ---------------------------------------------------------------------------
// Suite 2: Bug 2 -- Hardware SPI ADDR1:ADDR0 = {0, 2, 1, 3} per schematic
// ---------------------------------------------------------------------------
static void test_bug2_hardware_spi_addresses()
{
    spy_reset();
    mock_adar_sim_enable(true);

    ADAR1000Manager mgr;
    assert(mgr.devices_.size() == 4U);
    assert(mgr.devices_[0]->dev_addr == 0U); // ADAR1_ = 0b00
    assert(mgr.devices_[1]->dev_addr == 2U); // ADAR2_ = 0b10
    assert(mgr.devices_[2]->dev_addr == 1U); // ADAR3_ = 0b01
    assert(mgr.devices_[3]->dev_addr == 3U); // ADAR4_ = 0b11

    // Verify scratchpad write/read (0xA5) succeeds on all 4 physical devices
    for (uint8_t dev = 0; dev < 4U; ++dev) {
        assert(mgr.verifyDeviceCommunication(dev));
    }

    // Regression proof: if ADAR2_ (dev=1) had legacy wrong address 1 instead of 2,
    // hardware chip-address comparator rejects the SPI frame!
    mgr.devices_[1]->dev_addr = 1U;
    assert(!mgr.verifyDeviceCommunication(1U));
    mgr.devices_[1]->dev_addr = 2U;
    assert(mgr.verifyDeviceCommunication(1U));
}

// ---------------------------------------------------------------------------
// Suite 3: Bug 3 -- 1-based channel indexing (1..4) without CH4->CH1 wrap
// ---------------------------------------------------------------------------
static void test_bug3_one_based_channel_indexing_and_bounds()
{
    spy_reset();
    mock_adar_sim_enable(true);

    ADAR1000Manager mgr;

    // 1. TX VGA Gain: channels 1..4 must map to 0x01C, 0x01D, 0x01E, 0x01F
    const uint8_t tx_gains[4] = {0x71U, 0x72U, 0x73U, 0x74U};
    for (uint8_t ch = 1U; ch <= 4U; ++ch) {
        mgr.adarSetTxVgaGain(0U, ch, tx_gains[ch - 1U], BROADCAST_OFF);
    }
    assert(mock_adar_sim_get_reg(0U, REG_CH1_TX_GAIN) == 0x71U); // NOT overwritten by ch=4!
    assert(mock_adar_sim_get_reg(0U, REG_CH2_TX_GAIN) == 0x72U);
    assert(mock_adar_sim_get_reg(0U, REG_CH3_TX_GAIN) == 0x73U);
    assert(mock_adar_sim_get_reg(0U, REG_CH4_TX_GAIN) == 0x74U); // 0x01F written properly!

    // 2. RX VGA Gain: channels 1..4 must map to 0x010, 0x011, 0x012, 0x013
    const uint8_t rx_gains[4] = {0x21U, 0x22U, 0x23U, 0x24U};
    for (uint8_t ch = 1U; ch <= 4U; ++ch) {
        mgr.adarSetRxVgaGain(1U, ch, rx_gains[ch - 1U], BROADCAST_OFF);
    }
    assert(mock_adar_sim_get_reg(1U, REG_CH1_RX_GAIN) == 0x21U);
    assert(mock_adar_sim_get_reg(1U, REG_CH2_RX_GAIN) == 0x22U);
    assert(mock_adar_sim_get_reg(1U, REG_CH3_RX_GAIN) == 0x23U);
    assert(mock_adar_sim_get_reg(1U, REG_CH4_RX_GAIN) == 0x24U);

    // 3. TX Phase: channels 1..4 must map to 0x020/0x021 .. 0x026/0x027 + LDTX_OVERRIDE (0x02)
    const uint8_t phases[4] = {0U, 16U, 32U, 64U};
    for (uint8_t ch = 1U; ch <= 4U; ++ch) {
        mgr.adarSetTxPhase(2U, ch, phases[ch - 1U], BROADCAST_OFF);
    }
    for (uint8_t ch = 1U; ch <= 4U; ++ch) {
        const uint16_t reg_i = static_cast<uint16_t>(REG_CH1_TX_PHS_I + (ch - 1U) * 2U);
        const uint16_t reg_q = static_cast<uint16_t>(REG_CH1_TX_PHS_Q + (ch - 1U) * 2U);
        assert(mock_adar_sim_get_reg(2U, reg_i) == ADAR1000Manager::VM_I[phases[ch - 1U]]);
        assert(mock_adar_sim_get_reg(2U, reg_q) == ADAR1000Manager::VM_Q[phases[ch - 1U]]);
    }
    assert(mock_adar_sim_get_reg(2U, REG_LOAD_WORKING) == LD_WRK_REGS_LDTX_OVERRIDE);

    // 4. RX Phase: channels 1..4 must map to 0x014/0x015 .. 0x01A/0x01B + LDRX_OVERRIDE (0x01)
    for (uint8_t ch = 1U; ch <= 4U; ++ch) {
        mgr.adarSetRxPhase(3U, ch, phases[ch - 1U], BROADCAST_OFF);
    }
    for (uint8_t ch = 1U; ch <= 4U; ++ch) {
        const uint16_t reg_i = static_cast<uint16_t>(REG_CH1_RX_PHS_I + (ch - 1U) * 2U);
        const uint16_t reg_q = static_cast<uint16_t>(REG_CH1_RX_PHS_Q + (ch - 1U) * 2U);
        assert(mock_adar_sim_get_reg(3U, reg_i) == ADAR1000Manager::VM_I[phases[ch - 1U]]);
        assert(mock_adar_sim_get_reg(3U, reg_q) == ADAR1000Manager::VM_Q[phases[ch - 1U]]);
    }
    assert(mock_adar_sim_get_reg(3U, REG_LOAD_WORKING) == LD_WRK_REGS_LDRX_OVERRIDE);

    // 5. Out-of-bounds channel=0, channel=5, and deviceIndex=4 must emit ZERO SPI frames
    const int before_frames = mock_spi_frame_count;
    mgr.adarSetTxVgaGain(0U, 0U, 0x55U, BROADCAST_OFF);
    mgr.adarSetTxVgaGain(0U, 5U, 0x55U, BROADCAST_OFF);
    mgr.adarSetRxVgaGain(0U, 0U, 0x55U, BROADCAST_OFF);
    mgr.adarSetRxVgaGain(0U, 5U, 0x55U, BROADCAST_OFF);
    mgr.adarSetTxPhase(0U, 0U, 10U, BROADCAST_OFF);
    mgr.adarSetTxPhase(0U, 5U, 10U, BROADCAST_OFF);
    mgr.adarSetRxPhase(0U, 0U, 10U, BROADCAST_OFF);
    mgr.adarSetRxPhase(0U, 5U, 10U, BROADCAST_OFF);
    mgr.adarSetPaBiasOn(0U, 0U, 0x39U, BROADCAST_OFF);
    mgr.adarSetPaBiasOn(0U, 5U, 0x39U, BROADCAST_OFF);
    mgr.adarSetTxVgaGain(4U, 1U, 0x55U, BROADCAST_OFF);
    assert(mock_spi_frame_count == before_frames);
}

// ---------------------------------------------------------------------------
// Suite 4: Bug 4 -- PCB Phase LUT (6-bit & 7-bit), Quadrant Routing & I2C1/I2C2
// ---------------------------------------------------------------------------
static void test_bug4_pcb_phase_lut_and_quadrant_i2c_topology()
{
    const uint8_t expected_tx_6b[16] = {
        0x00, 0x00, 0x00, 0x00, 0x01, 0x3F, 0x3D, 0x3E,
        0x3F, 0x3E, 0x3D, 0x3C, 0x3F, 0x3F, 0x3D, 0x3D
    };
    const uint8_t expected_rx_6b[16] = {
        0x00, 0x00, 0x00, 0x01, 0x01, 0x07, 0x3E, 0x3F,
        0x06, 0x02, 0x3F, 0x3F, 0x04, 0x05, 0x3F, 0x01
    };

    for (uint8_t i = 0; i < 16U; ++i) {
        assert(kPcbPhaseOffsetCodeTx[i] == expected_tx_6b[i]);
        assert(kPcbPhaseOffsetCodeRx[i] == expected_rx_6b[i]);
        assert((kPcbPhaseOffsetCodeTx[i] & 0xC0U) == 0U);
        assert((kPcbPhaseOffsetCodeRx[i] & 0xC0U) == 0U);
        assert((kPcbPhaseOffsetCode7BitTx[i] & 0x80U) == 0U);
        assert((kPcbPhaseOffsetCode7BitRx[i] & 0x80U) == 0U);
    }

    // Verify bijective 16-channel quadrant mapping ADAR1..4 CH1..4 <-> ADTR1107_1..16
    bool seen_adtr[16] = {false};
    for (uint8_t dev = 0; dev < 4U; ++dev) {
        for (uint8_t ch1 = 1U; ch1 <= 4U; ++ch1) {
            const uint8_t adtr0 = mapAdarChannelToAdtr1107ZeroBased(dev, ch1);
            assert(adtr0 < 16U);
            assert(!seen_adtr[adtr0]);
            seen_adtr[adtr0] = true;
            assert(kAdtr1107ZeroBasedToAdarDev[adtr0] == dev);
            assert(kAdtr1107ZeroBasedToAdarCh1Based[adtr0] == ch1);
        }
    }

    // Verify setCustomBeamPattern16 applies 7-bit PCB trace phase offsets cleanly
    spy_reset();
    mock_adar_sim_enable(true);
    ADAR1000Manager mgr;
    uint8_t zero_beam[16] = {0U};
    mgr.setPcbPhaseCompensation(true);
    mgr.setCustomBeamPattern16(zero_beam, ADAR1000Manager::BeamDirection::TX);
    mgr.setCustomBeamPattern16(zero_beam, ADAR1000Manager::BeamDirection::RX);

    for (uint8_t dev = 0; dev < 4U; ++dev) {
        for (uint8_t ch = 0; ch < 4U; ++ch) {
            const uint8_t ap = static_cast<uint8_t>(dev * 4U + ch);
            const uint8_t tx_p7 = kPcbPhaseOffsetCode7BitTx[ap];
            const uint8_t rx_p7 = kPcbPhaseOffsetCode7BitRx[ap];
            assert(mock_adar_sim_get_reg(dev, static_cast<uint16_t>(REG_CH1_TX_PHS_I + ch * 2U)) == ADAR1000Manager::VM_I[tx_p7]);
            assert(mock_adar_sim_get_reg(dev, static_cast<uint16_t>(REG_CH1_TX_PHS_Q + ch * 2U)) == ADAR1000Manager::VM_Q[tx_p7]);
            assert(mock_adar_sim_get_reg(dev, static_cast<uint16_t>(REG_CH1_RX_PHS_I + ch * 2U)) == ADAR1000Manager::VM_I[rx_p7]);
            assert(mock_adar_sim_get_reg(dev, static_cast<uint16_t>(REG_CH1_RX_PHS_Q + ch * 2U)) == ADAR1000Manager::VM_Q[rx_p7]);
        }
    }

    // Verify I2C1 DAC (U7@0x48, U69@0x49) and I2C2 ADC (U10@0x48, U88@0x4A, U89@0x49) bus isolation
    uint8_t dac_frame[3] = {0x20U, 0x00U, 0x7EU}; // DAC5578 WRITE_UPDATE ch0 = 126 on I2C1 @ 0x48
    mock_i2c_ads7830_set_channel(2U, 0x48U, 0U, 108U); // U10 @ 0x48 ch0 on I2C2
    assert(HAL_I2C_Master_Transmit(&hi2c1, static_cast<uint16_t>(kI2c1DacVgBank0Addr7Bit << 1U), dac_frame, 3U, 100U) == HAL_OK);
    assert(mock_i2c_dac5578_get_channel(1U, 0x48U, 0U) == 0x7EU);

    ADAR1000_BIST bist;
    uint8_t raw_u10 = 0U;
    assert(bist.readAds7830Channel(kI2c2AdcIdqBank0Addr7Bit, 0U, &raw_u10));
    assert(raw_u10 == 108U); // Uncorrupted by I2C1 write to 0x48!
}

// ---------------------------------------------------------------------------
// Suite 5a: BIST -- 4.00 dB TX power spread across 16 channels -> 0.00 dB in <= 2 iters
// ---------------------------------------------------------------------------
static void test_bist_nominal_4db_spread_equalizes_to_zero()
{
    spy_reset();
    mock_adar_sim_enable(true);

    ADAR1000Manager mgr;
    assert(mgr.initializeAllDevices());

    // Seed a deterministic 4.00 dB TX output power gradient (6.0 dBm .. 10.0 dBm in 0.5 dB steps)
    const float offsets_db[16] = {
         6.0f,  6.5f,  7.0f,  7.5f,
         8.0f,  8.5f,  9.0f,  9.5f,
        10.0f,  9.5f,  9.0f,  8.5f,
         8.0f,  7.5f,  7.0f,  6.0f
    };
    for (uint8_t ap = 0; ap < 16U; ++ap) {
        const uint8_t dev = static_cast<uint8_t>(ap / 4U);
        const uint8_t ch1 = static_cast<uint8_t>((ap % 4U) + 1U);
        mock_adar_sim_set_base_tx_power_dbm(dev, ch1, offsets_db[ap]);
    }

    ADAR1000_BIST::Config cfg;
    cfg.spread_tolerance_db = 0.05f; // Strict zero-spread convergence check
    ADAR1000_BIST bist(cfg);

    const ADAR1000_BIST::Report rep = bist.runFullBist(mgr);
    assert(rep.overall_pass);
    assert(rep.spi_bus_healthy);
    assert(rep.bias_en_verified_active_low);
    assert(rep.healthy_channel_count == 16U);
    assert(rep.faulty_channel_count == 0U);
    assert(std::fabs(rep.initial_spread_db - 4.00f) < 0.01f);
    assert(rep.final_spread_db < 0.01f); // 0.00 dB post-equalization spread!
    assert(rep.iterations_executed >= 1U && rep.iterations_executed <= 2U);
    assert(rep.max_board_temp_c > 30.0f && rep.max_board_temp_c < 45.0f);
}

// ---------------------------------------------------------------------------
// Suite 5b: BIST -- OPEN_CIRCUIT coupler fault detection
// ---------------------------------------------------------------------------
static void test_bist_open_circuit_fault_detection()
{
    spy_reset();
    mock_adar_sim_enable(true);

    ADAR1000Manager mgr;
    assert(mgr.initializeAllDevices());

    // Inject open RF trace / dead coupler on ADAR2_ CH3 (aperture idx 6 -> ADTR1107_6)
    mock_adar_sim_set_det_override(1U, 3U, 3); // 3 < min_det_code_open (12)

    ADAR1000_BIST bist;
    const ADAR1000_BIST::Report rep = bist.runFullBist(mgr);

    assert(!rep.overall_pass);
    assert(rep.healthy_channel_count == 15U);
    assert(rep.faulty_channel_count == 1U);
    assert(rep.channels[6].adtr1107_1based == 6U);
    assert((rep.channels[6].fault_mask & ADAR1000_BIST::FAULT_OPEN_CIRCUIT) != 0U);
    assert(rep.final_spread_db <= 0.25f);
}

// ---------------------------------------------------------------------------
// Suite 5c: BIST -- OVERDRIVE_HIGH_VSWR fault + automatic PA gate pinch-off
// ---------------------------------------------------------------------------
static void test_bist_overdrive_high_vswr_pinchoff()
{
    spy_reset();
    mock_adar_sim_enable(true);

    ADAR1000Manager mgr;
    assert(mgr.initializeAllDevices());

    // Inject severe reflection / overdrive on ADAR3_ CH4 (aperture idx 11 -> ADTR1107_9)
    mock_adar_sim_set_det_override(2U, 4U, 245); // > max_det_code_overdrive (225)

    ADAR1000_BIST bist;
    const ADAR1000_BIST::Report rep = bist.runFullBist(mgr);

    assert(!rep.overall_pass);
    assert(rep.healthy_channel_count == 15U);
    assert(rep.faulty_channel_count == 1U);
    assert(rep.channels[11].adtr1107_1based == 9U);
    assert((rep.channels[11].fault_mask & ADAR1000_BIST::FAULT_OVERDRIVE_HIGH_VSWR) != 0U);

    // Verify BIST pinched off PA_BIAS4_ON (0x02C) on ADAR3_ (dev=2) to kPaBiasTxSafe (0x5D)
    // and muted CH4_TX_GAIN (0x01F) to 0x00!
    assert(mock_adar_sim_get_reg(2U, REG_PA_CH4_BIAS_ON) == ADAR1000Manager::kPaBiasTxSafe);
    assert(mock_adar_sim_get_reg(2U, REG_CH4_TX_GAIN) == 0x00U);
}

// ---------------------------------------------------------------------------
// Suite 5d: BIST -- VGG_PINCHOFF & PA_OVERCURRENT across U10@0x48 & U88@0x4A
// ---------------------------------------------------------------------------
static void test_bist_vgg_pinchoff_and_overcurrent_quadrant_map()
{
    spy_reset();
    mock_adar_sim_enable(true);

    ADAR1000Manager mgr;
    assert(mgr.initializeAllDevices());

    // Physical PA_1 (ADTR1107_1, pa_idx0 = 0 -> U10 @ 0x48 CH0) routes to ADAR1_ CH2 (aperture idx 1):
    // Inject VGG pinch-off (raw = 1 -> Idq = 0.052 A < 0.10 A)
    mock_i2c_ads7830_set_channel(2U, kI2c2AdcIdqBank0Addr7Bit, 0U, 1U);

    // Physical PA_12 (ADTR1107_12, pa_idx0 = 11 -> U88 @ 0x4A CH3) routes to ADAR3_ CH2 (aperture idx 9):
    // Inject PA drain overcurrent (raw = 185 -> Idq = 9.576 A > 2.50 A)
    mock_i2c_ads7830_set_channel(2U, kI2c2AdcIdqBank1Addr7Bit, 3U, 185U);

    ADAR1000_BIST bist;
    const ADAR1000_BIST::Report rep = bist.runFullBist(mgr);

    assert(!rep.overall_pass);
    assert(rep.healthy_channel_count == 14U);
    assert(rep.faulty_channel_count == 2U);

    // Aperture idx 1 (ADAR1_ CH2 -> ADTR1107_1) must report FAULT_VGG_PINCHOFF
    assert(rep.channels[1].adtr1107_1based == 1U);
    assert((rep.channels[1].fault_mask & ADAR1000_BIST::FAULT_VGG_PINCHOFF) != 0U);

    // Aperture idx 9 (ADAR3_ CH2 -> ADTR1107_12) must report FAULT_PA_OVERCURRENT & pinch off PA_BIAS2
    assert(rep.channels[9].adtr1107_1based == 12U);
    assert((rep.channels[9].fault_mask & ADAR1000_BIST::FAULT_PA_OVERCURRENT) != 0U);
    assert(mock_adar_sim_get_reg(2U, REG_PA_CH2_BIAS_ON) == ADAR1000Manager::kPaBiasTxSafe);
    assert(mock_adar_sim_get_reg(2U, REG_CH2_TX_GAIN) == 0x00U);
}

// ---------------------------------------------------------------------------
// Suite 5e: BIST -- I2C2 Bank 1 NACK isolation (U88 @ 0x4A)
// ---------------------------------------------------------------------------
static void test_bist_i2c2_bank1_nack_isolation()
{
    spy_reset();
    mock_adar_sim_enable(true);

    ADAR1000Manager mgr;
    assert(mgr.initializeAllDevices());

    // Disable ACK only on U88 @ 0x4A (Bank 1 PA indices 8..15 -> aperture indices 8..15)
    mock_i2c_ads7830_set_ack(2U, kI2c2AdcIdqBank1Addr7Bit, false);

    ADAR1000_BIST bist;
    const ADAR1000_BIST::Report rep = bist.runFullBist(mgr);

    assert(!rep.overall_pass);
    assert(rep.healthy_channel_count == 8U);
    assert(rep.faulty_channel_count == 8U);
    for (uint8_t ap = 0; ap < 8U; ++ap) {
        assert(rep.channels[ap].fault_mask == ADAR1000_BIST::FAULT_NONE);
    }
    for (uint8_t ap = 8U; ap < 16U; ++ap) {
        assert((rep.channels[ap].fault_mask & ADAR1000_BIST::FAULT_I2C_READ) != 0U);
    }
}

int main()
{
    std::printf("=== ADAR1000 Bugfixes (1-4), PCB Phase LUT & BIST Unit Tests ===\n");

    RUN_TEST(test_bug1_bias_en_active_low_tx_and_rx);
    RUN_TEST(test_bug2_hardware_spi_addresses);
    RUN_TEST(test_bug3_one_based_channel_indexing_and_bounds);
    RUN_TEST(test_bug4_pcb_phase_lut_and_quadrant_i2c_topology);
    RUN_TEST(test_bist_nominal_4db_spread_equalizes_to_zero);
    RUN_TEST(test_bist_open_circuit_fault_detection);
    RUN_TEST(test_bist_overdrive_high_vswr_pinchoff);
    RUN_TEST(test_bist_vgg_pinchoff_and_overcurrent_quadrant_map);
    RUN_TEST(test_bist_i2c2_bank1_nack_isolation);

    std::printf("=== Results: %d/%d passed ===\n", g_passed, g_total);
    return (g_passed == g_total) ? 0 : 1;
}
