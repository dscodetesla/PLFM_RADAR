// ADAR1000_PcbPhaseLut.h -- MainBoard 10.5 GHz PCB RF trace phase compensation
// and schematic-verified hardware topology LUTs for AERIS-10N (PLFM_RADAR).
//
// Provenance:
//   1. Electromagnetic geometry extracted from RADAR_Main_Board.brd (10-layer
//      Rogers RO4350B h = 0.102 mm / 4 mil core, microstrip w = 0.204 mm,
//      f0 = 10.5 GHz, guided wavelength lambda_g = 17.3618 mm):
//        - TX path (U16 EP4RKU+ -> ADAR1..4 -> ADTR1107_1..16 -> RF_SW_1..16 -> J25..J55):
//          L_TX spans 83.2882 mm (aperture idx 4, J33) to 84.5783 mm (idx 11, J47),
//          max spread = 1.2901 mm (26.75 deg; +22.01 deg vs aperture idx 0).
//        - RX path (J24..J54 -> RF_SW_1..16 -> ADTR1107_1..16 -> ADAR1..4 -> U16 EP4RKU+):
//          L_RX spans 81.8236 mm (aperture idx 5, J34, -37.62 deg vs idx 0) to
//          84.1915 mm (aperture idx 6, J36, +11.48 deg vs idx 0), max spread = 2.3679 mm (49.10 deg).
//   2. Hardware pinout and bus topology extracted from RADAR_Main_Board.sch:
//        - ADAR1000 SPI chip addresses ADDR1:ADDR0:
//          ADAR1_ = 0b00 (0), ADAR2_ = 0b10 (2), ADAR3_ = 0b01 (1), ADAR4_ = 0b11 (3).
//        - Non-linear quadrant routing ADARx_ CH1..4 -> ADTR1107_k (1..16):
//          ADAR1_: {3, 1, 2, 4}, ADAR2_: {7, 5, 6, 8},
//          ADAR3_: {10, 12, 11, 9}, ADAR4_: {14, 16, 15, 13}.
//          Along the PCB edge SMA pairs (J24/J25 .. J54/J55), linear aperture
//          index k = 0..15 maps directly to (dev = k / 4, ch_1based = (k % 4) + 1).
//        - I2C1 / I2C2 bus separation (no 0x48 collision on PCB):
//          I2C1: U7 DAC5578 @ 0x48 (VG 1..8), U69 DAC5578 @ 0x49 (VG 9..16).
//          I2C2: U10 ADS7830 @ 0x48 (INA241A3 Bank 0: U11, U73..U79),
//                U88 ADS7830 @ 0x4A (INA241A3 Bank 1: U80..U87),
//                U89 ADS7830 @ 0x49 (TMP37 thermistors JP*).

#ifndef ADAR1000_PCB_PHASE_LUT_H
#define ADAR1000_PCB_PHASE_LUT_H

#include <stdint.h>

// Number of ADAR1000 beamformer ICs and channels on MainBoard
static constexpr uint8_t kAdarNumDevices = 4U;
static constexpr uint8_t kAdarChannelsPerDevice = 4U;
static constexpr uint8_t kRadarTotalChannels = 16U;

// Bug 2 fix: Schematic-verified hardware SPI address pins ADDR1:ADDR0
// for ADAR1_, ADAR2_, ADAR3_, ADAR4_ (RADAR_Main_Board.sch).
static constexpr uint8_t kAdarHwSpiAddress[kAdarNumDevices] = {
    0U, // ADAR1_: ADDR1=GND, ADDR0=GND -> 0b00
    2U, // ADAR2_: ADDR1=1V8, ADDR0=GND -> 0b10
    1U, // ADAR3_: ADDR1=GND, ADDR0=1V8 -> 0b01
    3U  // ADAR4_: ADDR1=1V8, ADDR0=1V8 -> 0b11
};

