// ADAR1000_BIST.h -- Built-In Self-Test (BIST) & Closed-Loop TX Power Equalization
// for the 16-channel PLFM_RADAR phased array (4x ADAR1000 + 16x ADTR1107 + PA telemetry).
//
// Hardware signal chain verified against RADAR_Main_Board.sch & ADAR1000 Rev. B:
//   - RF directional coupler feedback: ADTR1107_k CPLR_OUT (Pad 12) -> ADARx_ DET1..4
//     (enabled via 0x030 MISC_ENABLES bits [3:0] with Bit 5 BIAS_EN = 0 active-low;
//      sampled via 8-bit on-chip SAR ADC 0x032 ADC_CTRL MUX_SEL = 1..4 -> 0x033 ADC_OUT).
//   - Non-linear quadrant routing:
//       ADAR1_ (addr 0b00): CH1..4 -> ADTR1107_3,  1,  2,  4
//       ADAR2_ (addr 0b10): CH1..4 -> ADTR1107_7,  5,  6,  8
//       ADAR3_ (addr 0b01): CH1..4 -> ADTR1107_10, 12, 11, 9
//       ADAR4_ (addr 0b11): CH1..4 -> ADTR1107_14, 16, 15, 13
//   - PA quiescent current telemetry on I2C2 (separate bus from I2C1 DACs U7@0x48 / U69@0x49):
//       U10 ADS7830 @ 0x48 -> INA241A3 (G=50 V/V, Rshunt=5 mOhm) Bank 0 (ch 0..7)
//       U88 ADS7830 @ 0x4A -> INA241A3 (G=50 V/V, Rshunt=5 mOhm) Bank 1 (ch 8..15)
//       U89 ADS7830 @ 0x49 -> TMP37 thermistor array (ch 0..7)

#ifndef ADAR1000_BIST_H
#define ADAR1000_BIST_H

#include "ADAR1000_Manager.h"
#include "ADAR1000_PcbPhaseLut.h"
#include <stdint.h>

class ADAR1000_BIST {
public:
    enum FaultMask : uint8_t {
        FAULT_NONE                = 0x00U,
        FAULT_SPI_COMM            = 0x01U, // Scratchpad verify or BIAS_EN readback failed
        FAULT_I2C_READ            = 0x02U, // ADS7830 I2C2 read NACK / timeout (0xFF)
        FAULT_VGG_PINCHOFF        = 0x04U, // Idq < min_idq_amps (gate pinched off / open drain rail)
        FAULT_PA_OVERCURRENT      = 0x08U, // Idq > max_idq_amps (drain short / bias runaway)
        FAULT_OPEN_CIRCUIT        = 0x10U, // Coupler DETx code < min_det_code_open despite active TX
        FAULT_OVERDRIVE_HIGH_VSWR = 0x20U  // Coupler DETx code > max_det_code_overdrive (compression / high VSWR)
    };

    struct Config {
        uint8_t initial_tx_vga_reg = 0xFFU; // Bypass + max 7-bit VGA code (0x7F)
        uint8_t min_tx_vga_code    = 0x40U; // Minimum 7-bit VGA code floor
        uint8_t max_tx_vga_code    = 0x7FU; // Maximum 7-bit VGA code ceiling

        float det_code_at_0dbm  = 60.0f;
        float det_lsb_per_db    = 6.0f;
        float tx_vga_db_per_lsb = 0.5f;

        uint8_t min_det_code_open      = 12U;
        uint8_t max_det_code_overdrive = 225U;

        bool  check_external_pa_idq = true;
        float min_idq_amps          = 0.10f;
        float max_idq_amps          = 2.50f;

        bool    auto_target_min_healthy = true;
        float   fixed_target_power_dbm  = 5.0f;
        float   spread_tolerance_db     = 0.25f;
        uint8_t max_equalization_iters  = 4U;
    };

    struct ChannelDiagnostic {
        uint8_t aperture_idx;
        uint8_t adar_dev_idx;
        uint8_t adar_hw_addr;
        uint8_t adar_channel_1based;
        uint8_t adtr1107_1based;
        uint8_t raw_idq_adc;
        float   idq_amps;
        uint8_t initial_det_code;
        uint8_t final_det_code;
        float   initial_power_dbm;
        float   final_power_dbm;
        uint8_t applied_tx_vga_reg;
        uint8_t fault_mask;
    };

    struct Report {
        bool     overall_pass;
        bool     spi_bus_healthy;
        bool     bias_en_verified_active_low;
        uint8_t  healthy_channel_count;
        uint8_t  faulty_channel_count;
        uint8_t  iterations_executed;
        float    initial_spread_db;
        float    final_spread_db;
        float    target_power_dbm;
        float    max_board_temp_c;
        ChannelDiagnostic channels[kRadarTotalChannels];
    };

    typedef bool (*Ads7830ReadFn)(uint8_t i2c_bus_id, uint8_t addr_7bit, uint8_t channel, uint8_t* out_raw, void* user_ctx);

    ADAR1000_BIST();
    explicit ADAR1000_BIST(const Config& cfg);

    void setConfig(const Config& cfg) { config_ = cfg; }
    const Config& getConfig() const { return config_; }

    void setAds7830Reader(Ads7830ReadFn fn, void* user_ctx = nullptr) {
        ads_reader_fn_ = fn;
        ads_reader_ctx_ = user_ctx;
    }

    static float rawAdcToIdqAmps(uint8_t raw_adc);
    static float rawAdcToTempCelsius(uint8_t raw_adc);
    float detCodeToDbm(uint8_t det_code) const;

    bool readAds7830Channel(uint8_t addr_7bit, uint8_t channel, uint8_t* out_raw) const;
    bool readPaIdqChannel(uint8_t pa_index_0based, uint8_t* out_raw, float* out_amps) const;
    bool readMaxBoardTemperatureC(float* out_max_temp_c) const;

    Report runFullBist(ADAR1000Manager& mgr) const;

private:
    Config        config_;
    Ads7830ReadFn ads_reader_fn_;
    void*         ads_reader_ctx_;

    static bool defaultHalAds7830Read(uint8_t i2c_bus_id, uint8_t addr_7bit, uint8_t channel, uint8_t* out_raw, void* user_ctx);
};

#endif // ADAR1000_BIST_H
