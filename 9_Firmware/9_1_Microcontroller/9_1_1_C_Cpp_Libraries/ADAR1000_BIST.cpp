// ADAR1000_BIST.cpp -- Built-In Self-Test (BIST) & Closed-Loop TX Power Equalization
// implementation for PLFM_RADAR (AERIS-10N).

#include "ADAR1000_BIST.h"
#include "diag_log.h"

#include <cmath>
#include <cstring>

extern I2C_HandleTypeDef hi2c2;

namespace {

constexpr uint8_t buildAds7830SingleEndedCmd(uint8_t channel) {
    return static_cast<uint8_t>(0x8CU | ((channel & 0x07U) << 4U));
}

} // namespace

ADAR1000_BIST::ADAR1000_BIST()
    : config_()
    , ads_reader_fn_(&ADAR1000_BIST::defaultHalAds7830Read)
    , ads_reader_ctx_(nullptr)
{
}

ADAR1000_BIST::ADAR1000_BIST(const Config& cfg)
    : config_(cfg)
    , ads_reader_fn_(&ADAR1000_BIST::defaultHalAds7830Read)
    , ads_reader_ctx_(nullptr)
{
}

bool ADAR1000_BIST::defaultHalAds7830Read(uint8_t i2c_bus_id,
                                          uint8_t addr_7bit,
                                          uint8_t channel,
                                          uint8_t* out_raw,
                                          void* user_ctx)
{
    (void)user_ctx;
    if (out_raw == nullptr || channel > 7U || i2c_bus_id != 2U) {
        return false;
    }

    uint8_t cmd = buildAds7830SingleEndedCmd(channel);
    const uint16_t shifted_addr = static_cast<uint16_t>(static_cast<uint16_t>(addr_7bit) << 1U);

    if (HAL_I2C_Master_Transmit(&hi2c2, shifted_addr, &cmd, 1U, 100U) != HAL_OK) {
        *out_raw = 0xFFU;
        return false;
    }

    HAL_Delay(1U);

    uint8_t rx = 0xFFU;
    if (HAL_I2C_Master_Receive(&hi2c2, shifted_addr, &rx, 1U, 100U) != HAL_OK) {
        *out_raw = 0xFFU;
        return false;
    }

    *out_raw = rx;
    return true;
}

float ADAR1000_BIST::rawAdcToIdqAmps(uint8_t raw_adc)
{
    return (3.3f / 255.0f) * static_cast<float>(raw_adc) / (50.0f * 0.005f);
}

float ADAR1000_BIST::rawAdcToTempCelsius(uint8_t raw_adc)
{
    return static_cast<float>(raw_adc) * (165.0f / 255.0f);
}

float ADAR1000_BIST::detCodeToDbm(uint8_t det_code) const
{
    const float slope = (config_.det_lsb_per_db > 1e-3f) ? config_.det_lsb_per_db : 6.0f;
    return (static_cast<float>(det_code) - config_.det_code_at_0dbm) / slope;
}

bool ADAR1000_BIST::readAds7830Channel(uint8_t addr_7bit, uint8_t channel, uint8_t* out_raw) const
{
    if (out_raw == nullptr || channel > 7U || ads_reader_fn_ == nullptr) {
        return false;
    }
    return ads_reader_fn_(2U, addr_7bit, channel, out_raw, ads_reader_ctx_);
}

bool ADAR1000_BIST::readPaIdqChannel(uint8_t pa_index_0based, uint8_t* out_raw, float* out_amps) const
{
    if (pa_index_0based >= kRadarTotalChannels || out_raw == nullptr || out_amps == nullptr) {
        return false;
    }

    const uint8_t adc_addr = (pa_index_0based < 8U) ? kI2c2AdcIdqBank0Addr7Bit
                                                    : kI2c2AdcIdqBank1Addr7Bit;
    const uint8_t adc_ch   = static_cast<uint8_t>(pa_index_0based & 0x07U);

    uint8_t raw = 0xFFU;
    const bool ok = readAds7830Channel(adc_addr, adc_ch, &raw);
    *out_raw = raw;
    if (!ok || raw == 0xFFU) {
        *out_amps = 0.0f;
        return false;
    }

    *out_amps = rawAdcToIdqAmps(raw);
    return true;
}