// Non-linear quadrant routing: (dev_idx 0..3, ch_idx 0..3) -> 1-based ADTR1107 index (1..16).
// Verified from TXx_y, RXx_y, DETx_y, and PA_BIASx_y nets in RADAR_Main_Board.sch.
static constexpr uint8_t kAdarToAdtr1107OneBased[kAdarNumDevices][kAdarChannelsPerDevice] = {
    { 3U,  1U,  2U,  4U}, // ADAR1_ CH1..CH4 -> ADTR1107_3,  1,  2,  4 (J24/J25 .. J30/J31)
    { 7U,  5U,  6U,  8U}, // ADAR2_ CH1..CH4 -> ADTR1107_7,  5,  6,  8 (J32/J33 .. J38/J39)
    {10U, 12U, 11U,  9U}, // ADAR3_ CH1..CH4 -> ADTR1107_10, 12, 11, 9 (J40/J41 .. J46/J47)
    {14U, 16U, 15U, 13U}  // ADAR4_ CH1..CH4 -> ADTR1107_14, 16, 15, 13 (J48/J49 .. J54/J55)
};

// Linear SMA aperture index (0..15, J24/J25 .. J54/J55) -> 1-based ADTR1107 index (1..16).
static constexpr uint8_t kApertureToAdtr1107OneBased[kRadarTotalChannels] = {
     3U,  1U,  2U,  4U,
     7U,  5U,  6U,  8U,
    10U, 12U, 11U,  9U,
    14U, 16U, 15U, 13U
};

// Inverse quadrant lookup: 0-based ADTR1107 index (0..15 for ADTR1107_1..16)
// -> owning ADAR1000 device index (0..3) and 1-based ADAR1000 channel (1..4).
static constexpr uint8_t kAdtr1107ZeroBasedToAdarDev[kRadarTotalChannels] = {
    0U, 0U, 0U, 0U, // ADTR1107_1..4  -> ADAR1_
    1U, 1U, 1U, 1U, // ADTR1107_5..8  -> ADAR2_
    2U, 2U, 2U, 2U, // ADTR1107_9..12 -> ADAR3_
    3U, 3U, 3U, 3U  // ADTR1107_13..16 -> ADAR4_
};

static constexpr uint8_t kAdtr1107ZeroBasedToAdarCh1Based[kRadarTotalChannels] = {
    2U, 3U, 1U, 4U, // ADTR1107_1->CH2, _2->CH3, _3->CH1, _4->CH4
    2U, 3U, 1U, 4U, // ADTR1107_5->CH2, _6->CH3, _7->CH1, _8->CH4
    4U, 1U, 3U, 2U, // ADTR1107_9->CH4, _10->CH1, _11->CH3, _12->CH2
    4U, 1U, 3U, 2U  // ADTR1107_13->CH4, _14->CH1, _15->CH3, _16->CH2
};

// Schematic-verified I2C1 / I2C2 7-bit slave addresses on MainBoard:
//   - I2C1 (STM32_SCL1 / STM32_SDA1): DAC5578 gate-bias DACs U7 & U69
//   - I2C2 (STM32_SCL2 / STM32_SDA2): ADS7830 monitoring ADCs U10, U88 & U89
static constexpr uint8_t kI2c1DacVgBank0Addr7Bit  = 0x48U; // U7  (DAC5578, VG 1..8)
static constexpr uint8_t kI2c1DacVgBank1Addr7Bit  = 0x49U; // U69 (DAC5578, VG 9..16)
static constexpr uint8_t kI2c2AdcIdqBank0Addr7Bit = 0x48U; // U10 (ADS7830, INA241A3 Bank 0: U11, U73..U79)
static constexpr uint8_t kI2c2AdcIdqBank1Addr7Bit = 0x4AU; // U88 (ADS7830, INA241A3 Bank 1: U80..U87)
static constexpr uint8_t kI2c2AdcTempAddr7Bit     = 0x49U; // U89 (ADS7830, TMP37 thermistors JP*)

