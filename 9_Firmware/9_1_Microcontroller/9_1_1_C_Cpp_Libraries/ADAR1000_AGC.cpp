// ADAR1000_AGC.cpp -- STM32 outer-loop AGC implementation
//
// See ADAR1000_AGC.h for architecture overview.
// Includes saturating uint8_t arithmetic & attack underflow guard (PR #154 / Issue #145 & #147).

#include "ADAR1000_AGC.h"
#include "ADAR1000_Manager.h"
#include "diag_log.h"

#include <cstring>
#include <limits>

// ---------------------------------------------------------------------------
// Constructor -- set all config fields to safe defaults
// ---------------------------------------------------------------------------
ADAR1000_AGC::ADAR1000_AGC()
    : agc_base_gain(ADAR1000Manager::kDefaultRxVgaGain) // 30
    , gain_step_down(4)
    , gain_step_up(1)
    , min_gain(0)
    , max_gain(127)
    , holdoff_frames(4)
    , enabled(false)
    , holdoff_counter(0)
    , last_saturated(false)
    , saturation_event_count(0)
{
    memset(cal_offset, 0, sizeof(cal_offset));
}

// ---------------------------------------------------------------------------
// update -- called once per frame with the FPGA DIG_5 saturation flag
// ---------------------------------------------------------------------------
void ADAR1000_AGC::update(bool fpga_saturation)
{
    if (!enabled)
        return;

    last_saturated = fpga_saturation;

    if (fpga_saturation) {
        // Attack: reduce gain immediately using saturating uint8_t arithmetic.
        // Never allow gain to increase on saturation if agc_base_gain < min_gain (PR #154),
        // and avoid uint8_t addition overflow on (gain_step_down + min_gain) (Issue #147).
        if (saturation_event_count < std::numeric_limits<uint32_t>::max()) {
            saturation_event_count++;
        }
        holdoff_counter = 0;

        if (agc_base_gain > min_gain) {
            const uint8_t headroom_above_min = static_cast<uint8_t>(agc_base_gain - min_gain);
            if (headroom_above_min >= gain_step_down) {
                agc_base_gain = static_cast<uint8_t>(agc_base_gain - gain_step_down);
            } else {
                agc_base_gain = min_gain;
            }
        }

        DIAG("AGC", "SAT detected -- gain_base -> %u  (events=%lu)",
             (unsigned)agc_base_gain, (unsigned long)saturation_event_count);

    } else {
        // Recovery: wait for holdoff, then increase gain with saturating uint8_t bounds.
        if (holdoff_counter < std::numeric_limits<uint8_t>::max()) {
            holdoff_counter++;
        }

        if (holdoff_counter >= holdoff_frames) {
            holdoff_counter = 0;

            if (agc_base_gain < max_gain) {
                const uint8_t headroom_to_max = static_cast<uint8_t>(max_gain - agc_base_gain);
                if (headroom_to_max >= gain_step_up) {
                    agc_base_gain = static_cast<uint8_t>(agc_base_gain + gain_step_up);
                } else {
                    agc_base_gain = max_gain;
                }
            }

            DIAG("AGC", "Recovery step -- gain_base -> %u", (unsigned)agc_base_gain);
        }
    }
}

// ---------------------------------------------------------------------------
// applyGain -- write effective gain to all 16 RX VGA channels
//
// Uses the Manager's adarSetRxVgaGain which takes 1-based channel indices (1..4).
// Along the PCB edge SMA pairs (J24/J25 .. J54/J55), linear aperture index
// (dev * 4 + ch) maps directly to ADAR device `dev` (0..3) channel `ch + 1` (1..4).
// ---------------------------------------------------------------------------
void ADAR1000_AGC::applyGain(ADAR1000Manager &mgr)
{
    for (uint8_t dev = 0; dev < AGC_NUM_DEVICES; ++dev) {
        for (uint8_t ch = 0; ch < AGC_NUM_CHANNELS; ++ch) {
            const uint8_t aperture_idx = static_cast<uint8_t>(dev * AGC_NUM_CHANNELS + ch);
            const uint8_t gain = effectiveGain(aperture_idx);
            mgr.adarSetRxVgaGain(dev, static_cast<uint8_t>(ch + 1U), gain, BROADCAST_OFF);
        }
    }
}

// ---------------------------------------------------------------------------
// resetState -- clear runtime counters, preserve configuration
// ---------------------------------------------------------------------------
void ADAR1000_AGC::resetState()
{
    holdoff_counter = 0;
    last_saturated = false;
    saturation_event_count = 0;
}

// ---------------------------------------------------------------------------
// effectiveGain -- compute clamped per-channel gain
// ---------------------------------------------------------------------------
uint8_t ADAR1000_AGC::effectiveGain(uint8_t channel_index) const
{
    if (channel_index >= AGC_TOTAL_CHANNELS)
        return min_gain;  // safety fallback — OOB channels get minimum gain

    const uint8_t eff_max = (max_gain >= min_gain) ? max_gain : min_gain;
    const int32_t raw = static_cast<int32_t>(agc_base_gain) + static_cast<int32_t>(cal_offset[channel_index]);

    if (raw < static_cast<int32_t>(min_gain))
        return min_gain;
    if (raw > static_cast<int32_t>(eff_max))
        return eff_max;

    return static_cast<uint8_t>(raw);
}