bool ADAR1000_BIST::readMaxBoardTemperatureC(float* out_max_temp_c) const
{
    if (out_max_temp_c == nullptr) {
        return false;
    }

    float max_t = -273.15f;
    bool any_ok = false;
    for (uint8_t ch = 0U; ch < 8U; ++ch) {
        uint8_t raw = 0U;
        if (readAds7830Channel(kI2c2AdcTempAddr7Bit, ch, &raw) && raw != 0xFFU) {
            const float t_c = rawAdcToTempCelsius(raw);
            if (!any_ok || t_c > max_t) {
                max_t = t_c;
                any_ok = true;
            }
        }
    }

    *out_max_temp_c = max_t;
    return any_ok;
}

ADAR1000_BIST::Report ADAR1000_BIST::runFullBist(ADAR1000Manager& mgr) const
{
    DIAG_SECTION("ADAR1000 BIST & TX EQUALIZATION");

    Report rep;
    std::memset(&rep, 0, sizeof(rep));
    rep.spi_bus_healthy = true;
    rep.bias_en_verified_active_low = true;
    rep.max_board_temp_c = -273.15f;

    for (uint8_t ap = 0U; ap < kRadarTotalChannels; ++ap) {
        const uint8_t dev = static_cast<uint8_t>(ap / kAdarChannelsPerDevice);
        const uint8_t ch1 = static_cast<uint8_t>((ap % kAdarChannelsPerDevice) + 1U);
        ChannelDiagnostic& cd = rep.channels[ap];
        cd.aperture_idx        = ap;
        cd.adar_dev_idx        = dev;
        cd.adar_hw_addr        = (static_cast<size_t>(dev) < mgr.devices_.size())
                                     ? mgr.devices_[dev]->dev_addr
                                     : kAdarHwSpiAddress[dev];
        cd.adar_channel_1based = ch1;
        cd.adtr1107_1based     = kAdarToAdtr1107OneBased[dev][ch1 - 1U];
        cd.applied_tx_vga_reg  = config_.initial_tx_vga_reg;
        cd.fault_mask          = FAULT_NONE;
    }

    for (uint8_t dev = 0U; dev < kAdarNumDevices; ++dev) {
        const bool addr_ok = (static_cast<size_t>(dev) < mgr.devices_.size()) &&
                             (mgr.devices_[dev]->dev_addr == kAdarHwSpiAddress[dev]);
        const bool spi_ok  = addr_ok && mgr.verifyDeviceCommunication(dev);
        if (!spi_ok) {
            rep.spi_bus_healthy = false;
            for (uint8_t c = 0U; c < kAdarChannelsPerDevice; ++c) {
                rep.channels[dev * kAdarChannelsPerDevice + c].fault_mask |= FAULT_SPI_COMM;
            }
        }
    }

    mgr.setAllDevicesTXMode();

    uint8_t broadside_pattern[kRadarTotalChannels] = {0U};
    mgr.setPcbPhaseCompensation(true);
    mgr.setCustomBeamPattern16(broadside_pattern, ADAR1000Manager::BeamDirection::TX);

    for (uint8_t dev = 0U; dev < kAdarNumDevices; ++dev) {
        if ((rep.channels[dev * kAdarChannelsPerDevice].fault_mask & FAULT_SPI_COMM) != 0U) {
            continue;
        }
        uint8_t misc = mgr.readRegister(dev, REG_MISC_ENABLES);
        if ((misc & MISC_ENABLES_BIAS_EN_MASK) != 0U) {
            rep.bias_en_verified_active_low = false;
            misc = static_cast<uint8_t>(misc & ~MISC_ENABLES_BIAS_EN_MASK);
        }
        misc = static_cast<uint8_t>((misc | MISC_ENABLES_ALL_DET_EN) & ~MISC_ENABLES_BIAS_EN_MASK);
        mgr.writeRegister(dev, REG_MISC_ENABLES, misc);

        const uint8_t rb_misc = mgr.readRegister(dev, REG_MISC_ENABLES);
        if ((rb_misc & MISC_ENABLES_BIAS_EN_MASK) != 0U) {
            rep.bias_en_verified_active_low = false;
            for (uint8_t c = 0U; c < kAdarChannelsPerDevice; ++c) {
                rep.channels[dev * kAdarChannelsPerDevice + c].fault_mask |= FAULT_SPI_COMM;
            }
        }

        for (uint8_t ch1 = 1U; ch1 <= kAdarChannelsPerDevice; ++ch1) {
            mgr.adarSetTxVgaGain(dev, ch1, config_.initial_tx_vga_reg, BROADCAST_OFF);
        }
    }

    float max_temp_c = -273.15f;
    if (readMaxBoardTemperatureC(&max_temp_c)) {
        rep.max_board_temp_c = max_temp_c;
    }

    float min_healthy_p =  1e9f;
    float max_healthy_p = -1e9f;

    for (uint8_t ap = 0U; ap < kRadarTotalChannels; ++ap) {
        ChannelDiagnostic& cd = rep.channels[ap];
        const uint8_t pa_idx0 = static_cast<uint8_t>(cd.adtr1107_1based - 1U);

        if (config_.check_external_pa_idq) {
            uint8_t raw_idq = 0xFFU;
            float   amps    = 0.0f;
            if (!readPaIdqChannel(pa_idx0, &raw_idq, &amps)) {
                cd.raw_idq_adc = raw_idq;
                cd.idq_amps    = 0.0f;
                cd.fault_mask |= FAULT_I2C_READ;
            } else {
                cd.raw_idq_adc = raw_idq;
                cd.idq_amps    = amps;
                if (amps < config_.min_idq_amps) {
                    cd.fault_mask |= FAULT_VGG_PINCHOFF;
                } else if (amps > config_.max_idq_amps) {
                    cd.fault_mask |= FAULT_PA_OVERCURRENT;
                }
            }
        }

        if ((cd.fault_mask & FAULT_SPI_COMM) == 0U) {
            const uint8_t det_raw = mgr.readPowerDetector(cd.adar_dev_idx, cd.adar_channel_1based);
            cd.initial_det_code  = det_raw;
            cd.final_det_code    = det_raw;
            cd.initial_power_dbm = detCodeToDbm(det_raw);
            cd.final_power_dbm   = cd.initial_power_dbm;

            if (det_raw < config_.min_det_code_open) {
                cd.fault_mask |= FAULT_OPEN_CIRCUIT;
            } else if (det_raw > config_.max_det_code_overdrive) {
                cd.fault_mask |= FAULT_OVERDRIVE_HIGH_VSWR;
            }
        }

        if ((cd.fault_mask & (FAULT_PA_OVERCURRENT | FAULT_OVERDRIVE_HIGH_VSWR)) != 0U) {
            mgr.adarSetPaBiasOn(cd.adar_dev_idx, cd.adar_channel_1based, ADAR1000Manager::kPaBiasTxSafe, BROADCAST_OFF);
            mgr.adarSetTxVgaGain(cd.adar_dev_idx, cd.adar_channel_1based, 0x00U, BROADCAST_OFF);
            cd.applied_tx_vga_reg = 0x00U;
        }

        if (cd.fault_mask == FAULT_NONE) {
            rep.healthy_channel_count++;
            if (cd.initial_power_dbm < min_healthy_p) min_healthy_p = cd.initial_power_dbm;
            if (cd.initial_power_dbm > max_healthy_p) max_healthy_p = cd.initial_power_dbm;
        } else {
            rep.faulty_channel_count++;
        }
    }

    if (rep.healthy_channel_count == 0U) {
        rep.overall_pass = false;
        return rep;
    }

    rep.initial_spread_db = max_healthy_p - min_healthy_p;
    rep.final_spread_db   = rep.initial_spread_db;
    rep.target_power_dbm  = config_.auto_target_min_healthy ? min_healthy_p : config_.fixed_target_power_dbm;

    const uint8_t attn_bypass_bit = static_cast<uint8_t>(config_.initial_tx_vga_reg & 0x80U);
    const float vga_step_db = (config_.tx_vga_db_per_lsb > 1e-3f) ? config_.tx_vga_db_per_lsb : 0.5f;

    for (uint8_t iter = 0U; iter < config_.max_equalization_iters; ++iter) {
        if (rep.final_spread_db <= config_.spread_tolerance_db) {
            break;
        }

        rep.iterations_executed++;

        for (uint8_t ap = 0U; ap < kRadarTotalChannels; ++ap) {
            ChannelDiagnostic& cd = rep.channels[ap];
            if (cd.fault_mask != FAULT_NONE) {
                continue;
            }

            const float err_db = rep.target_power_dbm - cd.final_power_dbm;
            const int32_t delta_steps = static_cast<int32_t>(std::lround(err_db / vga_step_db));
            int32_t cur_code = static_cast<int32_t>(cd.applied_tx_vga_reg & 0x7FU);
            int32_t next_code = cur_code + delta_steps;

            if (next_code < static_cast<int32_t>(config_.min_tx_vga_code)) {
                next_code = static_cast<int32_t>(config_.min_tx_vga_code);
            }
            if (next_code > static_cast<int32_t>(config_.max_tx_vga_code)) {
                next_code = static_cast<int32_t>(config_.max_tx_vga_code);
            }

            const uint8_t next_reg = static_cast<uint8_t>(attn_bypass_bit | (static_cast<uint8_t>(next_code) & 0x7FU));
            cd.applied_tx_vga_reg = next_reg;
            mgr.adarSetTxVgaGain(cd.adar_dev_idx, cd.adar_channel_1based, next_reg, BROADCAST_OFF);
        }

        float iter_min_p =  1e9f;
        float iter_max_p = -1e9f;
        for (uint8_t ap = 0U; ap < kRadarTotalChannels; ++ap) {
            ChannelDiagnostic& cd = rep.channels[ap];
            if (cd.fault_mask != FAULT_NONE) {
                continue;
            }
            const uint8_t det_raw = mgr.readPowerDetector(cd.adar_dev_idx, cd.adar_channel_1based);
            cd.final_det_code  = det_raw;
            cd.final_power_dbm = detCodeToDbm(det_raw);

            if (det_raw > config_.max_det_code_overdrive) {
                cd.fault_mask |= FAULT_OVERDRIVE_HIGH_VSWR;
                rep.healthy_channel_count--;
                rep.faulty_channel_count++;
                mgr.adarSetPaBiasOn(cd.adar_dev_idx, cd.adar_channel_1based, ADAR1000Manager::kPaBiasTxSafe, BROADCAST_OFF);
                mgr.adarSetTxVgaGain(cd.adar_dev_idx, cd.adar_channel_1based, 0x00U, BROADCAST_OFF);
                cd.applied_tx_vga_reg = 0x00U;
                continue;
            }

            if (cd.final_power_dbm < iter_min_p) iter_min_p = cd.final_power_dbm;
            if (cd.final_power_dbm > iter_max_p) iter_max_p = cd.final_power_dbm;
        }

        if (rep.healthy_channel_count == 0U) {
            rep.overall_pass = false;
            return rep;
        }
        rep.final_spread_db = iter_max_p - iter_min_p;
    }

    rep.overall_pass = rep.spi_bus_healthy &&
                       rep.bias_en_verified_active_low &&
                       (rep.faulty_channel_count == 0U) &&
                       (rep.final_spread_db <= config_.spread_tolerance_db);
    return rep;
}