// 6-bit PCB phase compensation LUTs (64-state uniform grid, 5.625 deg/LSB, modulo 64)
// indexed by aperture channel 0..15 (dev*4 + (ch-1), SMA pairs J24/J25 .. J54/J55).
static constexpr uint8_t kPcbPhaseOffsetCodeTx[kRadarTotalChannels] = {
    0x00U, 0x00U, 0x00U, 0x00U,
    0x01U, 0x3FU, 0x3DU, 0x3EU,
    0x3FU, 0x3EU, 0x3DU, 0x3CU,
    0x3FU, 0x3FU, 0x3DU, 0x3DU
};

static constexpr uint8_t kPcbPhaseOffsetCodeRx[kRadarTotalChannels] = {
    0x00U, 0x00U, 0x00U, 0x01U,
    0x01U, 0x07U, 0x3EU, 0x3FU,
    0x06U, 0x02U, 0x3FU, 0x3FU,
    0x04U, 0x05U, 0x3FU, 0x01U
};

// 7-bit PCB phase compensation LUTs (128-state uniform grid, 2.8125 deg/LSB, modulo 128)
// directly indexing ADAR1000Manager::VM_I[128] / VM_Q[128].
static constexpr uint8_t kPcbPhaseOffsetCode7BitTx[kRadarTotalChannels] = {
    0x00U, 0x00U, 0x7FU, 0x00U,
    0x02U, 0x7FU, 0x7AU, 0x7CU,
    0x7EU, 0x7BU, 0x7AU, 0x78U,
    0x7FU, 0x7EU, 0x7AU, 0x79U
};

static constexpr uint8_t kPcbPhaseOffsetCode7BitRx[kRadarTotalChannels] = {
    0x00U, 0x01U, 0x00U, 0x01U,
    0x01U, 0x0DU, 0x7CU, 0x7FU,
    0x0CU, 0x05U, 0x7EU, 0x7DU,
    0x07U, 0x09U, 0x7EU, 0x02U
};

// Convert a 6-bit phase code (0..63, 5.625 deg/LSB) to a 7-bit VM LUT index (0..127, 2.8125 deg/LSB).
constexpr inline uint8_t pcbPhase6BitTo7Bit(uint8_t code6) {
    return static_cast<uint8_t>((code6 & 0x3FU) << 1U);
}

// Apply 6-bit PCB trace phase compensation (modulo 64) for aperture channel 0..15.
constexpr inline uint8_t applyPcbPhaseCompensation6Bit(uint8_t aperture_idx, uint8_t phase6, bool tx_mode) {
    if (aperture_idx >= kRadarTotalChannels) {
        return static_cast<uint8_t>(phase6 & 0x3FU);
    }
    const uint8_t offset = tx_mode ? kPcbPhaseOffsetCodeTx[aperture_idx]
                                   : kPcbPhaseOffsetCodeRx[aperture_idx];
    return static_cast<uint8_t>((phase6 + offset) & 0x3FU);
}

// Apply 7-bit PCB trace phase compensation (modulo 128) for aperture channel 0..15.
constexpr inline uint8_t applyPcbPhaseCompensation7Bit(uint8_t aperture_idx, uint8_t phase7, bool tx_mode) {
    if (aperture_idx >= kRadarTotalChannels) {
        return static_cast<uint8_t>(phase7 & 0x7FU);
    }
    const uint8_t offset = tx_mode ? kPcbPhaseOffsetCode7BitTx[aperture_idx]
                                   : kPcbPhaseOffsetCode7BitRx[aperture_idx];
    return static_cast<uint8_t>((phase7 + offset) & 0x7FU);
}

// Map (ADAR device 0..3, 1-based ADAR channel 1..4) -> 0-based ADTR1107 index (0..15), or 0xFF if invalid.
constexpr inline uint8_t mapAdarChannelToAdtr1107ZeroBased(uint8_t dev_idx, uint8_t ch_1based) {
    if (dev_idx >= kAdarNumDevices || ch_1based < 1U || ch_1based > kAdarChannelsPerDevice) {
        return 0xFFU;
    }
    return static_cast<uint8_t>(kAdarToAdtr1107OneBased[dev_idx][ch_1based - 1U] - 1U);
}

#endif // ADAR1000_PCB_PHASE_LUT_H
